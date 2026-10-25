"""The school's own set-up: /school (BUILD_PROMPT 9.2e, first part; SPEC F04, F08, F25).

Settings and branding, the assessment mode and head's title per level,
sessions and terms, classes and arms, departments, subjects and the subjects
each arm takes. Everyone in the school reads; school admins change
(`school.settings`, `assessment_mode.configure`). The database works for the
signed-in membership's school only, so an id from another school is simply
not found (404). Every change is audited in the same transaction.
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, ensure_level_enabled, found
from app.core.errors import ProblemError
from app.src.audit.services import write_audit
from app.src.platform_admin.schemas import SchoolDetails
from app.src.schools.models import Level
from app.src.schools.schemas import (
    EditSettings,
    LevelChange,
    LevelName,
    LevelResult,
    LevelRow,
    SchoolSettings,
)

# Unique-name rules from migrations 6 (names compared without capitals).
NAME_RULES = frozenset(
    {
        "ix_classes_unique_name",
        "ix_class_arms_unique_name",
        "ix_departments_unique_name",
        "ix_subjects_unique_name",
        "uq_academic_sessions_school_id_name",
        "uq_terms_session_id_term_number",
    }
)


@contextmanager
def unique_name(session: Session) -> Generator[None]:
    """Turn a clash with an existing name into a clear 409 `name_taken`."""
    try:
        with session.begin_nested():
            yield
    except IntegrityError as error:
        original = error.orig
        rule = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
        if rule in NAME_RULES:
            raise ProblemError(409, "This name is already used.", code="name_taken") from None
        raise


def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


def one_id(session: Session, sql: str, row_id: object) -> uuid.UUID:
    """The id of a row this school can see, or 404."""
    try:
        wanted = uuid.UUID(str(row_id))
    except ValueError:
        raise ProblemError(404, "Not Found") from None
    return found(session.scalar(text(sql), {"id": wanted}))


# --- settings and levels -----------------------------------------------------------------
SETTINGS_FIELDS = ("email", "phone", "address", "city", "state", "country", "colour")


def settings_of(session: Session, school_id: uuid.UUID) -> SchoolSettings:
    row = session.execute(
        text(
            "select id, code, name, email, phone, address, city, state, country, colour"
            " from schools where id = :id"
        ),
        {"id": school_id},
    ).one()
    features = {
        str(r.feature): bool(r.enabled)
        for r in session.execute(text("select feature, enabled from school_features"))
    }
    order = [level.value for level in Level]
    levels = sorted(
        (
            LevelRow(
                level=r.level,
                enabled=r.enabled,
                assessment_mode=r.assessment_mode,
                head_title=r.head_title,
            )
            for r in session.execute(
                text("select level, enabled, assessment_mode, head_title from school_levels")
            )
        ),
        key=lambda level: order.index(level.level),
    )
    return SchoolSettings(
        id=str(row.id),
        code=row.code,
        name=row.name,
        email=row.email,
        phone=row.phone,
        address=row.address,
        city=row.city,
        state=row.state,
        country=row.country,
        colour=row.colour,
        features=features,
        levels=levels,
    )


def get_settings(
    who: Principal,
    session: Session,
) -> SchoolSettings:
    return settings_of(session, found(who.school_id))


def edit_settings(
    body: EditSettings,
    who: Principal,
    session: Session,
) -> SchoolSettings:
    school_id = found(who.school_id)
    current = settings_of(session, school_id).model_dump()
    wanted = {field: current[field] for field in ("name", *SETTINGS_FIELDS)}
    wanted.update(body.model_dump(exclude_none=True))
    try:
        SchoolDetails.model_validate(wanted)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    changed = {f: wanted[f] for f in SETTINGS_FIELDS if wanted[f] != current[f]}
    if changed:
        assignments = ", ".join(f"{field} = :{field}" for field in changed)
        session.execute(
            text(f"update schools set {assignments} where id = :id"),  # noqa: S608 (fixed names)
            {**changed, "id": school_id},
        )
        audit(
            session,
            who,
            "school.update",
            target=("schools", school_id),
            old={f: current[f] for f in changed},
            new=changed,
        )
    return settings_of(session, school_id)


def change_level(
    level: LevelName,
    body: LevelChange,
    who: Principal,
    session: Session,
) -> LevelResult:
    ensure_level_enabled(session, who, Level(level))
    if body.assessment_mode is not None and "assessment_mode.configure" not in who.permissions:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")
    current = session.execute(
        text("select assessment_mode, head_title from school_levels where level = :l"),
        {"l": level},
    ).one()
    changes = body.model_dump(exclude_none=True)
    applies_from = "this_term"
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        session.execute(
            text(f"update school_levels set {assignments} where level = :l"),  # noqa: S608
            {**changes, "l": level},
        )
    if body.assessment_mode is not None and body.assessment_mode != current.assessment_mode:
        # The active term's structure keeps the mode its entries started with (AC08.6).
        structure = session.execute(
            text(
                "select s.id, s.locked_at is not null as locked from assessment_structures s"
                " join terms t on t.id = s.term_id where t.is_active and s.level = :l"
            ),
            {"l": level},
        ).first()
        if structure is not None and structure.locked:
            applies_from = "next_term"
        elif structure is not None:
            session.execute(
                text("update assessment_structures set assessment_mode = :m where id = :id"),
                {"m": body.assessment_mode, "id": structure.id},
            )
    if changes:
        audit(
            session,
            who,
            "school_levels.update",
            target=("schools", found(who.school_id)),
            old={"level": level, **{f: getattr(current, f) for f in changes}},
            new={"level": level, **changes},
        )
    row = session.execute(
        text("select assessment_mode, head_title from school_levels where level = :l"),
        {"l": level},
    ).one()
    return LevelResult(
        level=level,
        assessment_mode=row.assessment_mode,
        head_title=row.head_title,
        applies_from=applies_from,
    )
