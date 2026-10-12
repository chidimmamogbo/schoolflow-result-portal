"""Database connection (SQLAlchemy 2 + psycopg 3, decision D-017).

An "engine" is SQLAlchemy's connection pool: like WordPress's global $wpdb,
it is created once and reused, but it hands out connections from a pool
instead of opening a new one for every query. Sessions (one per request, or
one per test) borrow a connection from it.
"""

from sqlalchemy import Engine, create_engine


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
