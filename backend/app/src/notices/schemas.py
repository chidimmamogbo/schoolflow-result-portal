"""Requests and responses of the notice board (SPEC F17; D-175)."""

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import ApiModel

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
AudienceRole = Literal["school_admin", "reviewer", "teacher", "parent", "student"]


class Audience(ApiModel):
    """Everyone, or chosen roles, chosen classes, or roles within classes."""

    everyone: bool = False
    roles: Annotated[list[AudienceRole], Field(max_length=5)] = Field(
        default_factory=list[AudienceRole]
    )
    class_ids: Annotated[list[uuid.UUID], Field(max_length=100)] = Field(
        default_factory=list[uuid.UUID]
    )


class NewNotice(ApiModel):
    title: Title
    body: Body
    pinned: bool = False
    audience: Audience


class EditNotice(ApiModel):
    title: Title | None = None
    body: Body | None = None
    pinned: bool | None = None


class Notice(ApiModel):
    """A notice as its reader sees it, labelled with its school."""

    id: str
    school_id: str
    school_name: str
    school_code: str
    title: str
    body: str
    kind: Literal["manual", "system"]
    pinned: bool
    read: bool
    created_at: dt.datetime


class Board(ApiModel):
    notices: list[Notice]


class Unread(ApiModel):
    unread: int


class SchoolNotice(ApiModel):
    """A notice as school admins manage it."""

    id: str
    title: str
    body: str
    kind: Literal["manual", "system"]
    pinned: bool
    status: Literal["published", "archived"]
    author: str | None
    recipients: int
    reads: int
    created_at: dt.datetime
    updated_at: dt.datetime


class SchoolNotices(ApiModel):
    notices: list[SchoolNotice]
