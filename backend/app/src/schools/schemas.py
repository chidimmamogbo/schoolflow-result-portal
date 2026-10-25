"""Request and response shapes for /school (BUILD_PROMPT 9.2e, first part).

Unknown fields are refused, so a body can never carry `school_id`, `name`,
`code` or `enabled`: those belong to the signed-in membership or the super
admin.
"""

from typing import Annotated, Literal

from pydantic import StringConstraints

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Colour, Email, Line, Phone

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

HeadTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]

LevelName = Literal["nursery", "primary", "junior_secondary", "senior_secondary"]


class LevelRow(ApiModel):
    level: str
    enabled: bool
    assessment_mode: str
    head_title: str


class SchoolSettings(ApiModel):
    id: str
    code: str
    name: str
    email: str
    phone: str
    address: str
    city: str
    state: str
    country: str
    colour: str
    features: dict[str, bool]
    levels: list[LevelRow]


class EditSettings(ApiModel):
    email: Email | None = None
    phone: Phone | None = None
    address: Line | None = None
    city: Line | None = None
    state: Line | None = None
    country: Line | None = None
    colour: Colour | None = None


class LevelChange(ApiModel):
    assessment_mode: Literal["scores", "skill_ratings"] | None = None
    head_title: HeadTitle | None = None


class LevelResult(ApiModel):
    level: str
    assessment_mode: str
    head_title: str
    # A mode change waits for next term once the term's entries have started (AC08.6).
    applies_from: Literal["this_term", "next_term"]
