"""Shared route dependencies: the database session and the rate limiter.

A FastAPI "dependency" is a function a route asks for in its signature; FastAPI
runs it for each request and passes the result in (a little like WordPress
handing `$wpdb` to every plugin, but per request and easy to swap in tests).

Routes take the session as `DbSession`: one transaction per request, committed
before the response is sent (scope="function", FastAPI docs checked
2026-10-15), so a rule PostgreSQL checks at commit still becomes a proper
error response; rolled back on any error. Who the database works for is set
by the auth dependencies with `use_context()` (9.2b and 9.2c).
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from schoolflow_api.core.ratelimit import RateLimiter
from schoolflow_api.db import make_engine
from schoolflow_api.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    """The app's connection pool (role app_user, D-026), made on first use."""
    return make_engine(get_settings().database_url.get_secret_value())


def get_db() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db, scope="function")]


def get_rate_limiter() -> RateLimiter:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    return RateLimiter.for_engine(get_engine(), secret)
