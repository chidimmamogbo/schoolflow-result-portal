"""Database connection (SQLAlchemy 2 + psycopg 3, decision D-017).

An "engine" is SQLAlchemy's connection pool: like WordPress's global $wpdb,
it is created once and reused, but it hands out connections from a pool
instead of opening a new one for every query. Sessions (one per request, or
one per test) borrow a connection from it.
"""

import uuid

from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.orm import Session, SessionTransaction


def make_engine(url: str) -> Engine:
    return create_engine(
        url,
        # Checks a pooled connection still works before using it (Neon closes
        # idle connections when it scales to zero).
        pool_pre_ping=True,
        # Keeps SQL parameter values (passwords, tokens, scores) out of error
        # messages, and so out of logs and Sentry (D-021).
        hide_parameters=True,
    )


# --- Who the database is working for (D-027, D-051, D-137) ---------------------
#
# Row-level security rules in PostgreSQL read two settings: app.school_id (the
# school this request works for) and app.user_id (the signed-in person). They
# are set inside every transaction with set_config(..., true), so they vanish
# when the transaction ends and can never leak to the next request that reuses
# the same pooled connection.

_CONTEXT_KEY = "schoolflow_context"
_SET_CONTEXT = text(
    "select set_config('app.school_id', :school_id, true),"
    " set_config('app.user_id', :user_id, true)"
)


def use_context(
    session: Session,
    *,
    school_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    """Tell the database which school and user this session works for.

    Both values must come from the signed-in session, never from the URL or
    the request body (D-051). They apply to the current transaction and to
    every later transaction of this session. Call with no values to clear them.
    """
    session.info[_CONTEXT_KEY] = (school_id, user_id)
    if session.in_transaction():
        _apply_context(session.connection(), school_id, user_id)


def _apply_context(
    connection: Connection, school_id: uuid.UUID | None, user_id: uuid.UUID | None
) -> None:
    connection.execute(
        _SET_CONTEXT,
        {
            "school_id": str(school_id) if school_id else "",
            "user_id": str(user_id) if user_id else "",
        },
    )


def _set_context_when_a_transaction_begins(
    session: Session, transaction: SessionTransaction, connection: Connection
) -> None:
    # Runs at the start of every transaction, so a transaction without a
    # context always starts empty, whatever a reused connection held before.
    school_id, user_id = session.info.get(_CONTEXT_KEY, (None, None))
    _apply_context(connection, school_id, user_id)


# For every session in the app (SQLAlchemy 2.1 "after_begin" event, docs checked 2026-10-12).
event.listen(Session, "after_begin", _set_context_when_a_transaction_begins)
