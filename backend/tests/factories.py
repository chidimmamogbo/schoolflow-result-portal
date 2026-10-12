"""Builders for fictional test data, written as plain SQL.

Like a WordPress test that calls wp_insert_post() to set up a page before
checking something, these functions insert a complete, valid record so each
test can focus on the one rule it checks. All names and codes are fictional.
"""

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

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
