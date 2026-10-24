"""The rate limit counters (D-021, D-042; migration 19).

One row per keyed hash ("login:ip:..." after HMAC): when the current window
started and how many hits it has had. No app role can read or write the
table; they call the owner-run function rate_limit_hit() instead.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, LargeBinary, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.permissions import Role
from app.db.base import Base, one_of


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        CheckConstraint("octet_length(key_hash) = 32", name="key_hash_length"),
        CheckConstraint("hits >= 1", name="hits_positive"),
    )

    key_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hits: Mapped[int]


# --- authz_models ------------------------------------------------------------
# Tables that hold the permission matrix (D-046).
#
# The app checks permissions from app/authz/permissions.py; these
# tables keep the same matrix inside the database (seeded by migration 5) so
# it can be read in SQL and audited. The app's database roles may read them
# and never change them; a change always comes through a reviewed migration.


class RoleRecord(Base):
    __tablename__ = "roles"
    __table_args__ = (CheckConstraint(one_of("key", Role), name="key_allowed"),)

    key: Mapped[str] = mapped_column(primary_key=True)


class PermissionRecord(Base):
    __tablename__ = "permissions"
    __table_args__ = (CheckConstraint(r"key ~ '^[a-z_]+\.[a-z_]+$'", name="key_format"),)

    key: Mapped[str] = mapped_column(primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        CheckConstraint(
            "NOT primary_only OR role_key = 'school_admin'", name="primary_only_for_school_admins"
        ),
    )

    role_key: Mapped[str] = mapped_column(ForeignKey("roles.key"), primary_key=True)
    permission_key: Mapped[str] = mapped_column(ForeignKey("permissions.key"), primary_key=True)
    # True when only the principal (school_admin with is_primary) has it.
    primary_only: Mapped[bool] = mapped_column(server_default=text("false"))
