"""Tables for skill ratings (SPEC F26 rules 1 to 3; BUILD_PROMPT 9.1 item 6a).

learning_areas: per level, the areas a Skill ratings level is rated in
("Number work"), in order; a name is used once in a level.
class_learning_areas: which classes rate which areas (F26 rule 1, "assigned
to classes like subjects"); an area goes only to classes of its own level.
skills: what is rated in each area ("Counts 1 to 20"). A skill is retired,
not deleted, so ratings already given keep it.
rating_scales and rating_scale_points: one scale per school, best point
first, each point with a word, a short code and an optional description.
Exactly one point is the attention point: pupils rated at or below it appear
in Students needing attention (F23 rule 8).
skill_ratings: one rating per pupil per skill on a rating sheet (a
result_sheets row for a learning area), each with its author.
area_comments: the optional short comment per pupil per area.

No totals, averages, grades or positions exist in Skill ratings mode (F26
rule 5). Rules that read other tables are triggers in migration 12.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin

# Names are compared without caring about capitals: "Number work" and "number WORK" clash.
UNIQUE_LOWER_NAME = text("lower(name)")
DESCRIPTION_VALID = "btrim(description) <> '' AND char_length(description) <= 200"


class LearningArea(IdMixin, TimestampMixin, Base):
    __tablename__ = "learning_areas"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        # One of the school's four level rows; a trigger also refuses a level that is off.
        ForeignKeyConstraint(
            ["school_id", "level"], ["school_levels.school_id", "school_levels.level"]
        ),
        Index(
            "ix_learning_areas_unique_name", "school_id", "level", UNIQUE_LOWER_NAME, unique=True
        ),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 60", name="name_valid"),
        CheckConstraint("position >= 1", name="position_positive"),
    )

    school_id: Mapped[uuid.UUID]
    level: Mapped[str]
    name: Mapped[str]
    # The order of the areas on sheets and on the Skills report card.
    position: Mapped[int] = mapped_column(SmallInteger)


class ClassLearningArea(IdMixin, TimestampMixin, Base):
    """A learning area a class rates: one rating sheet per area per arm per term."""

    __tablename__ = "class_learning_areas"
    __table_args__ = (
        UniqueConstraint("class_id", "learning_area_id"),
        ForeignKeyConstraint(["class_id", "school_id"], ["classes.id", "classes.school_id"]),
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        Index("ix_class_learning_areas_learning_area_id", "learning_area_id"),
    )

    school_id: Mapped[uuid.UUID]
    class_id: Mapped[uuid.UUID]
    learning_area_id: Mapped[uuid.UUID]


class Skill(IdMixin, TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        Index("ix_skills_unique_name", "learning_area_id", UNIQUE_LOWER_NAME, unique=True),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 80", name="name_valid"),
        CheckConstraint(DESCRIPTION_VALID, name="description_valid"),
        CheckConstraint("position >= 1", name="position_positive"),
    )

    school_id: Mapped[uuid.UUID]
    learning_area_id: Mapped[uuid.UUID]
    name: Mapped[str]
    # Shown when "Show skill descriptions" is on (F26 rule 6).
    description: Mapped[str | None]
    position: Mapped[int] = mapped_column(SmallInteger)
    # A retired skill is no longer rated; ratings already given keep it.
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class RatingScale(IdMixin, TimestampMixin, Base):
    """The school's rating scale (F26 rule 2): one per school, its points below."""

    __tablename__ = "rating_scales"
    __table_args__ = (
        UniqueConstraint("school_id"),
        UniqueConstraint("id", "school_id"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))


class RatingScalePoint(IdMixin, TimestampMixin, Base):
    """One point of the scale, for example Very good (VG)."""

    __tablename__ = "rating_scale_points"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        # Checked at save, so points can be reordered or recoded in one go.
        UniqueConstraint("scale_id", "position", deferrable=True, initially="DEFERRED"),
        UniqueConstraint("scale_id", "code", deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(
            ["scale_id", "school_id"], ["rating_scales.id", "rating_scales.school_id"]
        ),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 30", name="name_valid"),
        # E, VG, NI ...: a capital letter and up to three more characters, like a grade.
        CheckConstraint("code ~ '^[A-Z][A-Z0-9+-]{0,3}$'", name="code_format"),
        CheckConstraint(DESCRIPTION_VALID, name="description_valid"),
    )

    school_id: Mapped[uuid.UUID]
    scale_id: Mapped[uuid.UUID]
    # 1 is the best point (the design: "List the best point first").
    position: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str]  # the word, "Very good"
    code: Mapped[str]  # the short code, "VG"
    description: Mapped[str | None]
    # Exactly one point of a scale is the attention point (checked at save, migration 12).
    is_attention: Mapped[bool] = mapped_column(server_default=text("false"))


class SkillRating(IdMixin, TimestampMixin, Base):
    __tablename__ = "skill_ratings"
    __table_args__ = (
        UniqueConstraint("sheet_id", "enrolment_id", "skill_id"),
        ForeignKeyConstraint(
            ["sheet_id", "school_id"], ["result_sheets.id", "result_sheets.school_id"]
        ),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        ForeignKeyConstraint(["skill_id", "school_id"], ["skills.id", "skills.school_id"]),
        ForeignKeyConstraint(
            ["point_id", "school_id"], ["rating_scale_points.id", "rating_scale_points.school_id"]
        ),
        Index("ix_skill_ratings_enrolment_id", "enrolment_id"),
        CheckConstraint(
            "btrim(change_reason) <> '' AND char_length(change_reason) <= 300",
            name="change_reason_valid",
        ),
    )

    school_id: Mapped[uuid.UUID]
    sheet_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    skill_id: Mapped[uuid.UUID]
    point_id: Mapped[uuid.UUID]
    # Set by the database from the signed-in user, never by the request.
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Required once the sheet has been submitted (D-143), as for scores.
    change_reason: Mapped[str | None]


class AreaComment(IdMixin, TimestampMixin, Base):
    """The optional comment on one pupil's learning area (F26 rule 3)."""

    __tablename__ = "area_comments"
    __table_args__ = (
        UniqueConstraint("sheet_id", "enrolment_id"),
        ForeignKeyConstraint(
            ["sheet_id", "school_id"], ["result_sheets.id", "result_sheets.school_id"]
        ),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        CheckConstraint(
            "btrim(comment) <> '' AND char_length(comment) <= 300", name="comment_valid"
        ),
    )

    school_id: Mapped[uuid.UUID]
    sheet_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    comment: Mapped[str]
    # Set by the database from the signed-in user, never by the request.
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
