"""Report template defaults follow the approved labels file (CHANGE 2026-10-24; D-170).

Behaviour: until a school saves its own, a Score report card hides Attendance,
shows the class average per subject, does not highlight scores below the pass
mark and leaves the number of subjects out of the summary; a Skills report
card leaves out the pupil's photo and shows ratings as words
(`design/NAVIGATION_AND_SETTINGS.md` section 3). Each template shows the
level's head's title, and saving a template can change it (audited). With
Attendance hidden, publishing does not ask for times present; shown, it does.
Every CSV export shows formula-like cells as text. All data is fictional.
"""

import csv
import io
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.test_publication import (
    app,
    approve_all,
    as_,
    fast_hashing,
    gmc,
    principal_comments,
    send,
)
from tests.test_ratings_and_workflow import rcs

__all__ = ["app", "fast_hashing", "gmc", "rcs"]


def templates(app: FastAPI, username: str) -> dict[str, Any]:
    status, body = send(as_(app, username), "GET", "/school/report-templates")
    assert status == 200
    return {t["level"]: t for t in body}


def test_score_card_defaults(app: FastAPI, gmc: dict[str, Any]) -> None:
    jss = templates(app, "ngozi.okeke")["junior_secondary"]
    settings = jss["settings"]
    assert settings["hidden"] == ["attendance"]
    assert settings["subject_table"]["class_average"] is True
    assert settings["subject_table"]["highlight_below_pass"] is False
    assert settings["summary"]["number_of_subjects"] is False
    assert jss["head_title"] == "Principal"


def test_skills_card_defaults(app: FastAPI, db_session: Session, rcs: dict[str, Any]) -> None:
    nursery = templates(app, "femi.ade")["nursery"]
    assert nursery["card"] == "skills"
    details = nursery["settings"]["student_details"]
    assert (details["photo"], details["age"]) == (False, True)
    assert nursery["settings"]["skills_table"]["rating_display"] == "words"
    assert nursery["settings"]["hidden"] == []
    assert nursery["head_title"] == db_session.scalar(
        text("select head_title from school_levels where school_id = :s and level = 'nursery'"),
        {"s": rcs["school"]},
    )


def test_saving_a_template_can_change_the_heads_title(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    jss = templates(app, "ngozi.okeke")["junior_secondary"]
    url = "/school/report-templates/junior_secondary"
    body = {"style": "modern", "head_title": "Head of school", "settings": jss["settings"]}
    assert send(ngozi, "PUT", url, {**body, "head_title": " "})[0] == 422
    status, saved = send(ngozi, "PUT", url, body)
    assert (status, saved["head_title"], saved["version"]) == (200, "Head of school", 1)
    assert templates(app, "ngozi.okeke")["junior_secondary"]["head_title"] == "Head of school"
    event = db_session.execute(
        text(
            "select old_values, new_values from audit_events where action = 'school_levels.update'"
        )
    ).one()
    assert event.old_values["head_title"] == "Principal"
    assert event.new_values["head_title"] == "Head of school"
    # Saving without a head's title keeps it.
    del body["head_title"]
    assert send(ngozi, "PUT", url, body)[1]["head_title"] == "Head of school"


def test_hidden_attendance_is_not_asked_for(app: FastAPI, gmc: dict[str, Any]) -> None:
    approve_all(app, gmc)
    tunde = as_(app, "tunde.adebayo")
    url = f"/form-class/{gmc['arm_a']}"
    ratings = {t["id"]: 4 for t in send(tunde, "GET", url)[1]["traits"]}
    for pupil in ("Chukwuemeka", "Musa", "Zainab"):
        body = {"comment": f"{pupil} worked well.", "ratings": ratings}
        assert send(tunde, "PUT", f"{url}/students/{gmc['pupils'][pupil]}/entry", body)[0] == 200
    assert send(tunde, "POST", f"{url}/sections/submit")[0] == 200
    principal_comments(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    publication = f"/school/publications/{gmc['arm_a']}"
    assert send(ngozi, "GET", publication)[1]["problems"] == []

    settings = templates(app, "ngozi.okeke")["junior_secondary"]["settings"]
    settings["hidden"] = []
    body = {"style": "modern", "settings": settings}
    assert send(ngozi, "PUT", "/school/report-templates/junior_secondary", body)[0] == 200
    assert send(ngozi, "GET", publication)[1]["problems"] == [
        "Times school opened is not set",
        "Times present is missing for 3 students",
    ]


def test_score_sheet_exports_show_formulas_as_text(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    db_session.execute(
        text("update students set surname = '=cmd|calc' where id = :s"),
        {"s": gmc["students"]["Musa"]},
    )
    tunde = as_(app, "tunde.adebayo")
    body = {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc["maths"])}
    sheet = send(tunde, "POST", "/sheets", body)[1]
    for path in ("export.csv", "template.csv"):
        response = tunde.get(f"/api/v1/sheets/{sheet['id']}/{path}")
        assert response.status_code == 200
        rows = list(csv.reader(io.StringIO(response.text)))
        surnames = [row[1] for row in rows[1:]]
        assert "'=cmd|calc" in surnames, path
        assert "=cmd|calc" not in surnames
