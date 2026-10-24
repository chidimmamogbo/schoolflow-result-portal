"""The permission matrix (SPEC section 5; D-045, D-046, D-047, D-052).

Behaviour: every role's permissions come from one Python file that matches
the SPEC section 5 table exactly; the database holds the same matrix (seeded
by migration 5); only the principal manages school admins; parents and pupils
never get staff powers; and the app can read permissions but never change them.

The test reads the table straight out of docs/SPEC.md, so if the spec or the
code changes without the other, this test fails.
"""

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.permissions import (
    COLUMNS,
    MATRIX,
    PRIMARY_ONLY,
    Role,
    permissions_for,
    role_permission_rows,
)
from app.src.accounts.models import MembershipRole
from app.tests.db_support import acting_as, refused

SPEC = Path(__file__).resolve().parents[4] / "docs" / "SPEC.md"  # the repo root
SPEC_COLUMNS = [
    "Super admin",
    "Principal",
    "Additional admin",
    "Reviewer/HOD",
    "Teacher",
    "Parent",
    "Student",
]


def spec_table() -> list[list[str]]:
    """The rows of the SPEC section 5 table, as lists of cell texts."""
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    start = lines.index("## 5. Permission matrix")
    rows: list[list[str]] = []
    for line in lines[start + 1 :]:
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
    return rows


def permission_names(capability: str) -> list[str]:
    """Turn a SPEC row label into permission names.

    "sheets.review / return" gives sheets.review and sheets.return: a part
    without a dot belongs to the area of the part before it. Brackets are
    explanations, and spaces become underscores ("email log" -> email_log).
    """
    names: list[str] = []
    area = ""
    for part in capability.split(" / "):
        name = re.sub(r"\s*\(.*\)$", "", part).strip().replace(" ", "_")
        if "." in name:
            area = name.split(".")[0]
            names.append(name)
        else:
            names.append(f"{area}.{name}")
    return names


def spec_matrix() -> dict[str, tuple[bool, ...]]:
    """A cell grants the permission unless it starts with "No" (scopes are checked in code)."""
    _header, _separator, *body = spec_table()
    matrix: dict[str, tuple[bool, ...]] = {}
    for capability, *cells in body:
        granted = tuple(not cell.startswith("No") for cell in cells)
        for name in permission_names(capability):
            matrix[name] = granted
    return matrix


# --- the file mirrors the spec ----------------------------------------------------


def test_the_spec_table_has_the_expected_columns() -> None:
    header = spec_table()[0]

    assert header[1:] == SPEC_COLUMNS
    assert len(COLUMNS) == len(SPEC_COLUMNS)


def test_the_permission_file_matches_spec_section_5() -> None:
    assert dict(MATRIX) == spec_matrix()


def test_permission_names_are_area_dot_action() -> None:
    bad = [name for name in MATRIX if not re.fullmatch(r"[a-z_]+\.[a-z_]+", name)]

    assert bad == []


def test_school_roles_match_membership_roles() -> None:
    assert {role.value for role in MembershipRole} == {role.value for role in Role} - {
        Role.SUPER_ADMIN.value
    }


# --- what the matrix means ------------------------------------------------------------


def test_only_the_principal_manages_school_admins() -> None:
    # D-046 and AC03.1: admin management needs school_admin plus is_primary.
    assert {
        "school_admins.create",
        "school_admins.remove",
        "school_admins.reset_login",
        "school_admins.sign_out_all",
    } == PRIMARY_ONLY
    assert permissions_for(Role.SCHOOL_ADMIN, is_primary=True) >= PRIMARY_ONLY
    assert not PRIMARY_ONLY & permissions_for(Role.SCHOOL_ADMIN, is_primary=False)


def test_an_additional_admin_never_has_more_than_the_principal() -> None:
    principal, additional = COLUMNS.index("principal"), COLUMNS.index("additional_admin")

    assert [
        name for name, cells in MATRIX.items() if cells[additional] and not cells[principal]
    ] == []


@pytest.mark.parametrize(
    ("role", "is_primary", "permission", "allowed"),
    [
        # Only the super admin switches report card levels and features (non-negotiable).
        (Role.SUPER_ADMIN, False, "report_card_levels.toggle", True),
        (Role.SCHOOL_ADMIN, True, "report_card_levels.toggle", False),
        (Role.SCHOOL_ADMIN, True, "features.toggle", False),
        # The super admin resets school admins only (AC03.6).
        (Role.SUPER_ADMIN, False, "school_admins.reset_login", True),
        (Role.SUPER_ADMIN, False, "users.reset_login", False),
        # Teachers enter and submit; reviewers review but never edit scores (D-052).
        (Role.TEACHER, False, "scores.enter", True),
        (Role.TEACHER, False, "sheets.submit", True),
        (Role.REVIEWER, False, "scores.enter", False),
        (Role.REVIEWER, False, "sheets.review", True),
        # Students needing attention is staff-only (non-negotiable).
        (Role.PARENT, False, "attention.view", False),
        (Role.STUDENT, False, "attention.view", False),
        (Role.TEACHER, False, "attention.view", True),
        # Approving and publishing is for school admins.
        (Role.TEACHER, False, "results.publish", False),
        (Role.SCHOOL_ADMIN, False, "results.publish", True),
    ],
)
def test_what_each_role_may_do(
    role: Role, is_primary: bool, permission: str, allowed: bool
) -> None:
    assert (permission in permissions_for(role, is_primary=is_primary)) is allowed


def test_a_pupil_may_only_read_reports_and_notices() -> None:
    assert permissions_for(Role.STUDENT) == {"reports.view", "notices.read"}


# --- the database holds the same matrix ------------------------------------------------


def test_the_database_holds_the_same_matrix(db_session: Session) -> None:
    roles = set(db_session.scalars(text("select key from roles")))
    permissions = set(db_session.scalars(text("select key from permissions")))
    grants = {
        (role, permission, primary_only)
        for role, permission, primary_only in db_session.execute(
            text("select role_key, permission_key, primary_only from role_permissions")
        )
    }

    assert roles == {role.value for role in Role}
    assert permissions == set(MATRIX)
    assert grants == role_permission_rows()


@pytest.mark.parametrize("role", ["app_user", "app_platform"])
def test_the_app_can_read_permissions(db_session: Session, role: str) -> None:
    with acting_as(db_session, role):
        count = db_session.scalar(text("select count(*) from role_permissions"))

    assert count == len(role_permission_rows())


@pytest.mark.parametrize(
    "statement",
    [
        "insert into permissions (key) values ('grades.fake')",
        "update role_permissions set primary_only = false",
        "delete from role_permissions where role_key = 'teacher'",
        "insert into roles (key) values ('bursar')",
    ],
)
@pytest.mark.parametrize("role", ["app_user", "app_platform"])
def test_the_app_can_never_change_permissions(
    db_session: Session, role: str, statement: str
) -> None:
    # Denied: permissions change only through a reviewed migration.
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(text(statement))
