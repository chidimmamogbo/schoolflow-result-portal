"""The super admin's database session (D-051).

/platform routes check who is asking with the normal chain (app_user reads
the session cookie), then do their work through a second connection logged
in as app_platform: it sees schools, school admins, billing and logs, and
cannot read pupils' scores or report contents. Like WordPress's network
admin, but with its own, narrower database login.
"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import PrincipalDep
from app.core.errors import ProblemError
from app.db.session import make_engine, use_context


@lru_cache
def get_platform_engine() -> Engine:
    url = get_settings().database_url_platform
    if url is None:
        raise ProblemError(503, "Service unavailable", "The platform database is not set up.")
    return make_engine(url.get_secret_value())


def get_platform_db() -> Iterator[Session]:
    session = Session(get_platform_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def platform_db(
    principal: PrincipalDep,
    session: Annotated[Session, Depends(get_platform_db, scope="function")],
) -> Session:
    """The platform session, working for the signed-in super admin."""
    if not principal.is_super_admin:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")
    use_context(session, user_id=principal.user_id)
    return session


PlatformDb = Annotated[Session, Depends(platform_db)]
