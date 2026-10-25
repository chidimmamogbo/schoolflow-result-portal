"""The grading routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.grading import services
from app.src.grading.schemas import (
    AreaOut,
    BandsIn,
    ClassAreas,
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
    RemarkBandsIn,
    ScaleIn,
    ScaleOut,
    SkillOut,
    StructureOut,
    Trait,
    TraitKey,
    Traits,
)
from app.src.schools.schemas import LevelName

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

Grading = Annotated[Principal, Depends(require("grading.configure"))]

PassMarks = Annotated[Principal, Depends(require("pass_mark.configure"))]

Structures = Annotated[Principal, Depends(require("assessment.configure"))]

Skills = Annotated[Principal, Depends(require("skills.configure"))]


# --- grading bands, remark bands and the pass mark -----------------------------------------
@router.get("/grading", response_model=GradingOut)
def get_grading(who: Member, session: DbSession) -> GradingOut:
    return services.get_grading(who=who, session=session)


@router.put("/grading/{level}/bands", response_model=LevelGrading)
def set_bands(level: LevelName, body: BandsIn, who: Grading, session: DbSession) -> LevelGrading:
    return services.set_bands(level=level, body=body, who=who, session=session)


@router.put("/grading/{level}/remark-bands", response_model=LevelGrading)
def set_remark_bands(
    level: LevelName, body: RemarkBandsIn, who: Grading, session: DbSession
) -> LevelGrading:
    return services.set_remark_bands(level=level, body=body, who=who, session=session)


@router.put("/grading/pass-mark", response_model=PassMark)
def set_pass_mark(body: PassMark, who: PassMarks, session: DbSession) -> PassMark:
    return services.set_pass_mark(body=body, who=who, session=session)


@router.get("/traits", response_model=Traits)
def get_traits(who: Member, session: DbSession) -> Traits:
    return services.get_traits(who=who, session=session)


@router.post("/traits", status_code=201, response_model=Trait)
def add_trait(body: NewTrait, who: Grading, session: DbSession) -> Trait:
    return services.add_trait(body=body, who=who, session=session)


@router.patch("/traits/{trait_id}", response_model=Trait)
def edit_trait(trait_id: uuid.UUID, body: EditTrait, who: Grading, session: DbSession) -> Trait:
    return services.edit_trait(trait_id=trait_id, body=body, who=who, session=session)


@router.put("/traits/key", response_model=TraitKey)
def set_trait_key(body: TraitKey, who: Grading, session: DbSession) -> TraitKey:
    return services.set_trait_key(body=body, who=who, session=session)


@router.get("/assessment-structures/{level}", response_model=StructureOut)
def get_structure(
    level: LevelName, who: Member, session: DbSession, term_id: uuid.UUID | None = None
) -> StructureOut:
    return services.get_structure(level=level, who=who, session=session, term_id=term_id)


@router.put("/assessment-structures/{level}", response_model=StructureOut)
def set_structure(
    level: LevelName,
    body: ComponentsIn,
    who: Structures,
    session: DbSession,
    term_id: uuid.UUID | None = None,
) -> StructureOut:
    return services.set_structure(level=level, body=body, who=who, session=session, term_id=term_id)


@router.get("/learning-areas", response_model=list[AreaOut])
def list_areas(who: Member, session: DbSession, level: LevelName | None = None) -> list[AreaOut]:
    return services.list_areas(who=who, session=session, level=level)


@router.post("/learning-areas", status_code=201, response_model=AreaOut)
def add_area(body: NewArea, who: Skills, session: DbSession) -> AreaOut:
    return services.add_area(body=body, who=who, session=session)


@router.patch("/learning-areas/{area_id}", response_model=AreaOut)
def edit_area(area_id: uuid.UUID, body: EditArea, who: Skills, session: DbSession) -> AreaOut:
    return services.edit_area(area_id=area_id, body=body, who=who, session=session)


@router.delete("/learning-areas/{area_id}", status_code=204)
def delete_area(area_id: uuid.UUID, who: Skills, session: DbSession) -> None:
    return services.delete_area(area_id=area_id, who=who, session=session)


@router.post("/learning-areas/{area_id}/skills", status_code=201, response_model=SkillOut)
def add_skill(area_id: uuid.UUID, body: NewSkill, who: Skills, session: DbSession) -> SkillOut:
    return services.add_skill(area_id=area_id, body=body, who=who, session=session)


@router.patch("/skills/{skill_id}", response_model=SkillOut)
def edit_skill(skill_id: uuid.UUID, body: EditSkill, who: Skills, session: DbSession) -> SkillOut:
    return services.edit_skill(skill_id=skill_id, body=body, who=who, session=session)


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: uuid.UUID, who: Skills, session: DbSession) -> None:
    return services.delete_skill(skill_id=skill_id, who=who, session=session)


@router.put("/classes/{class_id}/learning-areas", response_model=list[AreaOut])
def set_class_areas(
    class_id: uuid.UUID, body: ClassAreas, who: Skills, session: DbSession
) -> list[AreaOut]:
    return services.set_class_areas(class_id=class_id, body=body, who=who, session=session)


@router.get("/rating-scale", response_model=ScaleOut)
def get_scale(who: Member, session: DbSession) -> ScaleOut:
    return services.get_scale(who=who, session=session)


@router.put("/rating-scale", response_model=ScaleOut)
def set_scale(body: ScaleIn, who: Skills, session: DbSession) -> ScaleOut:
    return services.set_scale(body=body, who=who, session=session)
