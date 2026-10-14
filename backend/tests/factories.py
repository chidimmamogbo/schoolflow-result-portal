"""Builders for fictional test data, written as plain SQL.

Like a WordPress test that calls wp_insert_post() to set up a page before
checking something, these functions insert a complete, valid record so each
test can focus on the one rule it checks. All names and codes are fictional.
"""

import json
import secrets
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from schoolflow_api.grading.defaults import (
    DEFAULT_COMPONENTS,
    TRAIT_KEY,
    Component,
    GradeBand,
)
from schoolflow_api.ratings.defaults import ATTENTION_POINT, RATING_SCALE
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


# --- school structure (BUILD_PROMPT 9.1 item 3) ---------------------------------


def create_session(session: Session, school_id: uuid.UUID, name: str = "2026/2027") -> uuid.UUID:
    """An academic session from September to July."""
    # Bad names are allowed in, so tests can check the database refuses them.
    first_year = int(name[:4]) if name[:4].isdigit() else 2026
    session_id: uuid.UUID = session.scalar(
        text(
            "insert into academic_sessions (school_id, name, starts_on, ends_on)"
            " values (:school_id, :name, make_date(:year, 9, 1), make_date(:year + 1, 7, 31))"
            " returning id"
        ),
        {"school_id": school_id, "name": name, "year": first_year},
    )
    return session_id


def create_term(
    session: Session,
    school_id: uuid.UUID,
    session_id: uuid.UUID,
    term_number: int = 1,
    *,
    is_active: bool = False,
) -> uuid.UUID:
    """First Term 8 Sep to 11 Dec 2026, next term begins 5 Jan 2027 (design brief section 12)."""
    term_id: uuid.UUID = session.scalar(
        text(
            "insert into terms (school_id, session_id, term_number, starts_on, ends_on,"
            " next_term_begins, is_active) values (:school_id, :session_id, :term_number,"
            " date '2026-09-08' + (:term_number - 1) * 120, date '2026-12-11'"
            " + (:term_number - 1) * 120, date '2027-01-05' + (:term_number - 1) * 120,"
            " :is_active) returning id"
        ),
        {
            "school_id": school_id,
            "session_id": session_id,
            "term_number": term_number,
            "is_active": is_active,
        },
    )
    return term_id


def create_class(session: Session, school_id: uuid.UUID, level: str, name: str) -> uuid.UUID:
    class_id: uuid.UUID = session.scalar(
        text(
            "insert into classes (school_id, level, name) values (:school_id, :level, :name)"
            " returning id"
        ),
        {"school_id": school_id, "level": level, "name": name},
    )
    return class_id


def create_arm(
    session: Session, school_id: uuid.UUID, class_id: uuid.UUID, name: str = "A"
) -> uuid.UUID:
    arm_id: uuid.UUID = session.scalar(
        text(
            "insert into class_arms (school_id, class_id, name)"
            " values (:school_id, :class_id, :name) returning id"
        ),
        {"school_id": school_id, "class_id": class_id, "name": name},
    )
    return arm_id


def create_department(session: Session, school_id: uuid.UUID, name: str) -> uuid.UUID:
    department_id: uuid.UUID = session.scalar(
        text("insert into departments (school_id, name) values (:school_id, :name) returning id"),
        {"school_id": school_id, "name": name},
    )
    return department_id


def create_subject(
    session: Session,
    school_id: uuid.UUID,
    name: str,
    *,
    department_id: uuid.UUID | None = None,
    category: str | None = None,
) -> uuid.UUID:
    subject_id: uuid.UUID = session.scalar(
        text(
            "insert into subjects (school_id, name, department_id, category)"
            " values (:school_id, :name, :department_id, :category) returning id"
        ),
        {
            "school_id": school_id,
            "name": name,
            "department_id": department_id,
            "category": category,
        },
    )
    return subject_id


def add_arm_subject(
    session: Session, school_id: uuid.UUID, arm_id: uuid.UUID, subject_id: uuid.UUID
) -> uuid.UUID:
    link_id: uuid.UUID = session.scalar(
        text(
            "insert into arm_subjects (school_id, arm_id, subject_id)"
            " values (:school_id, :arm_id, :subject_id) returning id"
        ),
        {"school_id": school_id, "arm_id": arm_id, "subject_id": subject_id},
    )
    return link_id


# --- pupils and parents (BUILD_PROMPT 9.1 item 4) --------------------------------


def create_student(
    session: Session,
    school_id: uuid.UUID,
    admission_number: str,
    surname: str,
    first_name: str,
    *,
    gender: str = "male",
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    student_id: uuid.UUID = session.scalar(
        text(
            "insert into students (school_id, admission_number, surname, first_name, gender,"
            " user_id) values (:school_id, :admission_number, :surname, :first_name, :gender,"
            " :user_id) returning id"
        ),
        {
            "school_id": school_id,
            "admission_number": admission_number,
            "surname": surname,
            "first_name": first_name,
            "gender": gender,
            "user_id": user_id,
        },
    )
    return student_id


def create_guardian(
    session: Session,
    school_id: uuid.UUID,
    full_name: str,
    *,
    email: str | None = None,
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    guardian_id: uuid.UUID = session.scalar(
        text(
            "insert into guardians (school_id, full_name, email, user_id)"
            " values (:school_id, :full_name, :email, :user_id) returning id"
        ),
        {"school_id": school_id, "full_name": full_name, "email": email, "user_id": user_id},
    )
    return guardian_id


def link_ward(
    session: Session,
    school_id: uuid.UUID,
    guardian_id: uuid.UUID,
    student_id: uuid.UUID,
    relationship: str = "Father",
) -> uuid.UUID:
    link_id: uuid.UUID = session.scalar(
        text(
            "insert into guardian_students (school_id, guardian_id, student_id, relationship)"
            " values (:school_id, :guardian_id, :student_id, :relationship) returning id"
        ),
        {
            "school_id": school_id,
            "guardian_id": guardian_id,
            "student_id": student_id,
            "relationship": relationship,
        },
    )
    return link_id


def create_link_request(
    session: Session,
    school_id: uuid.UUID,
    guardian_id: uuid.UUID,
    email: str,
    token_hash: bytes | None = None,
) -> uuid.UUID:
    """A school's request for a parent to link their account (D-138, D-140), 14 days."""
    request_id: uuid.UUID = session.scalar(
        text(
            "insert into parent_link_requests (school_id, guardian_id, email, token_hash,"
            " expires_at) values (:school_id, :guardian_id, :email, :token_hash,"
            " now() + interval '14 days') returning id"
        ),
        {
            "school_id": school_id,
            "guardian_id": guardian_id,
            "email": email,
            "token_hash": secrets.token_bytes(32) if token_hash is None else token_hash,
        },
    )
    return request_id


def enrol(
    session: Session,
    school_id: uuid.UUID,
    student_id: uuid.UUID,
    session_id: uuid.UUID,
    arm_id: uuid.UUID,
) -> uuid.UUID:
    enrolment_id: uuid.UUID = session.scalar(
        text(
            "insert into enrolments (school_id, student_id, session_id, arm_id)"
            " values (:school_id, :student_id, :session_id, :arm_id) returning id"
        ),
        {
            "school_id": school_id,
            "student_id": student_id,
            "session_id": session_id,
            "arm_id": arm_id,
        },
    )
    return enrolment_id


def add_student_subject(
    session: Session, school_id: uuid.UUID, enrolment_id: uuid.UUID, subject_id: uuid.UUID
) -> uuid.UUID:
    link_id: uuid.UUID = session.scalar(
        text(
            "insert into student_subjects (school_id, enrolment_id, subject_id)"
            " values (:school_id, :enrolment_id, :subject_id) returning id"
        ),
        {"school_id": school_id, "enrolment_id": enrolment_id, "subject_id": subject_id},
    )
    return link_id


# --- staff assignments (BUILD_PROMPT 9.1 item 4) ---------------------------------


def assign_teacher(
    session: Session,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    *,
    form_teacher: bool = False,
    teaches_all_subjects: bool = False,
) -> uuid.UUID:
    """A subject in an arm, or (with no subject) the arm's form or class teacher."""
    assignment_id: uuid.UUID = session.scalar(
        text(
            "insert into teacher_assignments (school_id, teacher_id, arm_id, subject_id,"
            " is_form_teacher, teaches_all_subjects) values (:school_id, :teacher_id, :arm_id,"
            " :subject_id, :form_teacher, :teaches_all) returning id"
        ),
        {
            "school_id": school_id,
            "teacher_id": teacher_id,
            "arm_id": arm_id,
            "subject_id": subject_id,
            "form_teacher": form_teacher,
            "teaches_all": teaches_all_subjects,
        },
    )
    return assignment_id


def add_assistant(
    session: Session, school_id: uuid.UUID, arm_id: uuid.UUID, assistant_id: uuid.UUID
) -> uuid.UUID:
    link_id: uuid.UUID = session.scalar(
        text(
            "insert into class_assistants (school_id, arm_id, assistant_id)"
            " values (:school_id, :arm_id, :assistant_id) returning id"
        ),
        {"school_id": school_id, "arm_id": arm_id, "assistant_id": assistant_id},
    )
    return link_id


def add_reviewer_scope(
    session: Session,
    school_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    *,
    department_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
) -> uuid.UUID:
    scope_id: uuid.UUID = session.scalar(
        text(
            "insert into reviewer_scopes (school_id, reviewer_id, department_id, subject_id,"
            " class_id) values (:school_id, :reviewer_id, :department_id, :subject_id,"
            " :class_id) returning id"
        ),
        {
            "school_id": school_id,
            "reviewer_id": reviewer_id,
            "department_id": department_id,
            "subject_id": subject_id,
            "class_id": class_id,
        },
    )
    return scope_id


# --- grading and assessment set-up (BUILD_PROMPT 9.1 item 5) ---------------------


def add_grade_bands(
    session: Session, school_id: uuid.UUID, level: str, bands: Iterable[GradeBand]
) -> None:
    for band in bands:
        session.execute(
            text(
                "insert into grade_bands (school_id, level, grade, min_score, max_score, remark)"
                " values (:school_id, :level, :grade, :min_score, :max_score, :remark)"
            ),
            {"school_id": school_id, "level": level, **band._asdict()},
        )


def add_remark_band(
    session: Session,
    school_id: uuid.UUID,
    level: str,
    min_score: int,
    max_score: int,
    comments: list[str],
) -> uuid.UUID:
    band_id: uuid.UUID = session.scalar(
        text(
            "insert into remark_bands (school_id, level, min_score, max_score, comments)"
            " values (:school_id, :level, :min_score, :max_score, :comments) returning id"
        ),
        {
            "school_id": school_id,
            "level": level,
            "min_score": min_score,
            "max_score": max_score,
            "comments": comments,
        },
    )
    return band_id


def create_structure(
    session: Session,
    school_id: uuid.UUID,
    level: str,
    term_id: uuid.UUID,
    components: Iterable[Component] = DEFAULT_COMPONENTS,
    *,
    mode: str = "scores",
) -> uuid.UUID:
    """An assessment structure for a level and term, with its components in order."""
    structure_id: uuid.UUID = session.scalar(
        text(
            "insert into assessment_structures (school_id, level, term_id, assessment_mode)"
            " values (:school_id, :level, :term_id, :mode) returning id"
        ),
        {"school_id": school_id, "level": level, "term_id": term_id, "mode": mode},
    )
    for position, component in enumerate(components, start=1):
        add_component(session, school_id, structure_id, position, component)
    return structure_id


def add_component(
    session: Session,
    school_id: uuid.UUID,
    structure_id: uuid.UUID,
    position: int,
    component: Component,
) -> uuid.UUID:
    component_id: uuid.UUID = session.scalar(
        text(
            "insert into assessment_components (school_id, structure_id, position, name, label,"
            " max_score) values (:school_id, :structure_id, :position, :name, :label,"
            " :max_score) returning id"
        ),
        {
            "school_id": school_id,
            "structure_id": structure_id,
            "position": position,
            **component._asdict(),
        },
    )
    return component_id


def add_trait(
    session: Session, school_id: uuid.UUID, domain: str, name: str, position: int
) -> uuid.UUID:
    trait_id: uuid.UUID = session.scalar(
        text(
            "insert into rating_traits (school_id, domain, name, position)"
            " values (:school_id, :domain, :name, :position) returning id"
        ),
        {"school_id": school_id, "domain": domain, "name": name, "position": position},
    )
    return trait_id


def add_trait_key(session: Session, school_id: uuid.UUID) -> None:
    for value, label in TRAIT_KEY.items():
        session.execute(
            text(
                "insert into trait_scale_points (school_id, value, label)"
                " values (:school_id, :value, :label)"
            ),
            {"school_id": school_id, "value": value, "label": label},
        )


# --- result sheets and scores (BUILD_PROMPT 9.1 item 6) -------------------------------


def create_sheet(
    session: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    arm_id: uuid.UUID,
    structure_id: uuid.UUID,
    subject_id: uuid.UUID,
) -> uuid.UUID:
    """A score sheet for one subject in one arm for one term (it starts as a draft)."""
    sheet_id: uuid.UUID = session.scalar(
        text(
            "insert into result_sheets (school_id, term_id, arm_id, structure_id, subject_id)"
            " values (:school_id, :term_id, :arm_id, :structure_id, :subject_id) returning id"
        ),
        {
            "school_id": school_id,
            "term_id": term_id,
            "arm_id": arm_id,
            "structure_id": structure_id,
            "subject_id": subject_id,
        },
    )
    return sheet_id


def component_ids(session: Session, structure_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """The structure's components by label, for example {"CA1": ..., "Exam": ...}."""
    return {
        label: component_id
        for label, component_id in session.execute(
            text("select label, id from assessment_components where structure_id = :id"),
            {"id": structure_id},
        )
    }


def enter_score(
    session: Session,
    school_id: uuid.UUID,
    sheet_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    component_id: uuid.UUID,
    value: int,
) -> uuid.UUID:
    """Save one score; the signed-in user (use_context) is recorded as its author."""
    score_id: uuid.UUID = session.scalar(
        text(
            "insert into scores (school_id, sheet_id, enrolment_id, component_id, value)"
            " values (:school_id, :sheet_id, :enrolment_id, :component_id, :value) returning id"
        ),
        {
            "school_id": school_id,
            "sheet_id": sheet_id,
            "enrolment_id": enrolment_id,
            "component_id": component_id,
            "value": value,
        },
    )
    return score_id


def move_sheet(
    session: Session,
    sheet_id: uuid.UUID,
    status: str,
    *,
    comment: str | None = None,
    reopen: bool = False,
) -> None:
    """Move a sheet along its workflow as the signed-in user (use_context)."""
    session.execute(
        text(
            "update result_sheets set status = :status, status_comment = :comment,"
            " revision = revision + :step where id = :id"
        ),
        {"status": status, "comment": comment, "step": 1 if reopen else 0, "id": sheet_id},
    )


# --- skill ratings (BUILD_PROMPT 9.1 item 6a) -------------------------------------


def create_learning_area(
    session: Session, school_id: uuid.UUID, level: str, name: str, position: int = 1
) -> uuid.UUID:
    area_id: uuid.UUID = session.scalar(
        text(
            "insert into learning_areas (school_id, level, name, position)"
            " values (:school_id, :level, :name, :position) returning id"
        ),
        {"school_id": school_id, "level": level, "name": name, "position": position},
    )
    return area_id


def assign_area_to_class(
    session: Session, school_id: uuid.UUID, class_id: uuid.UUID, area_id: uuid.UUID
) -> uuid.UUID:
    link_id: uuid.UUID = session.scalar(
        text(
            "insert into class_learning_areas (school_id, class_id, learning_area_id)"
            " values (:school_id, :class_id, :area_id) returning id"
        ),
        {"school_id": school_id, "class_id": class_id, "area_id": area_id},
    )
    return link_id


def create_skill(
    session: Session, school_id: uuid.UUID, area_id: uuid.UUID, name: str, position: int = 1
) -> uuid.UUID:
    skill_id: uuid.UUID = session.scalar(
        text(
            "insert into skills (school_id, learning_area_id, name, position)"
            " values (:school_id, :area_id, :name, :position) returning id"
        ),
        {"school_id": school_id, "area_id": area_id, "name": name, "position": position},
    )
    return skill_id


def create_rating_scale(session: Session, school_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """The default five-point scale, best first, with Needs improvement as the attention point."""
    scale_id: uuid.UUID = session.scalar(
        text("insert into rating_scales (school_id) values (:school_id) returning id"),
        {"school_id": school_id},
    )
    points: dict[str, uuid.UUID] = {}
    for position, point in enumerate(RATING_SCALE, start=1):
        points[point.code] = session.scalar(
            text(
                "insert into rating_scale_points (school_id, scale_id, position, name, code,"
                " is_attention) values (:school_id, :scale_id, :position, :name, :code,"
                " :is_attention) returning id"
            ),
            {
                "school_id": school_id,
                "scale_id": scale_id,
                "position": position,
                "name": point.name,
                "code": point.code,
                "is_attention": point.code == ATTENTION_POINT,
            },
        )
    return points


def create_rating_sheet(
    session: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    arm_id: uuid.UUID,
    structure_id: uuid.UUID,
    area_id: uuid.UUID,
) -> uuid.UUID:
    """A rating sheet for one learning area in one arm for one term (F26 rule 3)."""
    sheet_id: uuid.UUID = session.scalar(
        text(
            "insert into result_sheets (school_id, term_id, arm_id, structure_id,"
            " learning_area_id) values (:school_id, :term_id, :arm_id, :structure_id,"
            " :area_id) returning id"
        ),
        {
            "school_id": school_id,
            "term_id": term_id,
            "arm_id": arm_id,
            "structure_id": structure_id,
            "area_id": area_id,
        },
    )
    return sheet_id


def rate(
    session: Session,
    school_id: uuid.UUID,
    sheet_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    skill_id: uuid.UUID,
    point_id: uuid.UUID,
) -> uuid.UUID:
    """Save one skill rating; the signed-in user (use_context) is its author."""
    rating_id: uuid.UUID = session.scalar(
        text(
            "insert into skill_ratings (school_id, sheet_id, enrolment_id, skill_id, point_id)"
            " values (:school_id, :sheet_id, :enrolment_id, :skill_id, :point_id) returning id"
        ),
        {
            "school_id": school_id,
            "sheet_id": sheet_id,
            "enrolment_id": enrolment_id,
            "skill_id": skill_id,
            "point_id": point_id,
        },
    )
    return rating_id


def assign_area_teacher(
    session: Session,
    school_id: uuid.UUID,
    teacher_id: uuid.UUID,
    arm_id: uuid.UUID,
    area_id: uuid.UUID,
) -> uuid.UUID:
    """A specialist teacher for one learning area in one arm."""
    assignment_id: uuid.UUID = session.scalar(
        text(
            "insert into teacher_assignments (school_id, teacher_id, arm_id, learning_area_id)"
            " values (:school_id, :teacher_id, :arm_id, :area_id) returning id"
        ),
        {"school_id": school_id, "teacher_id": teacher_id, "arm_id": arm_id, "area_id": area_id},
    )
    return assignment_id


def comment_on_area(
    session: Session,
    school_id: uuid.UUID,
    sheet_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    comment: str,
) -> uuid.UUID:
    """The optional comment on one pupil's learning area; the signed-in user is its author."""
    comment_id: uuid.UUID = session.scalar(
        text(
            "insert into area_comments (school_id, sheet_id, enrolment_id, comment)"
            " values (:school_id, :sheet_id, :enrolment_id, :comment) returning id"
        ),
        {
            "school_id": school_id,
            "sheet_id": sheet_id,
            "enrolment_id": enrolment_id,
            "comment": comment,
        },
    )
    return comment_id


# --- form teacher class sections (BUILD_PROMPT 9.1 item 6b) -------------------------


def create_class_section(
    session: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    arm_id: uuid.UUID,
    times_school_opened: int | None = None,
) -> uuid.UUID:
    """The form teacher's class sections for one arm and term (they start Open)."""
    section_id: uuid.UUID = session.scalar(
        text(
            "insert into class_report_sections (school_id, term_id, arm_id, times_school_opened)"
            " values (:school_id, :term_id, :arm_id, :opened) returning id"
        ),
        {
            "school_id": school_id,
            "term_id": term_id,
            "arm_id": arm_id,
            "opened": times_school_opened,
        },
    )
    return section_id


def move_section(
    session: Session,
    section_id: uuid.UUID,
    status: str,
    *,
    comment: str | None = None,
    reopen: bool = False,
) -> None:
    """Move the class sections along their workflow as the signed-in user (use_context)."""
    session.execute(
        text(
            "update class_report_sections set status = :status, status_comment = :comment,"
            " revision = revision + :step where id = :id"
        ),
        {"status": status, "comment": comment, "step": 1 if reopen else 0, "id": section_id},
    )


def write_term_entry(
    session: Session,
    school_id: uuid.UUID,
    section_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    *,
    comment: str | None = None,
    times_present: int | None = None,
    head_comment: str | None = None,
) -> uuid.UUID:
    """One pupil's term entry; the signed-in user (use_context) is recorded as its author."""
    entry_id: uuid.UUID = session.scalar(
        text(
            "insert into student_term_entries (school_id, section_id, enrolment_id,"
            " form_teacher_comment, times_present, head_comment) values (:school_id,"
            " :section_id, :enrolment_id, :comment, :present, :head_comment) returning id"
        ),
        {
            "school_id": school_id,
            "section_id": section_id,
            "enrolment_id": enrolment_id,
            "comment": comment,
            "present": times_present,
            "head_comment": head_comment,
        },
    )
    return entry_id


def rate_trait(
    session: Session, school_id: uuid.UUID, entry_id: uuid.UUID, trait_id: uuid.UUID, value: int
) -> uuid.UUID:
    """One affective or psychomotor rating (1 to 5) on a pupil's term entry."""
    rating_id: uuid.UUID = session.scalar(
        text(
            "insert into student_trait_ratings (school_id, entry_id, trait_id, value)"
            " values (:school_id, :entry_id, :trait_id, :value) returning id"
        ),
        {"school_id": school_id, "entry_id": entry_id, "trait_id": trait_id, "value": value},
    )
    return rating_id


# --- report templates, report documents and attention entries (9.1 item 7) ---------


def create_template(
    session: Session,
    school_id: uuid.UUID,
    level: str,
    *,
    style: str = "modern",
    settings: Any = None,
) -> uuid.UUID:
    """Save a report template for a level; the database numbers the version."""
    template_id: uuid.UUID = session.scalar(
        text(
            "insert into report_templates (school_id, level, style, settings)"
            " values (:school_id, :level, :style, cast(:settings as jsonb)) returning id"
        ),
        {
            "school_id": school_id,
            "level": level,
            "style": style,
            "settings": json.dumps({} if settings is None else settings),
        },
    )
    return template_id


def publish_report(
    session: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    arm_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    report_code: str,
    verification_code: str,
    snapshot: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Store one pupil's published report; the signed-in user (use_context) publishes it."""
    report_id: uuid.UUID = session.scalar(
        text(
            "insert into report_documents (school_id, term_id, arm_id, enrolment_id,"
            " template_id, report_code, verification_code, snapshot, calculation_version)"
            " values (:school_id, :term_id, :arm_id, :enrolment_id, :template_id, :report_code,"
            " :verification_code, cast(:snapshot as jsonb), '1') returning id"
        ),
        {
            "school_id": school_id,
            "term_id": term_id,
            "arm_id": arm_id,
            "enrolment_id": enrolment_id,
            "template_id": template_id,
            "report_code": report_code,
            "verification_code": verification_code,
            "snapshot": json.dumps(snapshot or {"fictional": True}),
        },
    )
    return report_id


def add_attention_entry(
    session: Session,
    school_id: uuid.UUID,
    report_id: uuid.UUID,
    kind: str,
    *,
    subject_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    score: int | None = None,
    grade: str | None = None,
    pass_mark: int | None = None,
    failed_count: int | None = None,
    average: Decimal | None = None,
) -> uuid.UUID:
    """One Students needing attention finding from a published report (F23)."""
    entry_id: uuid.UUID = session.scalar(
        text(
            "insert into attention_entries (school_id, report_document_id, kind, subject_id,"
            " teacher_id, score, grade, pass_mark, failed_count, average) values (:school_id,"
            " :report_id, :kind, :subject_id, :teacher_id, :score, :grade, :pass_mark,"
            " :failed_count, :average) returning id"
        ),
        {
            "school_id": school_id,
            "report_id": report_id,
            "kind": kind,
            "subject_id": subject_id,
            "teacher_id": teacher_id,
            "score": score,
            "grade": grade,
            "pass_mark": pass_mark,
            "failed_count": failed_count,
            "average": average,
        },
    )
    return entry_id


# --- uploaded files and correction requests (BUILD_PROMPT 9.1 item 8) --------------


def store_file(
    session: Session,
    school_id: uuid.UUID,
    *,
    purpose: str = "correction_attachment",
    content_type: str = "image/jpeg",
    size_bytes: int = 250_000,
    storage_key: str | None = None,
    original_name: str = "exam-script.jpg",
) -> uuid.UUID:
    """Record one uploaded file (the bytes live in storage); the signed-in user uploaded it."""
    file_id: uuid.UUID = session.scalar(
        text(
            "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
            " sha256, original_name) values (:school_id, :purpose, :storage_key,"
            " :content_type, :size_bytes, :sha256, :original_name) returning id"
        ),
        {
            "school_id": school_id,
            "purpose": purpose,
            "storage_key": storage_key or f"schools/{school_id}/{purpose}/{uuid.uuid4().hex}",
            "content_type": content_type,
            "size_bytes": size_bytes,
            "sha256": secrets.token_bytes(32),
            "original_name": original_name,
        },
    )
    return file_id


def create_correction_request(
    session: Session,
    school_id: uuid.UUID,
    report_id: uuid.UUID,
    *,
    subject_id: uuid.UUID | None = None,
    issue_type: str = "score",
    explanation: str = "His Mathematics exam script shows 51, not 47.",
) -> uuid.UUID:
    """A "Report a problem" request on a published report; the signed-in user sends it."""
    request_id: uuid.UUID = session.scalar(
        text(
            "insert into correction_requests (school_id, report_document_id, subject_id,"
            " issue_type, explanation) values (:school_id, :report_id, :subject_id,"
            " :issue_type, :explanation) returning id"
        ),
        {
            "school_id": school_id,
            "report_id": report_id,
            "subject_id": subject_id,
            "issue_type": issue_type,
            "explanation": explanation,
        },
    )
    return request_id


def move_correction(
    session: Session,
    request_id: uuid.UUID,
    status: str,
    *,
    message: str | None = None,
    corrected_report_id: uuid.UUID | None = None,
) -> None:
    """Move a correction request along its workflow as the signed-in user."""
    session.execute(
        text(
            "update correction_requests set status = :status, status_message = :message,"
            " corrected_report_id = :corrected where id = :id"
        ),
        {
            "status": status,
            "message": message,
            "corrected": corrected_report_id,
            "id": request_id,
        },
    )


def attach_file(
    session: Session, school_id: uuid.UUID, request_id: uuid.UUID, file_id: uuid.UUID
) -> uuid.UUID:
    attachment_id: uuid.UUID = session.scalar(
        text(
            "insert into correction_attachments (school_id, request_id, file_id)"
            " values (:school_id, :request_id, :file_id) returning id"
        ),
        {"school_id": school_id, "request_id": request_id, "file_id": file_id},
    )
    return attachment_id
