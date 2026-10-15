"""JSON logs with redaction (D-021, D-124).

Every log line is one JSON object on standard output (Vercel collects it):
time, level, logger, message, request ID and any extra `fields`. Before a
line is written, values under sensitive keys (passwords, tokens, cookies,
emails, names, scores) become "[redacted]" and email addresses inside text
become "[email]". Exceptions are logged by type and stack only, never by
their message, which can contain data.
"""

import json
import logging
import re
import sys
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, cast

# The current request's ID, set by the request middleware.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

SENSITIVE_KEY = re.compile(
    r"password|token|secret|cookie|authorization|csrf|session|email|phone|full_name"
    r"|first_name|surname|other_names|^name$|score|grade|position|average|total",
    re.IGNORECASE,
)
EMAIL = re.compile(r"[^@\s\"']+@[^@\s\"']+\.[^@\s\"']+")
REDACTED = "[redacted]"


def redact(value: Any, key: str = "") -> Any:
    """A copy of the value that is safe to log."""
    if key and SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, dict):
        items = cast(dict[object, object], value).items()
        return {str(k): redact(v, str(k)) for k, v in items}
    if isinstance(value, list | tuple):
        return [redact(item) for item in cast(list[object], value)]
    if isinstance(value, str):
        return EMAIL.sub("[email]", value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            line.update(redact(fields))
        if record.exc_info and record.exc_info[0] is not None:
            line["exception"] = record.exc_info[0].__name__
            line["stack"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(line, default=str)


_configured = False


def configure_logging() -> None:
    """Send the app's logs to standard output as JSON, once."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("schoolflow")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _configured = True
