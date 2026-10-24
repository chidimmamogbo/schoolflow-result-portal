"""Tenant isolation: database roles and row-level security (D-026, D-027, D-051, D-137).

Behaviour: each database role sees and changes only what it should. A school
user (app_user) sees only its own school and cannot change platform data; the
platform role (app_platform) manages schools but cannot delete them; the
verification role (app_verifier) sees nothing yet; a connection with no school
set sees nothing; and the school setting never leaks into the next
transaction on a reused (pooled) connection.

Tests switch to each role inside the test transaction with SET LOCAL ROLE, so
PostgreSQL applies exactly the rules the real logins get. All data is fictional.
"""

import uuid

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.db.session import use_context
from app.tests.db_support import APP_ROLES, acting_as, refused
from app.tests.factories import create_school

COUNT = {
    "schools": text("select count(*) from schools"),
    "school_features": text("select count(*) from school_features"),
    "school_levels": text("select count(*) from school_levels"),
    "platform_settings": text("select count(*) from platform_settings"),
}


@pytest.fixture
def two_schools(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    return gmc, bsa


# --- the roles themselves ---------------------------------------------------


def test_app_roles_cannot_bypass_row_level_security(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "select rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles"
            " where rolname = any(:names) order by rolname"
        ),
        {"names": list(APP_ROLES)},
    ).all()

    assert [row.rolname for row in rows] == sorted(APP_ROLES)
    for row in rows:
        assert not (row.rolsuper or row.rolbypassrls or row.rolcreaterole or row.rolcreatedb)


@pytest.mark.parametrize("role", APP_ROLES)
def test_app_roles_cannot_create_tables(db_session: Session, role: str) -> None:
    can_create, can_use = db_session.execute(
        text(
            "select has_schema_privilege(:role, 'public', 'CREATE'),"
            " has_schema_privilege(:role, 'public', 'USAGE')"
        ),
        {"role": role},
    ).one()

    assert can_create is False
    assert can_use is True


# --- school users (app_user) -----------------------------------------------


def test_school_user_sees_only_their_own_school(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID]
) -> None:
    gmc, _ = two_schools

    with acting_as(db_session, "app_user", school_id=gmc):
        codes = db_session.scalars(text("select code from schools")).all()
        feature_schools = set(db_session.scalars(text("select school_id from school_features")))
        level_schools = set(db_session.scalars(text("select school_id from school_levels")))

    assert codes == ["GMC"]
    assert feature_schools == {gmc}
    assert level_schools == {gmc}


def test_school_user_cannot_read_another_school_by_id(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID]
) -> None:
    # Denied: an ID swap finds nothing, even if the application check were skipped (AT-27.1).
    gmc, bsa = two_schools

    with acting_as(db_session, "app_user", school_id=gmc):
        school = db_session.scalar(text("select count(*) from schools where id = :id"), {"id": bsa})
        levels = db_session.scalar(
            text("select count(*) from school_levels where school_id = :id"), {"id": bsa}
        )

    assert (school, levels) == (0, 0)


@pytest.mark.parametrize("table", ["schools", "school_features", "school_levels"])
def test_no_school_set_means_no_rows_and_no_error(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID], table: str
) -> None:
    with acting_as(db_session, "app_user"):
        assert db_session.scalar(COUNT[table]) == 0


def test_school_user_can_read_platform_settings(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID]
) -> None:
    db_session.execute(
        text(
            "insert into platform_settings (key, value) values ('billing.grace_period_days', '14')"
        )
    )

    with acting_as(db_session, "app_user", school_id=two_schools[0]):
        days = db_session.scalar(
            text("select value from platform_settings where key = 'billing.grace_period_days'")
        )

    assert days == 14


@pytest.mark.parametrize(
    "statement",
    [
        "update schools set name = 'Renamed College'",
        "update schools set status = 'suspended'",
        "delete from schools",
        "insert into schools (name, email, phone, address, city, state, code, colour,"
        " school_type) values ('Fake School', 'a@fake.example', '0801', 'x', 'x', 'x', 'FAKE',"
        " '#000000', 'custom')",
        # AC25.2: only the super admin switches report card levels, even at database level.
        "update school_levels set enabled = false",
        # F01: only the super admin switches features.
        "update school_features set enabled = false",
        "insert into platform_settings (key, value) values ('billing.grace_period_days', '30')",
        "update platform_settings set value = '30'",
    ],
)
def test_school_user_cannot_change_platform_data(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID], statement: str
) -> None:
    with acting_as(db_session, "app_user", school_id=two_schools[0]), refused(db_session):
        db_session.execute(text(statement))


# --- the platform (app_platform) and verification (app_verifier) roles ------


def test_platform_role_sees_and_manages_every_school(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID]
) -> None:
    with acting_as(db_session, "app_platform"):
        codes = sorted(db_session.scalars(text("select code from schools")))
        rcs = create_school(
            db_session, code="RCS", name="Royal Crest Schools", school_type="all_levels"
        )
        db_session.execute(
            text("update schools set status = 'suspended' where id = :id"), {"id": rcs}
        )
        db_session.execute(
            text(
                "update school_levels set enabled = false"
                " where school_id = :id and level = 'nursery'"
            ),
            {"id": rcs},
        )
        db_session.execute(
            text(
                "insert into platform_settings (key, value)"
                " values ('billing.invoice_due_days', '14')"
            )
        )
        status = db_session.scalar(text("select status from schools where id = :id"), {"id": rcs})

    assert codes == ["BSA", "GMC"]
    assert status == "suspended"


def test_platform_role_cannot_delete_schools(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID]
) -> None:
    # Denied: suspension never deletes data (F24); nobody deletes a school.
    with acting_as(db_session, "app_platform"), refused(db_session):
        db_session.execute(text("delete from schools where code = 'BSA'"))


@pytest.mark.parametrize("table", list(COUNT))
def test_verification_role_has_no_access_yet(
    db_session: Session, two_schools: tuple[uuid.UUID, uuid.UUID], table: str
) -> None:
    # Denied: app_verifier gets only what public verification needs, when it is built.
    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(COUNT[table])


# --- the per-transaction setting (D-027) -------------------------------------


def test_school_setting_never_leaks_to_the_next_transaction(db_engine: Engine) -> None:
    # One pooled connection only, so the second session reuses the first one's connection.
    engine = create_engine(db_engine.url, pool_size=1, max_overflow=0)
    school, user = uuid.uuid4(), uuid.uuid4()
    try:
        with Session(engine) as first:
            use_context(first, school_id=school, user_id=user)
            first_connection = first.scalar(text("select pg_backend_pid()"))
            seen = first.execute(
                text("select app_current_school_id(), app_current_user_id()")
            ).one()
            first.commit()
        with Session(engine) as second:
            same_connection = second.scalar(text("select pg_backend_pid()")) == first_connection
            after = second.execute(
                text("select app_current_school_id(), app_current_user_id()")
            ).one()
    finally:
        engine.dispose()

    assert tuple(seen) == (school, user)
    assert same_connection
    assert tuple(after) == (None, None)


def test_context_is_reset_at_the_start_of_every_transaction(db_engine: Engine) -> None:
    engine = create_engine(db_engine.url, pool_size=1, max_overflow=0)
    try:
        with Session(engine) as careless:
            # A bug that sets the school for the whole connection instead of one transaction.
            careless.execute(
                text("select set_config('app.school_id', :id, false)"), {"id": str(uuid.uuid4())}
            )
            careless.commit()
        with Session(engine) as next_session:
            school = next_session.scalar(text("select app_current_school_id()"))
    finally:
        engine.dispose()

    assert school is None


# --- the inventory (BUILD_PROMPT 9.1 item 12, now checked on every run) ------


def test_every_school_owned_table_has_row_level_security(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "select c.relname, c.relrowsecurity from pg_class c"
            " join pg_namespace n on n.oid = c.relnamespace"
            " where n.nspname = 'public' and c.relkind = 'r' and (c.relname = 'schools' or exists"
            " (select 1 from information_schema.columns col where col.table_schema = 'public'"
            " and col.table_name = c.relname and col.column_name = 'school_id'))"
        )
    ).all()

    assert {row.relname for row in rows} >= {"schools", "school_features", "school_levels"}
    assert [row.relname for row in rows if not row.relrowsecurity] == []


def test_no_table_is_open_to_everyone(db_session: Session) -> None:
    open_tables = db_session.scalars(
        text(
            "select table_name from information_schema.table_privileges"
            " where grantee = 'PUBLIC' and table_schema = 'public'"
        )
    ).all()

    assert open_tables == []
