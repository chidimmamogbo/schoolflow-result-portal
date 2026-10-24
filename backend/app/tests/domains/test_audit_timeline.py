"""The school's audit timeline (BUILD_PROMPT 9.2j; SPEC F11; D-171).

Behaviour: school admins read their school's audit events newest first, with
who did it (name and role), what, on which record, before and after, the
reason and when; they filter by area, action, person, record and dates, a
page at a time. Other staff, parents and pupils are refused; the super admin
uses the platform log; another school's events never appear. All data is
fictional.
"""

from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tests.auth_support import logged_in, make_login
from app.tests.domains.test_publication import (
    app,
    approve_all,
    as_,
    code_of,
    fast_hashing,
    gmc,
    principal_comments,
    send,
)
from app.tests.factories import create_school, write_audit_event

__all__ = ["app", "fast_hashing", "gmc"]


def events(app: FastAPI, query: str = "") -> dict[str, Any]:
    status, body = send(as_(app, "ngozi.okeke"), "GET", f"/school/audit{query}")
    assert status == 200, body
    return body


def test_school_admins_read_a_filtered_timeline(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    approve_all(app, gmc)
    principal_comments(app, gmc)
    other = create_school(db_session, code="BSA", name="Bright Star Academy")
    write_audit_event(db_session, other, "results.secret_elsewhere")

    timeline = events(app)
    assert timeline["has_more"] is False
    rows = timeline["events"]
    assert rows and all(e["action"] != "results.secret_elsewhere" for e in rows)
    stamps = [e["created_at"] for e in rows]
    assert stamps == sorted(stamps, reverse=True)
    # One test transaction gives every event the same time, so pick the event by its action.
    latest = next(e for e in rows if e["action"] == "results.principal_comments")
    assert (latest["action"], latest["actor_name"], latest["actor_role"]) == (
        "results.principal_comments",
        "Ngozi Okeke",
        "school_admin",
    )
    assert latest["new_values"] == {"count": 3}
    total = db_session.scalar(
        text("select count(*) from audit_events where school_id = :s"), {"s": gmc["school"]}
    )
    assert len(rows) == total

    sheets = events(app, "?area=sheets")["events"]
    assert sheets and all(e["action"].startswith("sheets.") for e in sheets)
    assert [e["action"] for e in events(app, "?action=results.principal_comments")["events"]] == [
        "results.principal_comments"
    ]
    mine = events(app, f"?actor_id={gmc['tunde']}")["events"]
    assert mine and {e["actor_name"] for e in mine} == {"Tunde Adebayo"}
    target = latest["target_id"]
    on_record = events(app, f"?target_table=class_report_sections&target_id={target}")["events"]
    assert [e["id"] for e in on_record] == [latest["id"]]
    assert len(events(app, "?since=2000-01-01&until=2999-12-31")["events"]) == total
    assert events(app, "?until=2000-01-01")["events"] == []
    assert events(app, "?since=2999-01-01")["events"] == []

    first = events(app, "?limit=2")
    second = events(app, "?limit=2&offset=2")
    assert (len(first["events"]), first["has_more"]) == (2, True)
    assert [e["id"] for e in first["events"] + second["events"]] == [e["id"] for e in rows[:4]]
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "GET", "/school/audit?area=results;drop")[0] == 422
    assert send(ngozi, "GET", "/school/audit?limit=201")[0] == 422


def test_only_school_admins_read_it(app: FastAPI, db_session: Session, gmc: dict[str, Any]) -> None:
    for client in (
        as_(app, "tunde.adebayo"),
        as_(app, "emeka.nwosu"),
        as_(app, "ikenna.obi"),
        logged_in(app, "chukwuemeka.obi", school_code="GMC"),
    ):
        assert code_of(send(client, "GET", "/school/audit")) == (403, "permission_denied")
    make_login(db_session, username="super.admin", full_name="Platform Owner", is_super_admin=True)
    assert send(as_(app, "super.admin"), "GET", "/school/audit")[0] == 404
