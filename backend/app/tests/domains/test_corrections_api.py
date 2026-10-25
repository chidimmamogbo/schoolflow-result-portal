"""The correction queue (BUILD_PROMPT 9.2n; SPEC F15, section 8; AC15.1; D-151, D-174).

Behaviour: when the school's Correction queue is on, a parent reports a
problem on their own child's Valid report, and staff on reports of classes
they teach, assist in or review; pupils cannot. Each request is numbered
(CR-0001), names the subject or learning area on the report, an issue type
and an explanation, and may carry one checked attachment (an image, or a
PDF without scripts, up to 4 MB) while it is open. The requester and school
admins see it; nobody else does. School admins move it through section 8
(investigating, needs more information, resolved, rejected; messages where
required); only the requester answers "needs more information". When a
reopen named the request and the pupil's corrected report is republished,
the request links that new revision and shows old against new (AC15.1).
The requester is emailed on each step, never with scores. All data is
fictional.
"""

import io
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.storage import LocalFileStorage, get_file_storage
from app.tests.auth_support import csrf, logged_in
from app.tests.domains.test_publication import app, as_, code_of, fast_hashing, gmc, send
from app.tests.domains.test_republishing import publish_a, sheet_of

__all__ = ["app", "fast_hashing", "gmc"]

WHY = "His Mathematics exam script shows 51, not 47."


@pytest.fixture(autouse=True)
def queue_on(db_session: Session, gmc: dict[str, Any], app: FastAPI, tmp_path: Any) -> None:
    db_session.execute(
        text(
            "update school_features set enabled = true"
            " where school_id = :s and feature = 'correction_queue'"
        ),
        {"s": gmc["school"]},
    )
    app.dependency_overrides[get_file_storage] = lambda: LocalFileStorage(tmp_path)


def report_of(db: Session, admission: str) -> str:
    return str(
        db.scalar(
            text(
                "select d.id from report_documents d join enrolments e on e.id = d.enrolment_id"
                " join students p on p.id = e.student_id where p.admission_number = :a"
                " and d.status = 'valid'"
            ),
            {"a": admission},
        )
    )


def ask(client: Any, report_id: str, subject: str | None, **more: Any) -> tuple[int, Any]:
    body = {"report_id": report_id, "issue_type": "score", "explanation": WHY, **more}
    if subject is not None:
        body["subject_id"] = subject
    return send(client, "POST", "/corrections", body)


def move(client: Any, request_id: str, status: str, message: str | None = None) -> tuple[int, Any]:
    body: dict[str, Any] = {"status": status}
    if message is not None:
        body["message"] = message
    return send(client, "POST", f"/corrections/{request_id}/move", body)


def png(size: tuple[int, int] = (40, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(out, format="PNG")
    return out.getvalue()


def attach(client: Any, request_id: str, name: str, data: bytes, kind: str) -> tuple[int, Any]:
    response = client.post(
        f"/api/v1/corrections/{request_id}/attachment",
        files={"file": (name, data, kind)},
        headers=csrf(client),
    )
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def test_a_parent_reports_a_problem_on_their_childs_report(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    chuk, musa = report_of(db_session, "GMC/2026/014"), report_of(db_session, "GMC/2026/015")
    maths = str(gmc["maths"])
    ikenna = as_(app, "ikenna.obi")

    status, made = ask(ikenna, chuk, maths)
    assert status == 201, made
    assert (made["number"], made["status"], made["subject"], made["student_name"]) == (
        "CR-0001",
        "open",
        "Mathematics",
        "Chukwuemeka Obi",
    )
    assert (made["report_code"], made["revision"], made["issue_type"]) == (
        "GMC-2627-T1-JSS1A-014",
        1,
        "score",
    )

    # Only their own child, a subject on the report, a known issue, a real explanation.
    assert send(ikenna, "POST", "/corrections", {"report_id": musa, "issue_type": "score",
                                                 "explanation": WHY})[0] == 404  # fmt: skip
    assert send(as_(app, "ada.eze"), "POST", "/corrections", {"report_id": chuk,
                "issue_type": "score", "explanation": WHY})[0] == 404  # fmt: skip
    assert code_of(ask(ikenna, chuk, str(uuid.uuid4()))) == (422, "not_on_report")
    assert ask(ikenna, chuk, maths, issue_type="grade")[0] == 422
    assert ask(ikenna, chuk, maths, explanation=" ")[0] == 422
    assert ask(ikenna, chuk, maths, explanation="x" * 1001)[0] == 422
    pupil = logged_in(app, "chukwuemeka.obi", school_code="GMC")
    assert code_of(ask(pupil, chuk, maths)) == (403, "permission_denied")
    whole = ask(ikenna, chuk, None, issue_type="detail", explanation="His surname is Obi.")
    assert (whole[0], whole[1]["subject"], whole[1]["number"]) == (201, None, "CR-0002")

    # Who sees what.
    assert [r["number"] for r in send(ikenna, "GET", "/corrections")[1]["requests"]] == [
        "CR-0002",
        "CR-0001",
    ]
    status, everyone = send(as_(app, "ngozi.okeke"), "GET", "/corrections")
    assert (status, everyone["open"], len(everyone["requests"])) == (200, 2, 2)
    assert send(as_(app, "ada.eze"), "GET", "/corrections")[1]["requests"] == []
    assert send(ikenna, "GET", f"/corrections/{made['id']}")[0] == 200
    for other in ("ada.eze", "tunde.adebayo", "amina.bello"):
        assert send(as_(app, other), "GET", f"/corrections/{made['id']}")[0] == 404

    # A revoked report takes no new requests; the queue switched off answers 404.
    revoke = {"reason": "Issued in error."}
    assert send(as_(app, "ngozi.okeke"), "POST", f"/school/reports/{chuk}/revoke", revoke)[0] == 200
    assert code_of(ask(ikenna, chuk, maths)) == (409, "report_not_valid")
    db_session.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :s and feature = 'correction_queue'"
        ),
        {"s": gmc["school"]},
    )
    assert code_of(send(ikenna, "GET", "/corrections")) == (404, "feature_disabled")


def test_staff_report_problems_in_their_own_classes(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    chuk, maths = report_of(db_session, "GMC/2026/014"), str(gmc["maths"])
    for username in ("tunde.adebayo", "amina.bello", "emeka.nwosu", "ngozi.okeke"):
        assert ask(as_(app, username), chuk, maths)[0] == 201, username
    assert ask(as_(app, "grace.etim"), chuk, maths)[0] == 404  # teaches JSS 1B only
    tunde = as_(app, "tunde.adebayo")
    assert [r["requested_by"] for r in send(tunde, "GET", "/corrections")[1]["requests"]] == [
        "Tunde Adebayo"
    ]


def edit_chuk_maths(app: FastAPI, db: Session, gmc: dict[str, Any], exam: int) -> None:
    tunde = as_(app, "tunde.adebayo")
    sheet = sheet_of(db, gmc, "maths")
    _, view = send(tunde, "GET", f"/sheets/{sheet}")
    cell = {
        "enrolment_id": str(gmc["pupils"]["Chukwuemeka"]),
        "component_id": view["columns"][-1]["id"],
        "value": exam,
    }
    body = {"scores": [cell], "reason": "Exam script re-checked."}
    assert send(tunde, "PUT", f"/sheets/{sheet}/scores", body)[0] == 200
    assert send(tunde, "POST", f"/sheets/{sheet}/submit")[0] == 200
    assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{sheet}/review")[0] == 200
    assert send(as_(app, "ngozi.okeke"), "POST", f"/sheets/{sheet}/approve")[0] == 200


def test_the_school_works_through_a_request_to_a_corrected_report(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    chuk = report_of(db_session, "GMC/2026/014")
    ikenna, ngozi = as_(app, "ikenna.obi"), as_(app, "ngozi.okeke")
    request_id = ask(ikenna, chuk, str(gmc["maths"]))[1]["id"]

    # Only school admins move a request; the steps follow section 8.
    assert code_of(move(ikenna, request_id, "investigating")) == (403, "permission_denied")
    assert code_of(move(ngozi, request_id, "resolved", "Done.")) == (409, "wrong_status")
    assert move(ngozi, request_id, "investigating")[0] == 200
    assert code_of(move(ngozi, request_id, "needs_more_information")) == (422, "message_required")
    asked = "Please send a photo of the marked script."
    assert move(ngozi, request_id, "needs_more_information", asked)[0] == 200
    # Only the requester answers, with a message.
    assert code_of(move(ngozi, request_id, "investigating", "Reply.")) == (403, "requester_replies")
    assert code_of(move(ikenna, request_id, "investigating")) == (422, "message_required")
    assert move(ikenna, request_id, "investigating", "The photo is attached.")[0] == 200

    # The school reopens Mathematics naming the request, fixes the score and republishes.
    reopen = {
        "reason": "Exam script re-checked: 51, not 47. Raised in CR-0001.",
        "sheet_ids": [str(sheet_of(db_session, gmc, "maths"))],
        "correction_request_id": request_id,
    }
    assert send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/reopen", reopen)[0] == 200
    edit_chuk_maths(app, db_session, gmc, 51)
    published = send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    assert published[0] == 200, published

    # AC15.1: the request shows the linked revision, and old against new.
    status, seen = send(ikenna, "GET", f"/corrections/{request_id}")
    assert status == 200
    fixed = seen["corrected_report"]
    assert (fixed["report_code"], fixed["revision"], fixed["status"]) == (
        "GMC-2627-T1-JSS1A-014",
        2,
        "valid",
    )
    assert seen["change"]["subject"] == {"name": "Mathematics", "before": 78, "after": 82}
    assert seen["change"]["average"]["before"] != seen["change"]["average"]["after"]

    done = "The script was re-checked and the score is now correct."
    assert move(ngozi, request_id, "resolved", done)[0] == 200
    _, seen = send(ikenna, "GET", f"/corrections/{request_id}")
    assert seen["status"] == "resolved"
    assert [(e["to_status"], e["message"]) for e in seen["events"]] == [
        ("open", None),
        ("investigating", None),
        ("needs_more_information", asked),
        ("investigating", "The photo is attached."),
        ("resolved", done),
    ]
    assert seen["events"][1]["actor_name"] == "Ngozi Okeke"
    assert code_of(move(ngozi, request_id, "investigating")) == (409, "wrong_status")

    # The parent is emailed at each step, without scores.
    emails = list(
        db_session.execute(
            text(
                "select to_address, template_data from email_outbox"
                " where template = 'correction_updated' order by created_at"
            )
        )
    )
    assert emails and {e.to_address for e in emails} == {"ikenna@home.example"}
    for email in emails:
        assert {"78", "82", "51", "47"}.isdisjoint(str(email.template_data).split())
        assert email.template_data["number"] == "CR-0001"
        # Only these fields: the school's message may quote scores, so it is never sent.
        assert set(email.template_data) == {
            "full_name", "school_name", "number", "status", "login_path",
        }  # fmt: skip


def test_a_request_can_be_rejected_with_a_reason(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    request_id = ask(as_(app, "ikenna.obi"), report_of(db_session, "GMC/2026/014"), None)[1]["id"]
    move(ngozi, request_id, "investigating")
    assert code_of(move(ngozi, request_id, "rejected")) == (422, "message_required")
    assert move(ngozi, request_id, "rejected", "The positions were correct.")[0] == 200
    assert code_of(move(ngozi, request_id, "investigating")) == (409, "wrong_status")
    assert send(ngozi, "GET", "/corrections?status=rejected")[1]["requests"][0]["id"] == request_id
    assert send(ngozi, "GET", "/corrections?status=open")[1]["requests"] == []


def test_one_checked_attachment_while_the_request_is_open(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    ikenna, ngozi = as_(app, "ikenna.obi"), as_(app, "ngozi.okeke")
    request_id = ask(ikenna, report_of(db_session, "GMC/2026/014"), str(gmc["maths"]))[1]["id"]

    assert code_of(attach(ikenna, request_id, "notes.txt", b"hello", "text/plain")) == (
        415,
        "unsupported_file",
    )
    scripted = (
        b"%PDF-1.7\n1 0 obj << /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>\n%%EOF\n"
    )
    assert code_of(attach(ikenna, request_id, "script.pdf", scripted, "application/pdf")) == (
        415,
        "unsafe_pdf",
    )
    big = b"%PDF-1.7\n" + b"0" * (4 * 1024 * 1024) + b"\n%%EOF\n"
    assert code_of(attach(ikenna, request_id, "big.pdf", big, "application/pdf")) == (
        413,
        "file_too_large",
    )
    assert send(as_(app, "ada.eze"), "GET", f"/corrections/{request_id}")[0] == 404
    assert attach(as_(app, "ada.eze"), request_id, "x.png", png(), "image/png")[0] == 404
    assert code_of(attach(ngozi, request_id, "x.png", png(), "image/png")) == (
        403,
        "requester_attaches",
    )

    status, made = attach(ikenna, request_id, "script photo.png", png(), "image/png")
    assert (status, made["content_type"], made["original_name"]) == (
        201,
        "image/png",
        "script photo.png",
    )
    assert code_of(attach(ikenna, request_id, "again.png", png(), "image/png")) == (
        409,
        "already_attached",
    )
    _, seen = send(ngozi, "GET", f"/corrections/{request_id}")
    assert seen["attachment"]["content_type"] == "image/png"

    download = ngozi.get(f"/api/v1/corrections/{request_id}/attachment")
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.content.startswith(b"\x89PNG")
    assert (
        as_(app, "ada.eze").get(f"/api/v1/corrections/{request_id}/attachment").status_code == 404
    )

    # A plain PDF is accepted on another request; nothing is added once it is closed.
    other = ask(ikenna, report_of(db_session, "GMC/2026/014"), None)[1]["id"]
    plain = b"%PDF-1.7\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    assert attach(ikenna, other, "letter.pdf", plain, "application/pdf")[0] == 201
    third = ask(ikenna, report_of(db_session, "GMC/2026/014"), None)[1]["id"]
    move(ngozi, third, "investigating")
    move(ngozi, third, "rejected", "Nothing to change.")
    assert code_of(attach(ikenna, third, "late.png", png(), "image/png")) == (409, "wrong_status")
