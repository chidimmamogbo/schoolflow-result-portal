"""The parent of every table class and the shared column helpers (D-017, D-028).

Every domain's models.py builds on these: Base (with predictable constraint
names for migrations), the random UUID id, created_at and updated_at, and
one_of() for CHECK rules on a fixed list of values.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, MetaData, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
    # Python str columns become PostgreSQL text (no fixed length); lengths and
    # formats are checked by CHECK rules and the API's Pydantic schemas.
    # (SQLAlchemy reads this class attribute by name, as its docs show.)
    type_annotation_map = {str: Text()}  # noqa: RUF012


class IdMixin:
    """A random UUID primary key, made by PostgreSQL (D-028): ids cannot be guessed."""

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        sort_order=-1,  # first column in the table, before the model's own columns
    )


class TimestampMixin:
    """created_at and updated_at; a database trigger keeps updated_at current."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def one_of(column: str, allowed: Iterable[StrEnum]) -> str:
    """SQL for a CHECK rule: the column must hold one of these values."""
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} in ({values})"
