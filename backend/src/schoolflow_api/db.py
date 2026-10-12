"""Database connection (SQLAlchemy 2 + psycopg 3, decision D-017).

An "engine" is SQLAlchemy's connection pool: like WordPress's global $wpdb,
it is created once and reused, but it hands out connections from a pool
instead of opening a new one for every query. Sessions (one per request, or
one per test) borrow a connection from it.
"""

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase

# Every constraint and index gets a predictable name, so migrations can find
# and change them later (Alembic cannot alter a constraint it cannot name).
NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


class Base(DeclarativeBase):
    """Parent of every table class. Like registering a custom table in WordPress,
    but the table's columns and rules are written once, here in Python."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


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
