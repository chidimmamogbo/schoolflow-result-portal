"""The audit log and the final database audit (BUILD_PROMPT 9.1 items 11 and 12; SPEC F11;
D-051, D-137, D-156).

Behaviour: audit events record who did what, never change or disappear (even
for the table owner) and never hold passwords, tokens or hashes; a school
sees and writes only its own events, the platform sees all. Across the whole
database: every table has row-level security except the listed platform-level
tables; no app role owns a table or can create one; every function that runs
as the owner fixes its search path and is not open to everyone; and no app
role can rewrite or delete the history and snapshot tables. All data is
fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import use_context
from app.tests.db_support import APP_ROLES, acting_as, refused, violates
from app.tests.factories import add_membership, create_school, create_user, write_audit_event

# Platform-level tables with no school rows; their grants keep them safe (D-137).
NO_RLS_NEEDED = {
    "alembic_version",
    "roles",
    "permissions",
    "role_permissions",
    "platform_settings",
    "pricing_versions",
    "pricing_tiers",
    "payment_events",
}
# History and snapshot tables: never rewritten or deleted by any app role.
KEPT_TABLES = (
    "approval_actions",
    "result_revisions",
    "class_section_actions",
    "report_templates",
    "report_documents",
    "verification_tokens",
    "attention_entries",
    "correction_events",
    "correction_attachments",
    "files",
    "notice_audiences",
    "notice_recipients",
    "notice_reads",
    "pricing_versions",
    "pricing_tiers",
    "audit_events",
)


@dataclass(frozen=True)
class Audit:
    gmc: uuid.UUID
    bsa: uuid.UUID
    tunde: uuid.UUID


@pytest.fixture
def audit(db_session: Session) -> Audit:
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    tunde = create_user(db_session, username="tunde.adebayo", full_name="Tunde Adebayo")
    add_membership(db_session, tunde, gmc, "teacher")
    return Audit(gmc, bsa, tunde)


# --- audit events (F11, item 11) ------------------------------------------------------


def test_an_audit_event_records_who_did_what(audit: Audit, db_session: Session) -> None:
    # F11: CA2 from 12 to 14 with its reason.
    use_context(db_session, school_id=audit.gmc, user_id=audit.tunde)

    event = write_audit_event(db_session, audit.gmc, reason="Corrected transcription error")

    row = db_session.execute(
        text(
            "select actor_id, action, old_values, new_values, reason from audit_events"
            " where id = :id"
        ),
        {"id": event},
    ).one()
    assert tuple(row) == (
        audit.tunde,
        "scores.update",
        {"value": 12},
        {"value": 14},
        "Corrected transcription error",
    )


@pytest.mark.parametrize(
    "statement", ["update audit_events set reason = 'Edited'", "delete from audit_events"]
)
def test_audit_events_never_change(audit: Audit, db_session: Session, statement: str) -> None:
    # Append-only at the database level, even for the owner.
    write_audit_event(db_session, audit.gmc)

    with violates(db_session, "audit_events_append_only"):
        db_session.execute(text(statement))


@pytest.mark.parametrize("key", ["password", "password_hash", "token", "token_hash"])
def test_audit_events_never_hold_secrets(audit: Audit, db_session: Session, key: str) -> None:
    with violates(db_session, "ck_audit_events_no_secrets"):
        write_audit_event(db_session, audit.gmc, new={key: "x"})


def test_an_action_is_area_dot_action(audit: Audit, db_session: Session) -> None:
    with violates(db_session, "ck_audit_events_action_format"):
        write_audit_event(db_session, audit.gmc, action="Changed a score")


def test_a_school_sees_and_writes_only_its_own_events(audit: Audit, db_session: Session) -> None:
    write_audit_event(db_session, audit.gmc)
    write_audit_event(db_session, None, action="pricing.update")

    with acting_as(db_session, "app_user", school_id=audit.bsa):
        bsa_sees = db_session.scalar(text("select count(*) from audit_events"))
    with acting_as(db_session, "app_user", school_id=audit.gmc):
        gmc_sees = db_session.scalar(text("select count(*) from audit_events"))
    with acting_as(db_session, "app_user", school_id=audit.gmc), refused(db_session):
        write_audit_event(db_session, audit.bsa)
    with acting_as(db_session, "app_platform"):
        platform_sees = db_session.scalar(text("select count(*) from audit_events"))

    assert (bsa_sees, gmc_sees, platform_sees) == (0, 1, 2)


@pytest.mark.parametrize("role", ["app_verifier", "app_sender"])
def test_other_roles_cannot_read_the_audit_log(
    audit: Audit, db_session: Session, role: str
) -> None:
    write_audit_event(db_session, audit.gmc)

    with acting_as(db_session, role), refused(db_session):
        db_session.execute(text("select count(*) from audit_events"))


# --- the final database audit (item 12) ----------------------------------------------


def test_every_table_has_row_level_security(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
            " where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
        )
    ).scalars()

    assert set(rows) == NO_RLS_NEEDED


def test_no_app_role_owns_anything(db_session: Session) -> None:
    owned = db_session.scalars(
        text(
            "select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace"
            " where n.nspname = 'public' and pg_get_userbyid(c.relowner) = any(:roles)"
        ),
        {"roles": list(APP_ROLES)},
    ).all()

    assert owned == []


def test_owner_run_functions_are_locked_down(db_session: Session) -> None:
    # Each SECURITY DEFINER function fixes its search path and is not open to everyone.
    rows = db_session.execute(
        text(
            "select p.proname, p.proconfig,"
            " has_function_privilege('public', p.oid, 'EXECUTE') as public_can_run"
            " from pg_proc p join pg_namespace n on n.oid = p.pronamespace"
            " where n.nspname = 'public' and p.prosecdef"
        )
    ).all()

    settings: dict[str, list[str]] = {row.proname: row.proconfig or [] for row in rows}
    assert settings
    assert [
        name for name, config in settings.items() if not any("search_path" in c for c in config)
    ] == []
    assert [row.proname for row in rows if row.public_can_run] == []


@pytest.mark.parametrize("table", KEPT_TABLES)
@pytest.mark.parametrize("role", APP_ROLES)
def test_no_app_role_rewrites_history(db_session: Session, table: str, role: str) -> None:
    can_change = db_session.scalar(
        text(
            "select has_table_privilege(:role, :table, 'DELETE')"
            " or has_table_privilege(:role, :table, 'TRUNCATE')"
        ),
        {"role": role, "table": table},
    )

    assert can_change is False
