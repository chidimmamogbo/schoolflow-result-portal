"""Health checks (D-126).

/health: the app is up (no database; safe to call often, reveals nothing).
/health/ready: the app can reach the database (used after deploys).
"""

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.dependencies import DbSession
from app.core.errors import ProblemError

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(session: DbSession) -> dict[str, str]:
    try:
        session.execute(text("select 1"))
    except OperationalError as error:
        raise ProblemError(503, "Service unavailable", "The database cannot be reached.") from error
    return {"status": "ok"}
