"""Copying the platform's grading defaults into a school, once (D-141, D-145; D-165).

The first time anyone in a school opens its grading set-up, the defaults
from grading/defaults.py and ratings/defaults.py are copied in as the
school's own rows: grading bands for all four levels, the pass mark, the
affective and psychomotor traits with their 1 to 5 key, the rating scale and,
when Nursery is on, the default learning areas with their sample skills.

The school_settings row is the marker that the copy was made, so a school
that deletes a learning area or a trait never sees it come back. Like the
first run of a WordPress plugin that adds its default options.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.grading.defaults import (
    AFFECTIVE_TRAITS,
    DEFAULT_PASS_MARK,
    PRIMARY_GRADE_BANDS,
    PSYCHOMOTOR_TRAITS,
    SECONDARY_GRADE_BANDS,
    TRAIT_KEY,
)
from schoolflow_api.ratings.defaults import ATTENTION_POINT, LEARNING_AREAS, RATING_SCALE
from schoolflow_api.schools.models import Level

BANDS_FOR_LEVEL = {
    Level.NURSERY: PRIMARY_GRADE_BANDS,
    Level.PRIMARY: PRIMARY_GRADE_BANDS,
    Level.JUNIOR_SECONDARY: SECONDARY_GRADE_BANDS,
    Level.SENIOR_SECONDARY: SECONDARY_GRADE_BANDS,
}


def ensure_defaults(session: Session, school_id: uuid.UUID, actor_role: str) -> None:
    """Copy the defaults into the school unless that was already done."""
    done = session.scalar(
        text("select exists (select 1 from school_settings where school_id = :s)"),
        {"s": school_id},
    )
    if done:
        return
    session.execute(
        text("insert into school_settings (school_id, pass_mark) values (:s, :p)"),
        {"s": school_id, "p": DEFAULT_PASS_MARK},
    )
    for level, bands in BANDS_FOR_LEVEL.items():
        for band in bands:
            session.execute(
                text(
                    "insert into grade_bands (school_id, level, grade, min_score, max_score,"
                    " remark) values (:s, :l, :g, :lo, :hi, :r)"
                ),
                {
                    "s": school_id,
                    "l": level.value,
                    "g": band.grade,
                    "lo": band.min_score,
                    "hi": band.max_score,
                    "r": band.remark,
                },
            )
    for domain, names in (("affective", AFFECTIVE_TRAITS), ("psychomotor", PSYCHOMOTOR_TRAITS)):
        for position, name in enumerate(names, start=1):
            session.execute(
                text(
                    "insert into rating_traits (school_id, domain, name, position)"
                    " values (:s, :d, :n, :p)"
                ),
                {"s": school_id, "d": domain, "n": name, "p": position},
            )
    for value, label in TRAIT_KEY.items():
        session.execute(
            text("insert into trait_scale_points (school_id, value, label) values (:s, :v, :l)"),
            {"s": school_id, "v": value, "l": label},
        )
    scale_id = session.scalar(
        text("insert into rating_scales (school_id) values (:s) returning id"), {"s": school_id}
    )
    for position, point in enumerate(RATING_SCALE, start=1):
        session.execute(
            text(
                "insert into rating_scale_points (school_id, scale_id, position, name, code,"
                " is_attention) values (:s, :scale, :p, :n, :c, :a)"
            ),
            {
                "s": school_id,
                "scale": scale_id,
                "p": position,
                "n": point.name,
                "c": point.code,
                "a": point.code == ATTENTION_POINT,
            },
        )
    nursery_on = session.scalar(
        text("select enabled from school_levels where school_id = :s and level = 'nursery'"),
        {"s": school_id},
    )
    if nursery_on:
        for position, (area, skills) in enumerate(LEARNING_AREAS.items(), start=1):
            area_id = session.scalar(
                text(
                    "insert into learning_areas (school_id, level, name, position)"
                    " values (:s, 'nursery', :n, :p) returning id"
                ),
                {"s": school_id, "n": area, "p": position},
            )
            for skill_position, skill in enumerate(skills, start=1):
                session.execute(
                    text(
                        "insert into skills (school_id, learning_area_id, name, position)"
                        " values (:s, :a, :n, :p)"
                    ),
                    {"s": school_id, "a": area_id, "n": skill, "p": skill_position},
                )
    write_audit(session, school_id, actor_role, "grading.defaults")
