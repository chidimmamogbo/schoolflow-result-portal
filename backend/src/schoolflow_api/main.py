"""The FastAPI application: the one object every request goes through.

Uvicorn (locally) and Vercel (in production) both start the server by
importing `app` from this module. `create_app()` builds it; tests call it
with the environment they want to check.
"""

from fastapi import APIRouter, FastAPI
from pydantic import ValidationError

from schoolflow_api.auth import routes as auth
from schoolflow_api.core import health
from schoolflow_api.core.errors import register_error_handlers
from schoolflow_api.core.logs import configure_logging
from schoolflow_api.core.middleware import add_request_middleware
from schoolflow_api.files import routes as files
from schoolflow_api.form_class import routes as form_class
from schoolflow_api.parents import routes as parents
from schoolflow_api.platform import routes as platform
from schoolflow_api.reports import publication
from schoolflow_api.reports import templates as report_templates
from schoolflow_api.results import rating_sheets
from schoolflow_api.results import sheets as result_sheets
from schoolflow_api.results import workflow as sheet_workflow
from schoolflow_api.school import grading as school_grading
from schoolflow_api.school import guardians as school_guardians
from schoolflow_api.school import people as school_people
from schoolflow_api.school import pupils as school_pupils
from schoolflow_api.school import routes as school
from schoolflow_api.school import staff as school_staff
from schoolflow_api.settings import get_settings


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
    api_v1.include_router(auth.router)
    api_v1.include_router(platform.router)
    api_v1.include_router(school.router)
    api_v1.include_router(school_people.router)
    api_v1.include_router(school_staff.router)
    api_v1.include_router(files.router)
    api_v1.include_router(school_pupils.router)
    api_v1.include_router(school_guardians.router)
    api_v1.include_router(parents.router)
    api_v1.include_router(school_grading.router)
    api_v1.include_router(result_sheets.router)
    api_v1.include_router(rating_sheets.router)
    api_v1.include_router(sheet_workflow.router)
    api_v1.include_router(form_class.router)
    api_v1.include_router(report_templates.router)
    api_v1.include_router(publication.router)
    app.include_router(api_v1)
    return app


app = create_app()
