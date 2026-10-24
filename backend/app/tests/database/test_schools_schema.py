"""Database rules for migration 1: schools, school_features, school_levels,
platform_settings (BUILD_PROMPT 9.1 item 1; SPEC F01, F24, F25; option A,
Chidimma 2026-10-12: four level rows per school).

Behaviour: the database itself rejects bad school data, even if a bug in the
Python code let it through. These tests use plain SQL on purpose, so they
check the database and not the Python models. All data is fictional.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

FEATURES = (
    "results",
    "report_cards",
    "parent_portal",
    "correction_queue",
    "notice_board",
    "email_notifications",
)
LEVELS = ("nursery", "primary", "junior_secondary", "senior_secondary")


def school_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "name": "Greenfield Model College",
        "email": "office@greenfield.example",
        "phone": "08010000001",
        "address": "12 Example Close",
        "city": "Ikeja",
        "state": "Lagos",
        "code": "GMC",
        "colour": "#1F6FEB",
        "school_type": "secondary_only",
    }
    values.update(overrides)
    return values


def insert_school(session: Session, **overrides: Any) -> str:
    return str(
        session.scalar(
            text(
                "insert into schools (name, email, phone, address, city, state, code, colour,"
                " school_type) values (:name, :email, :phone, :address, :city, :state, :code,"
                " :colour, :school_type) returning id"
            ),
            school_values(**overrides),
        )
    )


def insert_level(
    session: Session,
    school_id: str,
    level: str,
    *,
    enabled: bool = True,
    assessment_mode: str = "scores",
    head_title: str = "Principal",
) -> None:
    session.execute(
        text(
            "insert into school_levels (school_id, level, enabled, assessment_mode, head_title)"
            " values (:school_id, :level, :enabled, :assessment_mode, :head_title)"
        ),
        {
            "school_id": school_id,
            "level": level,
            "enabled": enabled,
            "assessment_mode": assessment_mode,
            "head_title": head_title,
        },
    )


def insert_levels(session: Session, school_id: str, enabled: dict[str, bool]) -> None:
    for level in LEVELS:
        insert_level(session, school_id, level, enabled=enabled[level])


def check_deferred_rules(session: Session) -> None:
    # Rules across several rows are checked at COMMIT. Tests never really
    # commit (everything is rolled back), so this runs those checks now, then
    # puts them back to "at commit", as a real commit would leave things.
    session.execute(text("set constraints all immediate"))
    session.execute(text("set constraints all deferred"))


@contextmanager
def violates(constraint: str) -> Generator[None]:
    """Expect the database to refuse the change because of this named rule."""
    with pytest.raises(IntegrityError) as error:
        yield
    original = error.value.orig
    assert isinstance(original, psycopg.Error)
    assert original.diag.constraint_name == constraint


SECONDARY_ONLY = {
    "nursery": False,
    "primary": False,
    "junior_secondary": True,
    "senior_secondary": True,
}


# --- schools ---------------------------------------------------------------


def test_a_valid_school_gets_safe_defaults(db_session: Session) -> None:
    school_id = insert_school(db_session)

    row = (
        db_session.execute(
            text("select status, country, created_at, updated_at from schools where id = :id"),
            {"id": school_id},
        )
        .mappings()
        .one()
    )
    assert len(school_id) == 36  # a random UUID, not 1, 2, 3 (D-028)
    assert row["status"] == "active"
    assert row["country"] == "Nigeria"
    assert row["created_at"] is not None
    assert row["updated_at"] == row["created_at"]


@pytest.mark.parametrize("code", ["GM", "gmc", "GMC-1", "ABCDEFGHIJK", " GMC"])
def test_school_code_must_be_3_to_10_capital_letters_or_digits(
    db_session: Session, code: str
) -> None:
    with violates("ck_schools_code_format"):
        insert_school(db_session, code=code)


def test_school_code_is_unique(db_session: Session) -> None:
    insert_school(db_session)

    with violates("uq_schools_code"):
        insert_school(db_session, name="Another School", email="hello@another.example")


@pytest.mark.parametrize("colour", ["red", "#12345", "#1F6FEBAA", "1F6FEB"])
def test_school_colour_must_be_a_hex_colour(db_session: Session, colour: str) -> None:
    with violates("ck_schools_colour_hex"):
        insert_school(db_session, colour=colour)


def test_school_status_is_active_or_suspended(db_session: Session) -> None:
    school_id = insert_school(db_session)

    with violates("ck_schools_status_allowed"):
        db_session.execute(
            text("update schools set status = 'deleted' where id = :id"), {"id": school_id}
        )


def test_school_type_must_be_a_known_type(db_session: Session) -> None:
    with violates("ck_schools_school_type_allowed"):
        insert_school(db_session, school_type="university")


@pytest.mark.parametrize("name", ["", "   "])
def test_school_name_cannot_be_blank(db_session: Session, name: str) -> None:
    with violates("ck_schools_name_not_blank"):
        insert_school(db_session, name=name)


def test_school_email_must_look_like_an_email(db_session: Session) -> None:
    with violates("ck_schools_email_format"):
        insert_school(db_session, email="office.greenfield.example")


def test_updated_at_moves_when_a_school_changes(db_session: Session) -> None:
    school_id = insert_school(db_session)
    db_session.execute(
        text("update schools set updated_at = '2020-01-01' where id = :id"), {"id": school_id}
    )

    db_session.execute(
        text("update schools set phone = '08010000002' where id = :id"), {"id": school_id}
    )

    changed = db_session.scalar(
        text("select updated_at > '2020-01-02' from schools where id = :id"), {"id": school_id}
    )
    assert changed is True


# --- school_features -------------------------------------------------------


def test_each_of_the_six_features_can_be_set(db_session: Session) -> None:
    school_id = insert_school(db_session)
    for feature in FEATURES:
        db_session.execute(
            text("insert into school_features (school_id, feature, enabled) values (:s, :f, true)"),
            {"s": school_id, "f": feature},
        )

    count = db_session.scalar(
        text("select count(*) from school_features where school_id = :s"), {"s": school_id}
    )
    assert count == 6


def test_unknown_feature_is_rejected(db_session: Session) -> None:
    school_id = insert_school(db_session)

    with violates("ck_school_features_feature_allowed"):
        db_session.execute(
            text(
                "insert into school_features (school_id, feature, enabled)"
                " values (:s, 'payroll', true)"
            ),
            {"s": school_id},
        )


def test_a_feature_appears_once_per_school(db_session: Session) -> None:
    school_id = insert_school(db_session)
    add = text(
        "insert into school_features (school_id, feature, enabled) values (:s, 'results', true)"
    )
    db_session.execute(add, {"s": school_id})

    with violates("uq_school_features_school_id_feature"):
        db_session.execute(add, {"s": school_id})


def test_a_feature_needs_a_real_school(db_session: Session) -> None:
    with violates("fk_school_features_school_id_schools"):
        db_session.execute(
            text(
                "insert into school_features (school_id, feature, enabled)"
                " values (gen_random_uuid(), 'results', true)"
            )
        )


# --- school_levels (option A: four rows per school) ------------------------


def test_secondary_only_school_has_four_levels_with_two_on(db_session: Session) -> None:
    school_id = insert_school(db_session)
    insert_levels(db_session, school_id, SECONDARY_ONLY)

    check_deferred_rules(db_session)
    on = db_session.scalars(
        text("select level from school_levels where school_id = :s and enabled order by level"),
        {"s": school_id},
    ).all()
    assert on == ["junior_secondary", "senior_secondary"]


def test_custom_primary_only_school_is_allowed(db_session: Session) -> None:
    school_id = insert_school(db_session, code="BSA", school_type="custom")
    insert_levels(
        db_session,
        school_id,
        {"nursery": False, "primary": True, "junior_secondary": False, "senior_secondary": False},
    )

    check_deferred_rules(db_session)


def test_unknown_level_is_rejected(db_session: Session) -> None:
    school_id = insert_school(db_session)

    with violates("ck_school_levels_level_allowed"):
        insert_level(db_session, school_id, "creche")


def test_assessment_mode_is_scores_or_skill_ratings(db_session: Session) -> None:
    school_id = insert_school(db_session)

    with violates("ck_school_levels_assessment_mode_allowed"):
        insert_level(db_session, school_id, "nursery", assessment_mode="grades")


def test_head_title_cannot_be_blank(db_session: Session) -> None:
    school_id = insert_school(db_session)

    with violates("ck_school_levels_head_title_not_blank"):
        insert_level(db_session, school_id, "primary", head_title=" ")


def test_a_level_appears_once_per_school(db_session: Session) -> None:
    school_id = insert_school(db_session)
    insert_level(db_session, school_id, "primary")

    with violates("uq_school_levels_school_id_level"):
        insert_level(db_session, school_id, "primary")


def test_junior_and_senior_secondary_switch_together(db_session: Session) -> None:
    # Denied: one "Secondary report cards" toggle covers both (SPEC F25 rule 2).
    school_id = insert_school(db_session)
    insert_levels(db_session, school_id, {**SECONDARY_ONLY, "senior_secondary": False})

    with violates("school_levels_secondary_together"):
        check_deferred_rules(db_session)


def test_at_least_one_level_must_be_on(db_session: Session) -> None:
    # Denied: AC25.5, all three toggles off is rejected.
    school_id = insert_school(db_session)
    insert_levels(db_session, school_id, dict.fromkeys(LEVELS, False))

    with violates("school_levels_at_least_one_on"):
        check_deferred_rules(db_session)


def test_switching_secondary_off_alone_is_rejected_later_too(db_session: Session) -> None:
    school_id = insert_school(db_session, code="RCS", school_type="all_levels")
    insert_levels(db_session, school_id, dict.fromkeys(LEVELS, True))
    check_deferred_rules(db_session)

    db_session.execute(
        text(
            "update school_levels set enabled = false"
            " where school_id = :s and level = 'junior_secondary'"
        ),
        {"s": school_id},
    )
    with violates("school_levels_secondary_together"):
        check_deferred_rules(db_session)


def test_a_school_with_levels_has_all_four(db_session: Session) -> None:
    school_id = insert_school(db_session)
    for level in ("primary", "junior_secondary", "senior_secondary"):
        insert_level(db_session, school_id, level)

    with violates("school_levels_all_four"):
        check_deferred_rules(db_session)


# --- platform_settings -----------------------------------------------------


def test_platform_setting_stores_a_json_value(db_session: Session) -> None:
    db_session.execute(
        text(
            "insert into platform_settings (key, value) values ('billing.grace_period_days', '14')"
        )
    )

    value = db_session.scalar(
        text("select value from platform_settings where key = 'billing.grace_period_days'")
    )
    assert value == 14


@pytest.mark.parametrize("key", ["Grace Period", "", "billing..days", "1billing"])
def test_platform_setting_key_format(db_session: Session, key: str) -> None:
    with violates("ck_platform_settings_key_format"):
        db_session.execute(
            text("insert into platform_settings (key, value) values (:key, '1')"), {"key": key}
        )


def test_platform_setting_key_is_unique(db_session: Session) -> None:
    add = text(
        "insert into platform_settings (key, value) values ('security.max_additional_admins', '2')"
    )
    db_session.execute(add)

    with violates("pk_platform_settings"):
        db_session.execute(add)
