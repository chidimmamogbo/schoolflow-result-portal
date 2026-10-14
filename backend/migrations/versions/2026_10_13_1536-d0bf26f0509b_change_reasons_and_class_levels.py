"""Migration 13: each change brings its own reason; a used class keeps its level.

Approved CHANGEs "Each score or rating change brings its own reason" and "A
class keeps its level once results work has started" (Chidimma, 2026-10-13,
before item 6b); D-143. Hand-written SQL only (D-023); no table changes:

- check_score() (migration 11) and check_skill_rating() (migration 12) are
  replaced with the same rules plus two. A reason counts only when the change
  gives it: the reason already on the row, left out or repeated word for
  word, counts as none and is cleared, so after a submission the change is
  refused (D-143). And a reason is never changed on its own
  (scores_reason_comes_with_a_change, skill_ratings_reason_comes_with_a_change).
  First-draft changes still need no reason.
- guard_class_level(): a class's level changes only while no arm of the
  class has a result sheet and the class has no learning areas
  (classes_level_fixed_once_used). Migration 6's classes_level_is_on still
  checks that the new level is switched on.

Downgrading puts back migration 11's and migration 12's functions.

Revision ID: d0bf26f0509b
Revises: 3319910af0cf
Create Date: 2026-10-13 15:36:56.274057

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0bf26f0509b"
down_revision: str | Sequence[str] | None = "3319910af0cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCORE_RULE = """
create or replace function check_score() returns trigger
language plpgsql
as $$
declare
    actor uuid;
    sheet_status text;
    sheet_revision int;
    sheet_subject uuid;
    sheet_arm uuid;
    sheet_structure uuid;
    sheet_term uuid;
    maximum int;
begin
    actor := app_current_user_id();
    if actor is null then
        raise exception 'Every score needs a signed-in author.'
            using errcode = 'check_violation',
                  constraint = 'scores_need_an_author';
    end if;

    select s.status, s.revision, s.subject_id, s.arm_id, s.structure_id, s.term_id
      into sheet_status, sheet_revision, sheet_subject, sheet_arm, sheet_structure, sheet_term
      from result_sheets s
     where s.id = case when tg_op = 'DELETE' then old.sheet_id else new.sheet_id end;

    if sheet_status not in ('draft', 'returned_for_correction') then
        raise exception 'This sheet is % and its scores cannot change.', sheet_status
            using errcode = 'check_violation',
                  constraint = 'scores_sheet_is_locked';
    end if;

    if tg_op = 'DELETE' then
        if not (sheet_status = 'draft' and sheet_revision = 1) then
            raise exception 'Scores are removed only while a sheet is its first draft.'
                using errcode = 'check_violation',
                      constraint = 'scores_removed_only_in_first_draft';
        end if;
        return old;
    end if;

    if tg_op = 'INSERT'
       or new.component_id is distinct from old.component_id
       or new.enrolment_id is distinct from old.enrolment_id
    then
        if not exists (
            select 1
              from assessment_components c
             where c.id = new.component_id
               and c.structure_id = sheet_structure
        ) then
            raise exception 'This column is not part of the sheet''s structure.'
                using errcode = 'check_violation',
                      constraint = 'scores_component_in_structure';
        end if;
        if not exists (
            select 1
              from enrolments e
              join terms t on t.id = sheet_term and t.session_id = e.session_id
              join student_subjects ss on ss.enrolment_id = e.id and ss.subject_id = sheet_subject
             where e.id = new.enrolment_id
               and e.arm_id = sheet_arm
        ) then
            raise exception 'This pupil does not take this subject in this arm.'
                using errcode = 'check_violation',
                      constraint = 'scores_student_takes_subject';
        end if;
    end if;

    select c.max_score into maximum from assessment_components c where c.id = new.component_id;
    if new.value > maximum then
        raise exception 'A score cannot be more than the column maximum (%).', maximum
            using errcode = 'check_violation',
                  constraint = 'scores_within_maximum';
    end if;

    if tg_op = 'INSERT' then
        new.entered_by := actor;
        new.updated_by := null;
    else
        new.entered_by := old.entered_by;
        if new.value is distinct from old.value then
            -- A reason counts only when this change gives it.
            if new.change_reason is not distinct from old.change_reason then
                new.change_reason := null;
            end if;
            if (sheet_status = 'returned_for_correction' or sheet_revision > 1)
               and (new.change_reason is null or btrim(new.change_reason) = '')
            then
                raise exception 'Changing a submitted score needs a reason.'
                    using errcode = 'check_violation',
                          constraint = 'scores_change_needs_reason';
            end if;
            new.updated_by := actor;
        elsif new.change_reason is distinct from old.change_reason then
            raise exception 'A reason is given with a change, not edited afterwards.'
                using errcode = 'check_violation',
                      constraint = 'scores_reason_comes_with_a_change';
        end if;
    end if;
    return new;
end
$$;
"""

RATING_RULE = """
create or replace function check_skill_rating() returns trigger
language plpgsql
as $$
declare
    actor uuid;
    sheet_status text;
    sheet_revision int;
    sheet_area uuid;
    sheet_arm uuid;
    sheet_term uuid;
begin
    actor := app_current_user_id();
    if actor is null then
        raise exception 'Every rating needs a signed-in author.'
            using errcode = 'check_violation',
                  constraint = 'skill_ratings_need_an_author';
    end if;

    select s.status, s.revision, s.learning_area_id, s.arm_id, s.term_id
      into sheet_status, sheet_revision, sheet_area, sheet_arm, sheet_term
      from result_sheets s
     where s.id = case when tg_op = 'DELETE' then old.sheet_id else new.sheet_id end;

    if sheet_status not in ('draft', 'returned_for_correction') then
        raise exception 'This sheet is % and its ratings cannot change.', sheet_status
            using errcode = 'check_violation',
                  constraint = 'skill_ratings_sheet_is_locked';
    end if;

    if tg_op = 'DELETE' then
        if not (sheet_status = 'draft' and sheet_revision = 1) then
            raise exception 'Ratings are removed only while a sheet is its first draft.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_removed_only_in_first_draft';
        end if;
        return old;
    end if;

    if tg_op = 'INSERT'
       or new.skill_id is distinct from old.skill_id
       or new.enrolment_id is distinct from old.enrolment_id
    then
        if not exists (
            select 1
              from skills k
             where k.id = new.skill_id
               and k.learning_area_id = sheet_area
               and k.is_active
        ) then
            raise exception 'This is not an active skill of the sheet''s learning area.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_skill_in_area';
        end if;
        if not exists (
            select 1
              from enrolments e
              join terms t on t.id = sheet_term and t.session_id = e.session_id
             where e.id = new.enrolment_id
               and e.arm_id = sheet_arm
        ) then
            raise exception 'This pupil is not in the sheet''s class.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_pupil_in_arm';
        end if;
    end if;

    if tg_op = 'INSERT' then
        new.entered_by := actor;
        new.updated_by := null;
    else
        new.entered_by := old.entered_by;
        if new.point_id is distinct from old.point_id then
            -- A reason counts only when this change gives it.
            if new.change_reason is not distinct from old.change_reason then
                new.change_reason := null;
            end if;
            if (sheet_status = 'returned_for_correction' or sheet_revision > 1)
               and (new.change_reason is null or btrim(new.change_reason) = '')
            then
                raise exception 'Changing a submitted rating needs a reason.'
                    using errcode = 'check_violation',
                          constraint = 'skill_ratings_change_needs_reason';
            end if;
            new.updated_by := actor;
        elsif new.change_reason is distinct from old.change_reason then
            raise exception 'A reason is given with a change, not edited afterwards.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_reason_comes_with_a_change';
        end if;
    end if;
    return new;
end
$$;
"""

CLASS_LEVEL_RULE = """
create function guard_class_level() returns trigger
language plpgsql
as $$
begin
    if new.level is distinct from old.level and (
        exists (
            select 1
              from result_sheets s
              join class_arms a on a.id = s.arm_id
             where a.class_id = old.id
        )
        or exists (
            select 1
              from class_learning_areas cla
             where cla.class_id = old.id
        )
    ) then
        raise exception 'This class already has results work, so its level stays as it is.'
            using errcode = 'check_violation',
                  constraint = 'classes_level_fixed_once_used';
    end if;
    return new;
end
$$;

create trigger classes_level_fixed_once_used
    before update of level on classes
    for each row execute function guard_class_level();
"""

# Migration 11's and migration 12's functions exactly as they were, for the downgrade.
OLD_SCORE_RULE = """
create or replace function check_score() returns trigger
language plpgsql
as $$
declare
    actor uuid;
    sheet_status text;
    sheet_revision int;
    sheet_subject uuid;
    sheet_arm uuid;
    sheet_structure uuid;
    sheet_term uuid;
    maximum int;
begin
    actor := app_current_user_id();
    if actor is null then
        raise exception 'Every score needs a signed-in author.'
            using errcode = 'check_violation',
                  constraint = 'scores_need_an_author';
    end if;

    select s.status, s.revision, s.subject_id, s.arm_id, s.structure_id, s.term_id
      into sheet_status, sheet_revision, sheet_subject, sheet_arm, sheet_structure, sheet_term
      from result_sheets s
     where s.id = case when tg_op = 'DELETE' then old.sheet_id else new.sheet_id end;

    if sheet_status not in ('draft', 'returned_for_correction') then
        raise exception 'This sheet is % and its scores cannot change.', sheet_status
            using errcode = 'check_violation',
                  constraint = 'scores_sheet_is_locked';
    end if;

    if tg_op = 'DELETE' then
        if not (sheet_status = 'draft' and sheet_revision = 1) then
            raise exception 'Scores are removed only while a sheet is its first draft.'
                using errcode = 'check_violation',
                      constraint = 'scores_removed_only_in_first_draft';
        end if;
        return old;
    end if;

    if tg_op = 'INSERT'
       or new.component_id is distinct from old.component_id
       or new.enrolment_id is distinct from old.enrolment_id
    then
        if not exists (
            select 1
              from assessment_components c
             where c.id = new.component_id
               and c.structure_id = sheet_structure
        ) then
            raise exception 'This column is not part of the sheet''s structure.'
                using errcode = 'check_violation',
                      constraint = 'scores_component_in_structure';
        end if;
        if not exists (
            select 1
              from enrolments e
              join terms t on t.id = sheet_term and t.session_id = e.session_id
              join student_subjects ss on ss.enrolment_id = e.id and ss.subject_id = sheet_subject
             where e.id = new.enrolment_id
               and e.arm_id = sheet_arm
        ) then
            raise exception 'This pupil does not take this subject in this arm.'
                using errcode = 'check_violation',
                      constraint = 'scores_student_takes_subject';
        end if;
    end if;

    select c.max_score into maximum from assessment_components c where c.id = new.component_id;
    if new.value > maximum then
        raise exception 'A score cannot be more than the column maximum (%).', maximum
            using errcode = 'check_violation',
                  constraint = 'scores_within_maximum';
    end if;

    if tg_op = 'INSERT' then
        new.entered_by := actor;
        new.updated_by := null;
    else
        new.entered_by := old.entered_by;
        if new.value is distinct from old.value then
            if (sheet_status = 'returned_for_correction' or sheet_revision > 1)
               and (new.change_reason is null or btrim(new.change_reason) = '')
            then
                raise exception 'Changing a submitted score needs a reason.'
                    using errcode = 'check_violation',
                          constraint = 'scores_change_needs_reason';
            end if;
            new.updated_by := actor;
        end if;
    end if;
    return new;
end
$$;
"""

OLD_RATING_RULE = """
create or replace function check_skill_rating() returns trigger
language plpgsql
as $$
declare
    actor uuid;
    sheet_status text;
    sheet_revision int;
    sheet_area uuid;
    sheet_arm uuid;
    sheet_term uuid;
begin
    actor := app_current_user_id();
    if actor is null then
        raise exception 'Every rating needs a signed-in author.'
            using errcode = 'check_violation',
                  constraint = 'skill_ratings_need_an_author';
    end if;

    select s.status, s.revision, s.learning_area_id, s.arm_id, s.term_id
      into sheet_status, sheet_revision, sheet_area, sheet_arm, sheet_term
      from result_sheets s
     where s.id = case when tg_op = 'DELETE' then old.sheet_id else new.sheet_id end;

    if sheet_status not in ('draft', 'returned_for_correction') then
        raise exception 'This sheet is % and its ratings cannot change.', sheet_status
            using errcode = 'check_violation',
                  constraint = 'skill_ratings_sheet_is_locked';
    end if;

    if tg_op = 'DELETE' then
        if not (sheet_status = 'draft' and sheet_revision = 1) then
            raise exception 'Ratings are removed only while a sheet is its first draft.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_removed_only_in_first_draft';
        end if;
        return old;
    end if;

    if tg_op = 'INSERT'
       or new.skill_id is distinct from old.skill_id
       or new.enrolment_id is distinct from old.enrolment_id
    then
        if not exists (
            select 1
              from skills k
             where k.id = new.skill_id
               and k.learning_area_id = sheet_area
               and k.is_active
        ) then
            raise exception 'This is not an active skill of the sheet''s learning area.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_skill_in_area';
        end if;
        if not exists (
            select 1
              from enrolments e
              join terms t on t.id = sheet_term and t.session_id = e.session_id
             where e.id = new.enrolment_id
               and e.arm_id = sheet_arm
        ) then
            raise exception 'This pupil is not in the sheet''s class.'
                using errcode = 'check_violation',
                      constraint = 'skill_ratings_pupil_in_arm';
        end if;
    end if;

    if tg_op = 'INSERT' then
        new.entered_by := actor;
        new.updated_by := null;
    else
        new.entered_by := old.entered_by;
        if new.point_id is distinct from old.point_id then
            if (sheet_status = 'returned_for_correction' or sheet_revision > 1)
               and (new.change_reason is null or btrim(new.change_reason) = '')
            then
                raise exception 'Changing a submitted rating needs a reason.'
                    using errcode = 'check_violation',
                          constraint = 'skill_ratings_change_needs_reason';
            end if;
            new.updated_by := actor;
        end if;
    end if;
    return new;
end
$$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(SCORE_RULE)
    op.execute(RATING_RULE)
    op.execute(CLASS_LEVEL_RULE)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop trigger classes_level_fixed_once_used on classes")
    op.execute("drop function guard_class_level()")
    op.execute(OLD_RATING_RULE)
    op.execute(OLD_SCORE_RULE)
