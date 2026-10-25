"""The attention routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import DbSession, Principal, require
from app.src.attention import services
from app.src.attention.schemas import AttentionList, View
from app.src.attention.services import Ids
from app.src.schools.models import Feature

router = APIRouter(prefix="/attention", tags=["students needing attention"])

Viewers = Annotated[Principal, Depends(require("attention.view", feature=Feature.RESULTS))]


@router.get("", response_model=AttentionList)
def get_attention(
    who: Viewers,
    session: DbSession,
    view: View = "by_subject",
    term_id: Ids = None,
    session_id: Ids = None,
    class_id: Ids = None,
    arm_id: Ids = None,
    subject_id: Ids = None,
    learning_area_id: Ids = None,
    teacher_id: Ids = None,
) -> AttentionList:
    return services.get_attention(
        who=who,
        session=session,
        view=view,
        term_id=term_id,
        session_id=session_id,
        class_id=class_id,
        arm_id=arm_id,
        subject_id=subject_id,
        learning_area_id=learning_area_id,
        teacher_id=teacher_id,
    )


@router.get("/export.csv")
def export_attention(
    who: Viewers,
    session: DbSession,
    view: View = "by_subject",
    term_id: Ids = None,
    session_id: Ids = None,
    class_id: Ids = None,
    arm_id: Ids = None,
    subject_id: Ids = None,
    learning_area_id: Ids = None,
    teacher_id: Ids = None,
) -> Response:
    return services.export_attention(
        who=who,
        session=session,
        view=view,
        term_id=term_id,
        session_id=session_id,
        class_id=class_id,
        arm_id=arm_id,
        subject_id=subject_id,
        learning_area_id=learning_area_id,
        teacher_id=teacher_id,
    )
