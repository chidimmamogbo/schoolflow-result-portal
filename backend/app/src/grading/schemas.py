"""Requests and responses of the grading routes (D-173)."""

import uuid
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import ApiModel
from app.src.schools.schemas import LevelName

Text30 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]

Text60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]

Text80 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

Score = Annotated[int, Field(ge=0, le=100)]

Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9+-]{0,3}$")]

Label = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9 ]{0,9}$")]


# --- shapes ---------------------------------------------------------------------------------
class Band(ApiModel):
    grade: Code
    min_score: Score
    max_score: Score
    remark: Text30


class BandsIn(ApiModel):
    bands: Annotated[list[Band], Field(min_length=1, max_length=20)]


class RemarkBand(ApiModel):
    min_score: Score
    max_score: Score
    comments: Annotated[list[Comment], Field(min_length=1, max_length=3)]


class RemarkBandsIn(ApiModel):
    bands: Annotated[list[RemarkBand], Field(max_length=20)]


class LevelGrading(ApiModel):
    grade_bands: list[Band]
    remark_bands: list[RemarkBand]


class GradingOut(ApiModel):
    pass_mark: int
    levels: dict[str, LevelGrading]


class PassMark(ApiModel):
    pass_mark: Annotated[int, Field(ge=1, le=99)]


class Trait(ApiModel):
    id: str
    name: str
    position: int
    is_active: bool


class Traits(ApiModel):
    affective: list[Trait]
    psychomotor: list[Trait]
    key: dict[str, str]


class NewTrait(ApiModel):
    domain: Literal["affective", "psychomotor"]
    name: Text60


class EditTrait(ApiModel):
    name: Text60 | None = None
    position: Annotated[int, Field(ge=1, le=100)] | None = None
    is_active: bool | None = None


class TraitKey(ApiModel):
    key: dict[Literal["1", "2", "3", "4", "5"], Text30]

    @model_validator(mode="after")
    def all_five(self) -> Self:
        if len(self.key) != 5:
            raise ValueError("Give a label for each of 1, 2, 3, 4 and 5.")
        return self


class Component(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    label: Label
    max_score: Annotated[int, Field(ge=1, le=100)]


class ComponentsIn(ApiModel):
    components: Annotated[list[Component], Field(max_length=8)]


class StructureOut(ApiModel):
    level: str
    term_id: str
    assessment_mode: str
    saved: bool
    locked: bool
    components: list[Component]


class SkillOut(ApiModel):
    id: str
    name: str
    description: str | None
    position: int
    is_active: bool


class AreaOut(ApiModel):
    id: str
    level: str
    name: str
    position: int
    skills: list[SkillOut]


class NewArea(ApiModel):
    level: LevelName
    name: Text60


class EditArea(ApiModel):
    name: Text60 | None = None
    position: Annotated[int, Field(ge=1, le=100)] | None = None


class NewSkill(ApiModel):
    name: Text80
    description: Text200 | None = None


class EditSkill(ApiModel):
    name: Text80 | None = None
    description: Text200 | None = None
    position: Annotated[int, Field(ge=1, le=100)] | None = None
    is_active: bool | None = None


class ClassAreas(ApiModel):
    learning_area_ids: Annotated[list[uuid.UUID], Field(max_length=30)]


class Point(ApiModel):
    name: Text30
    code: Code
    description: Text200 | None = None
    is_attention: bool


class ScaleIn(ApiModel):
    points: Annotated[list[Point], Field(min_length=2, max_length=10)]


class ScaleOut(ApiModel):
    points: list[Point]
