"""Request and response shapes for /auth (BUILD_PROMPT 9.2b).

Lengths are generous outer limits only; the real password rules (D-036) are
checked in routes.py so each refusal gets its own clear code.
"""

from typing import Annotated, Literal

from pydantic import Field

from app.core.schemas import ApiModel

Text = Annotated[str, Field(min_length=1, max_length=254)]
Password = Annotated[str, Field(min_length=1, max_length=1024)]
Token = Annotated[str, Field(min_length=1, max_length=200)]


SchoolCode = Annotated[str, Field(min_length=1, max_length=10)]


class LoginRequest(ApiModel):
    """A login on a school's own page, /login/{code} (F02 rule 1, D-182)."""

    identifier: Text
    password: Password
    # From the page's link, never typed: the account must belong to this school.
    school_code: SchoolCode
    # Which tab: staff and parents use an email or username, students a username
    # or admission number inside the school (D-033).
    tab: Literal["staff", "student"] = "staff"


class PlatformLoginRequest(ApiModel):
    """The super admin's own page, /platform/login (F02 rule 11)."""

    identifier: Text
    password: Password


class LoginResult(ApiModel):
    must_change_password: bool
    # The school whose page was used, so a parent of several schools starts
    # there (F02 rule 1). None for the super admin.
    school_id: str | None = None
    # The super admin's next step (D-043): "setup" the authenticator, or enter a "code".
    two_factor: Literal["setup", "code"] | None = None


class ChangePasswordRequest(ApiModel):
    current_password: Password
    new_password: Password


class LinkRequest(ApiModel):
    token: Token
    password: Password


class ForgotRequest(ApiModel):
    # Any text: a username or admission number gets the same answer (AC02.8).
    email: Text


class Accepted(ApiModel):
    detail: str


class SchoolPublic(ApiModel):
    """What a school's login page shows (F02 rules 2 and 12). The code is the
    school's current one: when it differs from the link's, the page forwards."""

    code: str
    name: str
    colour: str
    logo_url: str | None
    layout: Literal["half", "behind"]
    picture: Literal["pattern", "people", "photo"]
    # The school's own words over the picture; None shows "Welcome to {name}".
    message: str | None
    photo_url: str | None


class MeUser(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None


class MeSchool(ApiModel):
    id: str
    code: str
    name: str
    colour: str


class MeSchoolLink(ApiModel):
    id: str
    name: str
    role: str


class FormClass(ApiModel):
    arm_id: str
    name: str


class Me(ApiModel):
    user: MeUser
    school: MeSchool | None
    schools: list[MeSchoolLink]
    role: str
    is_primary: bool
    is_super_admin: bool
    must_change_password: bool
    permissions: list[str]
    features: list[str]
    form_class: FormClass | None
    unread_notices: int
