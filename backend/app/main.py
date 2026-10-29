"""The FastAPI application: the one object every request goes through.

Uvicorn (locally) and Vercel (in production) both start the server by
importing `app` from this module. `create_app()` builds it; tests call it
with the environment they want to check.
"""

from fastapi import APIRouter, FastAPI
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logs import configure_logging
from app.core.middleware import add_request_middleware
from app.src.accounts import router as school_people
from app.src.attention import router as attention
from app.src.audit import router as audit
from app.src.auth import router as auth
from app.src.corrections import router as corrections
from app.src.cron import router as cron
from app.src.files import router as files
from app.src.form_class import router as form_class
from app.src.grading import router as school_grading
from app.src.guardians import router as guardians
from app.src.health import router as health
from app.src.notices import router as notices
from app.src.platform_admin import router as platform
from app.src.portal import router as portal
from app.src.publication import router as publication
from app.src.reports import router as reports
from app.src.results import router as results
from app.src.schools import router as school
from app.src.staff import router as school_staff
from app.src.structure import router as structure
from app.src.students import router as school_pupils
from app.src.verification import router as verify


def configured_env() -> str:
    """APP_ENV from the settings; without valid settings, the strictest choice."""
    try:
        return get_settings().app_env
    except ValidationError:
        return "production"


def create_app(app_env: str | None = None) -> FastAPI:
    app_env = app_env or configured_env()
    local = app_env == "local"
    configure_logging()
    # The /docs page and the API description exist only locally (D-020).
    app = FastAPI(
        title="SchoolFlow Result Portal API",
        docs_url="/api/v1/docs" if local else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if local else None,
    )
    app.state.app_env = app_env
    register_error_handlers(app)
    add_request_middleware(app)

    # Every endpoint lives under /api/v1 (decision D-015), so a future /api/v2
    # can sit beside it without breaking the frontend.
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health.router)
    api_v1.include_router(cron.router)
    api_v1.include_router(auth.router)
    api_v1.include_router(platform.router)
    api_v1.include_router(school.router)
    api_v1.include_router(structure.router)
    api_v1.include_router(school_people.router)
    api_v1.include_router(school_staff.router)
    api_v1.include_router(files.router)
    api_v1.include_router(school_pupils.router)
    api_v1.include_router(guardians.router)
    api_v1.include_router(guardians.parent_router)
    api_v1.include_router(school_grading.router)
    api_v1.include_router(results.router)
    api_v1.include_router(results.rating_router)
    api_v1.include_router(results.workflow_router)
    api_v1.include_router(form_class.router)
    api_v1.include_router(reports.templates_router)
    api_v1.include_router(publication.router)
    api_v1.include_router(attention.router)
    api_v1.include_router(audit.router)
    api_v1.include_router(reports.router)
    api_v1.include_router(portal.router)
    api_v1.include_router(verify.router)
    api_v1.include_router(corrections.router)
    api_v1.include_router(notices.router)
    api_v1.include_router(notices.school_router)
    app.include_router(api_v1)
    return app


app = create_app()
