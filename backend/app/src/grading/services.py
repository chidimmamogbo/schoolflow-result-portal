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
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from itertools import pairwise
from typing import Any

import psycopg
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, ensure_level_enabled, found
from app.core.errors import ProblemError
from app.src.audit.services import write_audit
from app.src.grading.defaults import (
    AFFECTIVE_TRAITS,
    ATTENTION_POINT,
    DEFAULT_COMPONENTS,
    DEFAULT_PASS_MARK,
    LEARNING_AREAS,
    PRIMARY_GRADE_BANDS,
    PSYCHOMOTOR_TRAITS,
    RATING_SCALE,
    SECONDARY_GRADE_BANDS,
    TRAIT_KEY,
)
from app.src.grading.schemas import (
    AreaOut,
    Band,
    BandsIn,
    ClassAreas,
    Component,
    ComponentsIn,
    EditArea,
    EditSkill,
    EditTrait,
    GradingOut,
    LevelGrading,
    NewArea,
    NewSkill,
    NewTrait,
    PassMark,
    Point,
    RemarkBand,
    RemarkBandsIn,
    ScaleIn,
    ScaleOut,
    SkillOut,
    StructureOut,
    Trait,
    TraitKey,
    Traits,
)
from app.src.schools.models import Level
from app.src.schools.schemas import LevelName

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


NAME_RULES = frozenset(
    {"ix_rating_traits_unique_name", "ix_learning_areas_unique_name", "ix_skills_unique_name"}
)


# --- helpers ------------------------------------------------------------------------------
def setup(session: Session, who: Principal) -> uuid.UUID:
    school_id = found(who.school_id)
    ensure_defaults(session, school_id, who.role.value)
    return school_id


def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


@contextmanager
def unique_name(session: Session) -> Generator[None]:
    try:
        with session.begin_nested():
            yield
    except IntegrityError as error:
        original = error.orig
        rule = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
        if rule in NAME_RULES:
            raise ProblemError(409, "This name is already used.", code="name_taken") from None
        raise


def check_cover(ranges: Sequence[tuple[int, int]]) -> None:
    """0 to 100, no gaps, no overlaps (D-141)."""
    ordered = sorted(ranges)
    ok = bool(ordered) and ordered[0][0] == 0 and ordered[-1][1] == 100
    ok = ok and all(low <= high for low, high in ordered)
    ok = ok and all(nxt[0] == cur[1] + 1 for cur, nxt in pairwise(ordered))
    if not ok:
        raise ProblemError(
            422, "Bands must cover 0 to 100 with no gaps or overlaps.", code="bands_must_cover"
        )


def bands_of(session: Session, level: str) -> LevelGrading:
    grade = [
        Band(grade=r.grade, min_score=r.min_score, max_score=r.max_score, remark=r.remark)
        for r in session.execute(
            text(
                "select grade, min_score, max_score, remark from grade_bands"
                " where level = :l order by min_score desc"
            ),
            {"l": level},
        )
    ]
    remarks = [
        RemarkBand(min_score=r.min_score, max_score=r.max_score, comments=list(r.comments))
        for r in session.execute(
            text(
                "select min_score, max_score, comments from remark_bands"
                " where level = :l order by min_score desc"
            ),
            {"l": level},
        )
    ]
    return LevelGrading(grade_bands=grade, remark_bands=remarks)


def get_grading(
    who: Principal,
    session: Session,
) -> GradingOut:
    setup(session, who)
    pass_mark = session.scalar(text("select pass_mark from school_settings"))
    order = [level.value for level in Level]
    levels = sorted(
        session.scalars(text("select level from school_levels where enabled")), key=order.index
    )
    return GradingOut(
        pass_mark=int(pass_mark or 0), levels={level: bands_of(session, level) for level in levels}
    )


def set_bands(
    level: LevelName,
    body: BandsIn,
    who: Principal,
    session: Session,
) -> LevelGrading:
    setup(session, who)
    ensure_level_enabled(session, who, Level(level))
    check_cover([(b.min_score, b.max_score) for b in body.bands])
    if len({b.grade for b in body.bands}) != len(body.bands):
        raise ProblemError(422, "Each grade appears once.", code="grades_repeat")
    before = bands_of(session, level).grade_bands
    session.execute(text("delete from grade_bands where level = :l"), {"l": level})
    for band in body.bands:
        session.execute(
            text(
                "insert into grade_bands (school_id, level, grade, min_score, max_score, remark)"
                " values (:s, :l, :g, :lo, :hi, :r)"
            ),
            {
                "s": who.school_id,
                "l": level,
                "g": band.grade,
                "lo": band.min_score,
                "hi": band.max_score,
                "r": band.remark,
            },
        )
    audit(
        session,
        who,
        "grade_bands.update",
        old={"level": level, "bands": [b.model_dump() for b in before]},
        new={"level": level, "bands": [b.model_dump() for b in body.bands]},
    )
    return bands_of(session, level)


def set_remark_bands(
    level: LevelName,
    body: RemarkBandsIn,
    who: Principal,
    session: Session,
) -> LevelGrading:
    setup(session, who)
    ensure_level_enabled(session, who, Level(level))
    if body.bands:
        check_cover([(b.min_score, b.max_score) for b in body.bands])
    session.execute(text("delete from remark_bands where level = :l"), {"l": level})
    for band in body.bands:
        session.execute(
            text(
                "insert into remark_bands (school_id, level, min_score, max_score, comments)"
                " values (:s, :l, :lo, :hi, :c)"
            ),
            {
                "s": who.school_id,
                "l": level,
                "lo": band.min_score,
                "hi": band.max_score,
                "c": band.comments,
            },
        )
    audit(
        session,
        who,
        "remark_bands.update",
        new={"level": level, "bands": [b.model_dump() for b in body.bands]},
    )
    return bands_of(session, level)


def set_pass_mark(
    body: PassMark,
    who: Principal,
    session: Session,
) -> PassMark:
    setup(session, who)
    before = session.scalar(text("select pass_mark from school_settings"))
    session.execute(text("update school_settings set pass_mark = :p"), {"p": body.pass_mark})
    audit(
        session,
        who,
        "pass_mark.update",
        old={"pass_mark": before},
        new={"pass_mark": body.pass_mark},
    )
    return body


# --- traits and their key ---------------------------------------------------------------
def traits_of(session: Session) -> Traits:
    rows = session.execute(
        text(
            "select id, domain, name, position, is_active from rating_traits"
            " order by position, name"
        )
    )
    grouped: dict[str, list[Trait]] = {"affective": [], "psychomotor": []}
    for r in rows:
        grouped[r.domain].append(
            Trait(id=str(r.id), name=r.name, position=r.position, is_active=r.is_active)
        )
    key = {
        str(r.value): r.label
        for r in session.execute(
            text("select value, label from trait_scale_points order by value desc")
        )
    }
    return Traits(affective=grouped["affective"], psychomotor=grouped["psychomotor"], key=key)


def get_traits(
    who: Principal,
    session: Session,
) -> Traits:
    setup(session, who)
    return traits_of(session)


def add_trait(
    body: NewTrait,
    who: Principal,
    session: Session,
) -> Trait:
    setup(session, who)
    position = int(
        session.scalar(
            text("select coalesce(max(position), 0) + 1 from rating_traits where domain = :d"),
            {"d": body.domain},
        )
        or 1
    )
    with unique_name(session):
        trait_id: uuid.UUID = session.scalar(
            text(
                "insert into rating_traits (school_id, domain, name, position)"
                " values (:s, :d, :n, :p) returning id"
            ),
            {"s": who.school_id, "d": body.domain, "n": body.name, "p": position},
        )
    audit(
        session,
        who,
        "rating_traits.create",
        target=("rating_traits", trait_id),
        new=body.model_dump(),
    )
    return Trait(id=str(trait_id), name=body.name, position=position, is_active=True)


def edit_trait(
    trait_id: uuid.UUID,
    body: EditTrait,
    who: Principal,
    session: Session,
) -> Trait:
    setup(session, who)
    found(session.scalar(text("select id from rating_traits where id = :t"), {"t": trait_id}))
    changes = body.model_dump(exclude_unset=True)
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        with unique_name(session):
            session.execute(
                text(f"update rating_traits set {assignments} where id = :id"),  # noqa: S608
                {**changes, "id": trait_id},
            )
        audit(session, who, "rating_traits.update", target=("rating_traits", trait_id), new=changes)
    r = session.execute(
        text("select id, name, position, is_active from rating_traits where id = :t"),
        {"t": trait_id},
    ).one()
    return Trait(id=str(r.id), name=r.name, position=r.position, is_active=r.is_active)


def set_trait_key(
    body: TraitKey,
    who: Principal,
    session: Session,
) -> TraitKey:
    setup(session, who)
    for value, label in body.key.items():
        session.execute(
            text("update trait_scale_points set label = :l where value = :v"),
            {"l": label, "v": int(value)},
        )
    audit(session, who, "trait_key.update", new=dict(body.key))
    return body


# --- assessment structures -----------------------------------------------------------------
def term_or_active(session: Session, term_id: uuid.UUID | None) -> uuid.UUID:
    if term_id is not None:
        return found(session.scalar(text("select id from terms where id = :t"), {"t": term_id}))
    active = session.scalar(text("select id from terms where is_active"))
    if active is None:
        raise ProblemError(409, "Activate a term first.", code="no_active_term")
    return active


def next_term(session: Session, term_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        text(
            "select t2.id from terms t1 join academic_sessions s1 on s1.id = t1.session_id,"
            " terms t2 join academic_sessions s2 on s2.id = t2.session_id"
            " where t1.id = :t and (s2.starts_on, t2.term_number) > (s1.starts_on, t1.term_number)"
            " order by s2.starts_on, t2.term_number limit 1"
        ),
        {"t": term_id},
    )


def components_of(session: Session, structure_id: uuid.UUID) -> list[Component]:
    return [
        Component(name=r.name, label=r.label, max_score=r.max_score)
        for r in session.execute(
            text(
                "select name, label, max_score from assessment_components"
                " where structure_id = :s order by position"
            ),
            {"s": structure_id},
        )
    ]


def structure_of(session: Session, level: str, term_id: uuid.UUID) -> StructureOut:
    row = session.execute(
        text(
            "select id, assessment_mode, locked_at is not null as locked"
            " from assessment_structures where level = :l and term_id = :t"
        ),
        {"l": level, "t": term_id},
    ).first()
    if row is not None:
        return StructureOut(
            level=level,
            term_id=str(term_id),
            assessment_mode=row.assessment_mode,
            saved=True,
            locked=row.locked,
            components=components_of(session, row.id),
        )
    mode = str(
        session.scalar(
            text("select assessment_mode from school_levels where level = :l"), {"l": level}
        )
    )
    # A suggestion: the level's latest earlier structure, else the platform default.
    earlier = session.scalar(
        text(
            "select a.id from assessment_structures a join terms t on t.id = a.term_id"
            " join academic_sessions s on s.id = t.session_id, terms here"
            " join academic_sessions hs on hs.id = here.session_id"
            " where a.level = :l and here.id = :t and a.assessment_mode = 'scores'"
            " and (s.starts_on, t.term_number) < (hs.starts_on, here.term_number)"
            " order by s.starts_on desc, t.term_number desc limit 1"
        ),
        {"l": level, "t": term_id},
    )
    if mode != "scores":
        components: list[Component] = []
    elif earlier is not None:
        components = components_of(session, earlier)
    else:
        components = [
            Component(name=c.name, label=c.label, max_score=c.max_score) for c in DEFAULT_COMPONENTS
        ]
    return StructureOut(
        level=level,
        term_id=str(term_id),
        assessment_mode=mode,
        saved=False,
        locked=False,
        components=components,
    )


def get_structure(
    level: LevelName,
    who: Principal,
    session: Session,
    term_id: uuid.UUID | None = None,
) -> StructureOut:
    ensure_level_enabled(session, who, Level(level))
    return structure_of(session, level, term_or_active(session, term_id))


def set_structure(
    level: LevelName,
    body: ComponentsIn,
    who: Principal,
    session: Session,
    term_id: uuid.UUID | None = None,
) -> StructureOut:
    ensure_level_enabled(session, who, Level(level))
    target = term_or_active(session, term_id)
    current = structure_of(session, level, target)
    if current.locked:
        following = next_term(session, target)
        if following is None:
            raise ProblemError(
                409, "This term is locked. Add the next term first.", code="no_next_term"
            )
        target = following
        current = structure_of(session, level, target)
        if current.locked:
            raise ProblemError(409, "The next term is locked too.", code="no_next_term")
    mode = current.assessment_mode
    if mode == "skill_ratings":
        if body.components:
            raise ProblemError(
                422, "A Skill ratings level has no score columns.", code="ratings_have_no_columns"
            )
    else:
        if not body.components:
            raise ProblemError(
                422, "Add at least one component.", code="structure_needs_components"
            )
        total = sum(c.max_score for c in body.components)
        if total != 100:
            gap = 100 - total
            more_or_less = f"{gap} more" if gap > 0 else f"{-gap} less"
            raise ProblemError(
                422,
                "The maximums must add up to 100.",
                f"The maximums add up to {total}. They must add up to 100 ({more_or_less}).",
                code="structure_total",
            )
        if len({c.label.lower() for c in body.components}) != len(body.components):
            raise ProblemError(422, "Each column label appears once.", code="labels_repeat")
    structure_id = session.scalar(
        text("select id from assessment_structures where level = :l and term_id = :t"),
        {"l": level, "t": target},
    )
    if structure_id is None:
        structure_id = session.scalar(
            text(
                "insert into assessment_structures (school_id, level, term_id, assessment_mode)"
                " values (:s, :l, :t, :m) returning id"
            ),
            {"s": who.school_id, "l": level, "t": target, "m": mode},
        )
    session.execute(
        text("delete from assessment_components where structure_id = :s"), {"s": structure_id}
    )
    for position, component in enumerate(body.components, start=1):
        session.execute(
            text(
                "insert into assessment_components (school_id, structure_id, position, name,"
                " label, max_score) values (:s, :st, :p, :n, :lb, :m)"
            ),
            {
                "s": who.school_id,
                "st": structure_id,
                "p": position,
                "n": component.name,
                "lb": component.label,
                "m": component.max_score,
            },
        )
    audit(
        session,
        who,
        "assessment_structures.update",
        target=("terms", target),
        old={"level": level, "components": [c.model_dump() for c in current.components]},
        new={"level": level, "components": [c.model_dump() for c in body.components]},
    )
    return structure_of(session, level, target)


# --- learning areas, skills and classes (F26 rule 1) -----------------------------------------
def skill_out(r: Any) -> SkillOut:
    return SkillOut(
        id=str(r.id),
        name=r.name,
        description=r.description,
        position=r.position,
        is_active=r.is_active,
    )


def areas_of(
    session: Session, level: str | None = None, area_id: uuid.UUID | None = None
) -> list[AreaOut]:
    skills: dict[uuid.UUID, list[SkillOut]] = {}
    for r in session.execute(
        text(
            "select id, learning_area_id, name, description, position,"
            " is_active from skills order by position, name"
        )
    ):
        skills.setdefault(r.learning_area_id, []).append(skill_out(r))
    rows = session.execute(
        text(
            "select id, level, name, position from learning_areas"
            " where (cast(:l as text) is null or level = :l)"
            " and (cast(:a as uuid) is null or id = :a) order by level, position, name"
        ),
        {"l": level, "a": area_id},
    )
    return [
        AreaOut(
            id=str(r.id),
            level=r.level,
            name=r.name,
            position=r.position,
            skills=skills.get(r.id, []),
        )
        for r in rows
    ]


def list_areas(
    who: Principal,
    session: Session,
    level: LevelName | None = None,
) -> list[AreaOut]:
    setup(session, who)
    return areas_of(session, level)


def add_area(
    body: NewArea,
    who: Principal,
    session: Session,
) -> AreaOut:
    setup(session, who)
    ensure_level_enabled(session, who, Level(body.level))
    position = int(
        session.scalar(
            text("select coalesce(max(position), 0) + 1 from learning_areas where level = :l"),
            {"l": body.level},
        )
        or 1
    )
    with unique_name(session):
        area_id: uuid.UUID = session.scalar(
            text(
                "insert into learning_areas (school_id, level, name, position)"
                " values (:s, :l, :n, :p) returning id"
            ),
            {"s": who.school_id, "l": body.level, "n": body.name, "p": position},
        )
    audit(
        session,
        who,
        "learning_areas.create",
        target=("learning_areas", area_id),
        new=body.model_dump(),
    )
    return areas_of(session, area_id=area_id)[0]


def edit_area(
    area_id: uuid.UUID,
    body: EditArea,
    who: Principal,
    session: Session,
) -> AreaOut:
    found(session.scalar(text("select id from learning_areas where id = :a"), {"a": area_id}))
    changes = body.model_dump(exclude_unset=True)
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        with unique_name(session):
            session.execute(
                text(f"update learning_areas set {assignments} where id = :id"),  # noqa: S608
                {**changes, "id": area_id},
            )
        audit(
            session, who, "learning_areas.update", target=("learning_areas", area_id), new=changes
        )
    return areas_of(session, area_id=area_id)[0]


def delete_area(
    area_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    found(session.scalar(text("select id from learning_areas where id = :a"), {"a": area_id}))
    session.execute(text("delete from skills where learning_area_id = :a"), {"a": area_id})
    session.execute(text("delete from learning_areas where id = :a"), {"a": area_id})
    audit(session, who, "learning_areas.delete", target=("learning_areas", area_id))


def add_skill(
    area_id: uuid.UUID,
    body: NewSkill,
    who: Principal,
    session: Session,
) -> SkillOut:
    found(session.scalar(text("select id from learning_areas where id = :a"), {"a": area_id}))
    position = int(
        session.scalar(
            text("select coalesce(max(position), 0) + 1 from skills where learning_area_id = :a"),
            {"a": area_id},
        )
        or 1
    )
    with unique_name(session):
        row = session.execute(
            text(
                "insert into skills (school_id, learning_area_id, name, description, position)"
                " values (:s, :a, :n, :d, :p)"
                " returning id, name, description, position, is_active"
            ),
            {
                "s": who.school_id,
                "a": area_id,
                "n": body.name,
                "d": body.description,
                "p": position,
            },
        ).one()
    audit(session, who, "skills.create", target=("skills", row.id), new=body.model_dump())
    return skill_out(row)


def edit_skill(
    skill_id: uuid.UUID,
    body: EditSkill,
    who: Principal,
    session: Session,
) -> SkillOut:
    found(session.scalar(text("select id from skills where id = :k"), {"k": skill_id}))
    changes = body.model_dump(exclude_unset=True)
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        with unique_name(session):
            session.execute(
                text(f"update skills set {assignments} where id = :id"),  # noqa: S608
                {**changes, "id": skill_id},
            )
        audit(session, who, "skills.update", target=("skills", skill_id), new=changes)
    return skill_out(
        session.execute(
            text("select id, name, description, position, is_active from skills where id = :k"),
            {"k": skill_id},
        ).one()
    )


def delete_skill(
    skill_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    """Only a skill nobody has rated; a rated skill is retired instead (is_active)."""
    found(session.scalar(text("select id from skills where id = :k"), {"k": skill_id}))
    session.execute(text("delete from skills where id = :k"), {"k": skill_id})
    audit(session, who, "skills.delete", target=("skills", skill_id))


def set_class_areas(
    class_id: uuid.UUID,
    body: ClassAreas,
    who: Principal,
    session: Session,
) -> list[AreaOut]:
    found(session.scalar(text("select id from classes where id = :c"), {"c": class_id}))
    wanted = {
        found(session.scalar(text("select id from learning_areas where id = :a"), {"a": a}))
        for a in body.learning_area_ids
    }
    current = set(
        session.scalars(
            text("select learning_area_id from class_learning_areas where class_id = :c"),
            {"c": class_id},
        )
    )
    for area in current - wanted:
        session.execute(
            text("delete from class_learning_areas where class_id = :c and learning_area_id = :a"),
            {"c": class_id, "a": area},
        )
    for area in wanted - current:
        session.execute(
            text(
                "insert into class_learning_areas (school_id, class_id,"
                " learning_area_id) values (:s, :c, :a)"
            ),
            {"s": who.school_id, "c": class_id, "a": area},
        )
    audit(
        session,
        who,
        "class_learning_areas.update",
        target=("classes", class_id),
        new={"learning_areas": sorted(map(str, wanted))},
    )
    return [area for area in areas_of(session) if uuid.UUID(area.id) in wanted]


# --- the rating scale (F26 rule 2) ----------------------------------------------------------
def scale_of(session: Session) -> ScaleOut:
    return ScaleOut(
        points=[
            Point(name=r.name, code=r.code, description=r.description, is_attention=r.is_attention)
            for r in session.execute(
                text(
                    "select name, code, description, is_attention"
                    " from rating_scale_points order by position"
                )
            )
        ]
    )


def get_scale(
    who: Principal,
    session: Session,
) -> ScaleOut:
    setup(session, who)
    return scale_of(session)


def set_scale(
    body: ScaleIn,
    who: Principal,
    session: Session,
) -> ScaleOut:
    setup(session, who)
    if sum(p.is_attention for p in body.points) != 1:
        raise ProblemError(422, "Choose exactly one attention rating.", code="one_attention_point")
    if len({p.code for p in body.points}) != len(body.points):
        raise ProblemError(422, "Each code appears once.", code="codes_repeat")
    scale_id = session.scalar(text("select id from rating_scales"))
    existing = list(
        session.scalars(
            text("select id from rating_scale_points where scale_id = :s order by position"),
            {"s": scale_id},
        )
    )
    # Points keep their ids where they can, so ratings already given still point at them.
    for position, point in enumerate(body.points, start=1):
        values = {
            "s": who.school_id,
            "scale": scale_id,
            "p": position,
            "n": point.name,
            "c": point.code,
            "d": point.description,
            "a": point.is_attention,
        }
        if position <= len(existing):
            session.execute(
                text(
                    "update rating_scale_points set position = :p, name = :n, code = :c,"
                    " description = :d, is_attention = :a where id = :id"
                ),
                {**values, "id": existing[position - 1]},
            )
        else:
            session.execute(
                text(
                    "insert into rating_scale_points (school_id, scale_id, position, name, code,"
                    " description, is_attention) values (:s, :scale, :p, :n, :c, :d, :a)"
                ),
                values,
            )
    for surplus in existing[len(body.points) :]:
        session.execute(text("delete from rating_scale_points where id = :id"), {"id": surplus})
    audit(
        session, who, "rating_scale.update", new={"points": [p.model_dump() for p in body.points]}
    )
    return scale_of(session)
