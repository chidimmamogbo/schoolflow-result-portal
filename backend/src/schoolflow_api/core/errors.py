"""One error format for the whole API: RFC 9457 "problem details" (D-015).

Every error answers with `Content-Type: application/problem+json` and a body
like {"type": "about:blank", "title": "Not Found", "status": 404,
"request_id": "..."}, plus `detail`, a machine-readable `code` or the list of
field `errors` when they help. The frontend reads one shape everywhere.

Safety rules (MEMORY, D-021): a validation error never repeats the values
sent; a database error never returns or logs PostgreSQL's own message (it
can quote data), only the SQLSTATE code and our own rule name.
"""

import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from schoolflow_api.core.logs import request_id_var

PROBLEM_JSON = "application/problem+json"
logger = logging.getLogger("schoolflow.errors")


class ProblemError(Exception):
    """Raise from a service or route to answer with a problem."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        *,
        code: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code
        self.headers = headers


def problem_response(
    status: int,
    title: str | None = None,
    detail: str | None = None,
    *,
    code: str | None = None,
    errors: Sequence[Mapping[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title or HTTPStatus(status).phrase,
        "status": status,
        "request_id": request_id_var.get(),
    }
    if detail:
        body["detail"] = detail
    if code:
        body["code"] = code
    if errors is not None:
        body["errors"] = list(errors)
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM_JSON)


def internal_error() -> JSONResponse:
    return problem_response(
        500,
        "Something went wrong",
        "Please try again. If it keeps happening, contact support with the request ID.",
    )


async def _problem(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ProblemError):
        raise exc
    return problem_response(exc.status, exc.title, exc.detail, code=exc.code, headers=exc.headers)


async def _http(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    return problem_response(exc.status_code, headers=exc.headers)


async def _validation(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # Only where and why: never "input" or "ctx", which hold what was sent.
    errors = [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return problem_response(422, "Check the highlighted fields", errors=errors)


async def _database(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DBAPIError):
        raise exc
    original = exc.orig
    sqlstate = original.sqlstate if isinstance(original, psycopg.Error) else None
    constraint = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
    logger.warning(
        "Database refused a request",
        extra={"fields": {"sqlstate": sqlstate, "constraint": constraint}},
    )
    if isinstance(exc, OperationalError):
        return problem_response(503, "Service unavailable", "Please try again in a moment.")
    if sqlstate is not None and sqlstate.startswith("23"):
        # A rule of ours (unique, check, link or trigger rule); the name is ours, not data.
        return problem_response(
            409, "This change breaks a rule", code=constraint or "integrity_error"
        )
    if sqlstate == "42501":
        return problem_response(403)
    if sqlstate in {"40001", "40P01"}:
        return problem_response(
            409, "Please try again", "Someone else changed this at the same time."
        )
    return internal_error()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemError, _problem)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(DBAPIError, _database)
