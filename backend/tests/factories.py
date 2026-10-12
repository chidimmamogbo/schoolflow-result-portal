"""Builders for fictional test data, written as plain SQL.

Like a WordPress test that calls wp_insert_post() to set up a page before
checking something, these functions insert a complete, valid record so each
test can focus on the one rule it checks. All names and codes are fictional.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from schoolflow_api.schools.models import AssessmentMode, Feature, Level

# Report card levels each school type switches on (SPEC F25 rule 2).
LEVELS_ON = {
    "secondary_only": {Level.JUNIOR_SECONDARY, Level.SENIOR_SECONDARY},
    "nursery_primary": {Level.NURSERY, Level.PRIMARY},
    "all_levels": set(Level),
}
# Feature defaults for a new school (NAVIGATION_AND_SETTINGS.md section 3).
FEATURES_ON = set(Feature) - {Feature.CORRECTION_QUEUE}


def create_school(
    session: Session,
    *,
    code: str,
    name: str,
    school_type: str = "secondary_only",
) -> uuid.UUID:
    """Insert a school with its six features and four levels; return its id."""
    values: dict[str, Any] = {
        "name": name,
        "email": f"office@{code.lower()}.example",
        "phone": "08010000001",
        "address": "1 Example Road",
        "city": "Ikeja",
        "state": "Lagos",
        "code": code,
        "colour": "#1E6B45",
        "school_type": school_type,
    }
    school_id: uuid.UUID = session.scalar(
        text(
            "insert into schools (name, email, phone, address, city, state, code, colour,"
            " school_type) values (:name, :email, :phone, :address, :city, :state, :code,"
            " :colour, :school_type) returning id"
        ),
        values,
    )
    for feature in Feature:
        session.execute(
            text(
                "insert into school_features (school_id, feature, enabled)"
                " values (:school_id, :feature, :enabled)"
            ),
            {"school_id": school_id, "feature": feature, "enabled": feature in FEATURES_ON},
        )
    for level in Level:
        nursery_or_primary = level in {Level.NURSERY, Level.PRIMARY}
        session.execute(
            text(
                "insert into school_levels (school_id, level, enabled, assessment_mode,"
                " head_title) values (:school_id, :level, :enabled, :mode, :head_title)"
            ),
            {
                "school_id": school_id,
                "level": level,
                "enabled": level in LEVELS_ON[school_type],
                "mode": AssessmentMode.SKILL_RATINGS
                if level == Level.NURSERY
                else AssessmentMode.SCORES,
                "head_title": "Head teacher" if nursery_or_primary else "Principal",
            },
        )
    return school_id


def create_user(
    session: Session,
    *,
    username: str,
    full_name: str,
    email: str | None = None,
    is_super_admin: bool = False,
    student_school_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert an account (no school link yet); return its id."""
    user_id: uuid.UUID = session.scalar(
        text(
            "insert into users (username, full_name, email, is_super_admin, student_school_id)"
            " values (:username, :full_name, :email, :is_super_admin, :student_school_id)"
            " returning id"
        ),
        {
            "username": username,
            "full_name": full_name,
            "email": email,
            "is_super_admin": is_super_admin,
            "student_school_id": student_school_id,
        },
    )
    return user_id


def add_membership(
    session: Session,
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    role: str,
    *,
    is_primary: bool = False,
) -> uuid.UUID:
    """Link an account to a school with one role; return the membership id.

    is_primary is only named when making a principal: school users have no
    permission on that column at all (only the platform names a principal).
    """
    values = {"user_id": user_id, "school_id": school_id, "role": role}
    statement = (
        "insert into school_memberships (user_id, school_id, role, is_primary)"
        " values (:user_id, :school_id, :role, true) returning id"
        if is_primary
        else "insert into school_memberships (user_id, school_id, role)"
        " values (:user_id, :school_id, :role) returning id"
    )
    membership_id: uuid.UUID = session.scalar(text(statement), values)
    return membership_id


def parent_accepts_link(session: Session, parent_id: uuid.UUID, school_id: uuid.UUID) -> uuid.UUID:
    """The parent links their existing account to another school (D-138).

    Only the parent can do this, so the database must know the parent is the
    one acting: the membership is added with the parent as the signed-in user.
    """
    use_context(session, user_id=parent_id)
    membership_id = add_membership(session, parent_id, school_id, "parent")
    use_context(session)
    return membership_id
