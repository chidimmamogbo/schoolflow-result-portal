"""The notice board (BUILD_PROMPT 9.2o; SPEC F17; AC17.1 to AC17.3; D-084 to D-086, D-175).

Behaviour: school admins post plain-text notices to everyone, to chosen
roles, to chosen classes, or to roles within classes; the people told are
worked out when it is posted and kept (D-084), except that a pinned notice
for everyone also reaches people who join later. Everyone reads only the
notices addressed to them, pinned first then newest, with an unread count
and a read mark; a parent linked to several schools sees each school's
notices labelled with its name, in one list and one count (AC17.3), and
nothing from a school they are not linked to (AC17.2). Admins edit (a
system notice's text never changes), pin and archive (final), all audited;
teachers and others cannot post. The Notice board switch off hides a
school's notices and its routes answer 404. All data is fictional.
"""

import uuid
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tests.auth_support import logged_in, make_login
from app.tests.domains.test_publication import app, as_, code_of, fast_hashing, gmc, send
from app.tests.factories import (
    create_arm,
    create_class,
    create_guardian,
    create_school,
    create_session,
    create_student,
    create_term,
    enrol,
    link_ward,
    parent_accepts_link,
)

__all__ = ["app", "fast_hashing", "gmc"]


def jss2_parent(db: Session, gmc: dict[str, Any]) -> uuid.UUID:
    """Mrs. Bisi Lawal, whose son is in JSS 2A at GMC."""
    year = db.scalar(text("select session_id from terms where id = :t"), {"t": gmc["term"]})
    arm = create_arm(
        db, gmc["school"], create_class(db, gmc["school"], "junior_secondary", "JSS 2"), "A"
    )
    pupil = create_student(db, gmc["school"], "GMC/2025/101", "Lawal", "Tobi")
    enrol(db, gmc["school"], pupil, year, arm)
    bisi = make_login(
        db, username="bisi.lawal", full_name="Bisi Lawal", school_id=gmc["school"], role="parent"
    )
    link_ward(
        db, gmc["school"], create_guardian(db, gmc["school"], "Bisi Lawal", user_id=bisi), pupil
    )
    return bisi


def jss1(db: Session, gmc: dict[str, Any]) -> str:
    return str(
        db.scalar(text("select class_id from class_arms where id = :a"), {"a": gmc["arm_a"]})
    )


def post(client: Any, **body: Any) -> tuple[int, Any]:
    body.setdefault("title", "Inter-house sports")
    body.setdefault("body", "Inter-house sports holds on Friday, 14 November.")
    return send(client, "POST", "/school/notices", body)


def titles(client: Any) -> list[str]:
    status, body = send(client, "GET", "/notices")
    assert status == 200, body
    return [n["title"] for n in body["notices"]]


def test_a_notice_reaches_only_its_audience(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    jss2_parent(db_session, gmc)
    ngozi = as_(app, "ngozi.okeke")
    status, made = post(
        ngozi,
        title="JSS 1 parents' meeting",
        audience={"roles": ["parent"], "class_ids": [jss1(db_session, gmc)]},
    )
    assert status == 201, made
    assert (made["kind"], made["status"], made["recipients"]) == ("manual", "published", 2)
    assert titles(as_(app, "ikenna.obi")) == ["JSS 1 parents' meeting"]  # Chukwuemeka, JSS 1A
    assert titles(as_(app, "ada.eze")) == ["JSS 1 parents' meeting"]  # Kosi, JSS 1B
    assert titles(as_(app, "bisi.lawal")) == []  # AC17.1: a JSS 2 parent
    assert titles(as_(app, "tunde.adebayo")) == []  # parents only
    pupil = logged_in(app, "chukwuemeka.obi", school_code="GMC")
    assert titles(pupil) == []

    status, made = post(ngozi, title="Staff briefing", audience={"roles": ["teacher", "reviewer"]})
    assert (status, made["recipients"]) == (201, 4)  # Tunde, Amina, Grace, Emeka
    assert titles(as_(app, "emeka.nwosu")) == ["Staff briefing"]
    assert titles(as_(app, "ikenna.obi")) == ["JSS 1 parents' meeting"]

    # A class with no role: its pupils, their parents and the class's teachers.
    _, made = post(ngozi, title="JSS 1 trip", audience={"class_ids": [jss1(db_session, gmc)]})
    # Chukwuemeka's own login, the two parents, Tunde, Amina and Grace, and Emeka
    # (his Sciences scope covers JSS 1 Mathematics).
    assert made["recipients"] == 7
    assert "JSS 1 trip" in titles(pupil) and "JSS 1 trip" in titles(as_(app, "grace.etim"))
    assert "JSS 1 trip" not in titles(as_(app, "bisi.lawal"))


def test_everyone_pinned_first_and_people_who_join_later(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    post(ngozi, title="Older news", audience={"everyone": True})
    post(ngozi, title="Pinned for everyone", audience={"everyone": True}, pinned=True)
    post(ngozi, title="Newest news", audience={"everyone": True})
    # The setup moves two notices back in time, as a school admin (the database asks who).
    db_session.execute(
        text("select set_config('app.user_id', :u, true), set_config('app.school_id', :s, true)"),
        {"u": str(gmc["ngozi"]), "s": str(gmc["school"])},
    )
    db_session.execute(
        text(
            "update notices set created_at = created_at - interval '1 hour'"
            " where title = 'Older news'"
        )
    )
    db_session.execute(
        text(
            "update notices set created_at = created_at - interval '2 hours'"
            " where title = 'Pinned for everyone'"
        )
    )
    assert titles(as_(app, "ikenna.obi")) == ["Pinned for everyone", "Newest news", "Older news"]
    assert titles(ngozi)[0] == "Pinned for everyone"  # the poster is one of everyone

    # Someone who joins later sees the pinned notice for everyone, and nothing else.
    make_login(
        db_session,
        username="new.teacher",
        full_name="Kemi Ade",
        school_id=gmc["school"],
        role="teacher",
    )
    assert titles(as_(app, "new.teacher")) == ["Pinned for everyone"]


def test_unread_counts_and_read_marks(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi, ikenna = as_(app, "ngozi.okeke"), as_(app, "ikenna.obi")
    first = post(ngozi, title="First", audience={"everyone": True})[1]
    post(ngozi, title="Second", audience={"everyone": True})
    assert send(ikenna, "GET", "/notices/unread-count")[1] == {"unread": 2}
    assert send(ikenna, "POST", f"/notices/{first['id']}/read")[0] == 204
    assert send(ikenna, "POST", f"/notices/{first['id']}/read")[0] == 204  # twice is fine
    assert send(ikenna, "GET", "/notices/unread-count")[1] == {"unread": 1}
    read = {n["title"]: n["read"] for n in send(ikenna, "GET", "/notices")[1]["notices"]}
    assert read == {"First": True, "Second": False}
    parents_only = post(ngozi, title="Parents only", audience={"roles": ["parent"]})[1]
    assert send(as_(app, "tunde.adebayo"), "POST", f"/notices/{parents_only['id']}/read")[0] == 404
    assert send(ikenna, "POST", f"/notices/{uuid.uuid4()}/read")[0] == 404


def test_parents_see_each_linked_schools_notices(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    s = db_session
    bsa = create_school(s, code="BSA", name="Bright Star Academy")
    year = create_session(s, bsa)
    create_term(s, bsa, year, 1, is_active=True)
    arm = create_arm(s, bsa, create_class(s, bsa, "junior_secondary", "JSS 2"), "B")
    tobi = create_student(s, bsa, "BSA/2025/031", "Obi", "Tobenna")
    enrol(s, bsa, tobi, year, arm)
    parent_accepts_link(s, gmc["ikenna"], bsa)
    link_ward(s, bsa, create_guardian(s, bsa, "Ikenna Obi", user_id=gmc["ikenna"]), tobi)
    make_login(
        s,
        username="bsa.head",
        full_name="Femi Bello",
        school_id=bsa,
        role="school_admin",
        is_primary=True,
    )
    make_login(
        s,
        username="third.school",
        full_name="Uche Eze",
        school_id=create_school(s, code="RCS", name="Royal Crest Schools"),
        role="school_admin",
        is_primary=True,
    )

    post(as_(app, "ngozi.okeke"), title="GMC sports day", audience={"everyone": True})
    bsa_notice = post(as_(app, "bsa.head"), title="BSA open day", audience={"roles": ["parent"]})[1]
    post(as_(app, "third.school"), title="RCS news", audience={"everyone": True})

    ikenna = as_(app, "ikenna.obi")
    status, board = send(ikenna, "GET", "/notices")
    assert status == 200
    assert sorted((n["school_code"], n["school_name"], n["title"]) for n in board["notices"]) == [
        ("BSA", "Bright Star Academy", "BSA open day"),
        ("GMC", "Greenfield Model College", "GMC sports day"),
    ]  # AC17.3; nothing from RCS
    assert send(ikenna, "GET", "/notices/unread-count")[1] == {"unread": 2}
    # Marked read from either school's context.
    assert send(ikenna, "POST", f"/notices/{bsa_notice['id']}/read")[0] == 204
    assert send(ikenna, "GET", "/notices/unread-count")[1] == {"unread": 1}
    # AC17.2: other schools' people never see GMC's notice.
    assert titles(as_(app, "bsa.head")) == []
    assert titles(as_(app, "third.school")) == ["RCS news"]

    # A paused link to a school hides that school's notices.
    s.execute(
        text(
            "update school_memberships set status = 'paused' where user_id = :u and school_id = :s"
        ),
        {"u": gmc["ikenna"], "s": bsa},
    )
    assert titles(ikenna) == ["GMC sports day"]
    s.execute(
        text(
            "update school_memberships set status = 'active' where user_id = :u and school_id = :s"
        ),
        {"u": gmc["ikenna"], "s": bsa},
    )
    assert len(titles(ikenna)) == 2

    # A school with its Notice board off is left out.
    s.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :s and feature = 'notice_board'"
        ),
        {"s": bsa},
    )
    assert titles(ikenna) == ["GMC sports day"]


def test_only_school_admins_post_edit_and_archive(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    for username in ("tunde.adebayo", "emeka.nwosu", "ikenna.obi"):
        assert code_of(post(as_(app, username), audience={"everyone": True})) == (
            403,
            "permission_denied",
        )
    assert code_of(post(ngozi, audience={})) == (422, "no_audience")
    assert post(ngozi, audience={"roles": ["janitor"]})[0] == 422
    assert post(ngozi, audience={"everyone": True}, title=" ")[0] == 422
    assert post(ngozi, audience={"everyone": True}, body="x" * 5001)[0] == 422
    assert post(ngozi, audience={"class_ids": [str(uuid.uuid4())]})[0] == 404
    assert code_of(post(ngozi, audience={"everyone": True, "roles": ["parent"]})) == (
        422,
        "no_audience",
    )

    # A paused member is not told (Ada's link to GMC is paused).
    db_session.execute(
        text("update school_memberships set status = 'paused' where user_id = :u"),
        {"u": gmc["ada"]},
    )
    made = post(ngozi, title="Sports day", audience={"everyone": True}, body="<b>Friday</b>")[1]
    assert made["body"] == "<b>Friday</b>"  # plain text, shown as typed (D-086)
    url = f"/school/notices/{made['id']}"
    status, edited = send(ngozi, "PATCH", url, {"title": "Sports day moved", "pinned": True})
    assert (status, edited["title"], edited["pinned"]) == (200, "Sports day moved", True)
    assert send(as_(app, "tunde.adebayo"), "PATCH", url, {"title": "Mine now"})[0] == 403
    assert titles(as_(app, "ikenna.obi")) == ["Sports day moved"]

    # A system notice (from publishing) can be pinned, never reworded.
    system = db_session.scalar(
        text(
            "insert into notices (school_id, title, body, kind)"
            " values (:s, 'Results', 'Out now.', 'system') returning id"
        ),
        {"s": gmc["school"]},
    )
    assert code_of(send(ngozi, "PATCH", f"/school/notices/{system}", {"title": "Changed"})) == (
        409,
        "system_notice",
    )
    assert send(ngozi, "PATCH", f"/school/notices/{system}", {"pinned": True})[0] == 200

    assert send(ngozi, "POST", f"{url}/archive")[0] == 200
    assert titles(as_(app, "ikenna.obi")) == []
    assert code_of(send(ngozi, "POST", f"{url}/archive")) == (409, "wrong_status")
    assert code_of(send(ngozi, "PATCH", url, {"title": "Back"})) == (409, "wrong_status")
    status, listing = send(ngozi, "GET", "/school/notices")
    assert status == 200
    sports = next(n for n in listing["notices"] if n["id"] == made["id"])
    assert (sports["status"], sports["recipients"], sports["reads"]) == ("archived", 7, 0)
    assert send(as_(app, "tunde.adebayo"), "GET", "/school/notices")[0] == 403
    actions = set(
        db_session.scalars(text("select action from audit_events where action like 'notices.%'"))
    )
    assert actions == {"notices.post", "notices.edit", "notices.archive"}

    db_session.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :s and feature = 'notice_board'"
        ),
        {"s": gmc["school"]},
    )
    assert code_of(send(ngozi, "GET", "/school/notices")) == (404, "feature_disabled")
    assert send(as_(app, "ikenna.obi"), "GET", "/notices")[1]["notices"] == []
