"""Tables that hold the permission matrix (D-046).

The app checks permissions from schoolflow_api/authz/permissions.py; these
tables keep the same matrix inside the database (seeded by migration 5) so
it can be read in SQL and audited. The app's database roles may read them
and never change them; a change always comes through a reviewed migration.
"""

from sqlalchemy import CheckConstraint, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.authz.permissions import Role
from schoolflow_api.db import Base, one_of


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
