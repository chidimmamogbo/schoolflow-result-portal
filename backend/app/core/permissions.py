"""Who may do what: the permission matrix (SPEC section 5; D-045, D-046, D-047).

Like WordPress's roles and capabilities (current_user_can('edit_posts')), but
the list is fixed in code and mirrors the SPEC table row for row. Each
permission has one True/False per SPEC column: super admin, principal,
additional admin, reviewer, teacher, parent, student.

True also covers cells with a scope ("Assigned sheets only", "Own school",
"Platform log", "Linked wards"): the scope is checked in code by the
ownership step of the check chain (D-047), not here. For the super admin,
school-side names such as invoices.pay are reached only through the platform
pages and their own checks, because the super admin has no school.

The principal is a school admin with is_primary (D-045): permissions only the
principal has are PRIMARY_ONLY. tests/test_permissions.py compares this table
with SPEC section 5 and with the rows migration 5 put in the database, so the
three cannot drift apart. Changing a permission means: SPEC, this file and a
new migration, together.
"""

from enum import StrEnum


class Role(StrEnum):
    """The six fixed roles (D-045). No custom roles in the MVP."""

    SUPER_ADMIN = "super_admin"
    SCHOOL_ADMIN = "school_admin"
    REVIEWER = "reviewer"
    TEACHER = "teacher"
    PARENT = "parent"
    STUDENT = "student"


# The SPEC section 5 columns, in order.
COLUMNS = (
    "super_admin",
    "principal",
    "additional_admin",
    "reviewer",
    "teacher",
    "parent",
    "student",
)

Y, N = True, False

# fmt: off
#                                      super  princ. addl.  review teach. parent student
MATRIX: dict[str, tuple[bool, bool, bool, bool, bool, bool, bool]] = {
    "schools.manage":                  (Y,     N,     N,     N,     N,     N,     N),
    "features.toggle":                 (Y,     N,     N,     N,     N,     N,     N),
    "report_card_levels.toggle":       (Y,     N,     N,     N,     N,     N,     N),
    "platform.settings":               (Y,     N,     N,     N,     N,     N,     N),
    "platform.audit":                  (Y,     N,     N,     N,     N,     N,     N),
    "platform.email_log":              (Y,     N,     N,     N,     N,     N,     N),
    "platform.payments_log":           (Y,     N,     N,     N,     N,     N,     N),
    "school_admins.reset_login":       (Y,     Y,     N,     N,     N,     N,     N),
    "school_admins.sign_out_all":      (Y,     Y,     N,     N,     N,     N,     N),
    "school_admins.create":            (N,     Y,     N,     N,     N,     N,     N),
    "school_admins.remove":            (N,     Y,     N,     N,     N,     N,     N),
    "pricing.manage":                  (Y,     N,     N,     N,     N,     N,     N),
    "invoices.generate":               (Y,     N,     N,     N,     N,     N,     N),
    "payments.record_manual":          (Y,     N,     N,     N,     N,     N,     N),
    "school.settings":                 (N,     Y,     Y,     N,     N,     N,     N),
    "users.create":                    (N,     Y,     Y,     N,     N,     N,     N),
    "users.reset_login":               (N,     Y,     Y,     N,     N,     N,     N),
    "assignments.manage":              (N,     Y,     Y,     N,     N,     N,     N),
    "guardian_links.manage":           (N,     Y,     Y,     N,     N,     N,     N),
    "grading.configure":               (N,     Y,     Y,     N,     N,     N,     N),
    "assessment.configure":            (N,     Y,     Y,     N,     N,     N,     N),
    "pass_mark.configure":             (N,     Y,     Y,     N,     N,     N,     N),
    "assessment_mode.configure":       (N,     Y,     Y,     N,     N,     N,     N),
    "skills.configure":                (N,     Y,     Y,     N,     N,     N,     N),
    "scores.enter":                    (N,     N,     N,     N,     Y,     N,     N),
    "ratings.enter":                   (N,     N,     N,     N,     Y,     N,     N),
    "sheets.submit":                   (N,     N,     N,     N,     Y,     N,     N),
    "sheets.review":                   (N,     N,     N,     Y,     N,     N,     N),
    "sheets.return":                   (N,     N,     N,     Y,     N,     N,     N),
    "form_class.report_entries":       (N,     Y,     Y,     N,     Y,     N,     N),
    "sheets.approve":                  (N,     Y,     Y,     N,     N,     N,     N),
    "results.publish":                 (N,     Y,     Y,     N,     N,     N,     N),
    "results.principal_comments":      (N,     Y,     Y,     N,     N,     N,     N),
    "results.reopen":                  (N,     Y,     Y,     N,     N,     N,     N),
    "results.revoke":                  (N,     Y,     Y,     N,     N,     N,     N),
    "attention.view":                  (N,     Y,     Y,     Y,     Y,     N,     N),
    "audit.view":                      (Y,     Y,     Y,     N,     N,     N,     N),
    "report_templates.manage":         (N,     Y,     Y,     N,     N,     N,     N),
    "reports.view":                    (N,     Y,     Y,     Y,     Y,     Y,     Y),
    "corrections.create":              (N,     Y,     Y,     Y,     Y,     Y,     N),
    "corrections.manage":              (N,     Y,     Y,     N,     N,     N,     N),
    "notices.post":                    (Y,     Y,     Y,     N,     N,     N,     N),
    "notices.read":                    (Y,     Y,     Y,     Y,     Y,     Y,     Y),
    "billing.view":                    (Y,     Y,     Y,     N,     N,     N,     N),
    "invoices.pay":                    (Y,     Y,     Y,     N,     N,     N,     N),
}
# fmt: on

_PRINCIPAL = COLUMNS.index("principal")
_ADDITIONAL_ADMIN = COLUMNS.index("additional_admin")
_COLUMN_OF = {
    Role.SUPER_ADMIN: COLUMNS.index("super_admin"),
    Role.REVIEWER: COLUMNS.index("reviewer"),
    Role.TEACHER: COLUMNS.index("teacher"),
    Role.PARENT: COLUMNS.index("parent"),
    Role.STUDENT: COLUMNS.index("student"),
}

# Things the principal may do and an additional school admin may not.
PRIMARY_ONLY = frozenset(
    name for name, cells in MATRIX.items() if cells[_PRINCIPAL] and not cells[_ADDITIONAL_ADMIN]
)


def permissions_for(role: Role, *, is_primary: bool = False) -> frozenset[str]:
    """Everything this role may do, before the scope and ownership checks (D-047)."""
    if role is Role.SCHOOL_ADMIN:
        column = _PRINCIPAL if is_primary else _ADDITIONAL_ADMIN
    else:
        column = _COLUMN_OF[role]
    return frozenset(name for name, cells in MATRIX.items() if cells[column])


def role_permission_rows() -> set[tuple[str, str, bool]]:
    """The (role, permission, primary_only) rows the database must hold (migration 5)."""
    rows: set[tuple[str, str, bool]] = set()
    for name, cells in MATRIX.items():
        for role, column in _COLUMN_OF.items():
            if cells[column]:
                rows.add((role.value, name, False))
        if cells[_PRINCIPAL] or cells[_ADDITIONAL_ADMIN]:
            rows.add((Role.SCHOOL_ADMIN.value, name, name in PRIMARY_ONLY))
    return rows
