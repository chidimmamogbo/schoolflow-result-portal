"""Request and response shapes for /platform (BUILD_PROMPT 9.2d; SPEC F24, F25).

Field names follow the Create school form (design/NAVIGATION_AND_SETTINGS.md).
Unknown fields are refused (ApiModel), so `status`, `is_primary` or a school
id can never ride along in a body.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, StringConstraints, model_validator

from schoolflow_api.core.schemas import ApiModel

# The 36 states and the FCT (F24 rule 1: a dropdown when the country is Nigeria).
NIGERIAN_STATES = frozenset(
    {
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
        "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe", "Imo",
        "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
        "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba",
        "Yobe", "Zamfara",
    }
)  # fmt: skip

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9 ]{7,20}$")]
Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


def _upper(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


# Uppercased before the format check, so "gmc" is read as GMC (D-033).
Code = Annotated[str, BeforeValidator(_upper), StringConstraints(pattern=r"^[A-Z0-9]{3,10}$")]
Username = Annotated[str, StringConstraints(pattern=r"^[a-z0-9._-]{3,30}$")]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
SchoolType = Literal["nursery_primary", "secondary_only", "all_levels"]


class Features(ApiModel):
    """All six switches, every time (F01)."""

    results: bool
    report_cards: bool
    parent_portal: bool
    correction_queue: bool
    notice_board: bool
    email_notifications: bool


class PrincipalForm(ApiModel):
    full_name: Line
    username: Username
    email: Email


class SchoolDetails(ApiModel):
    name: Line
    email: Email
    phone: Phone
    address: Line
    city: Line
    state: Line
    country: Line = "Nigeria"
    colour: Colour

    @model_validator(mode="after")
    def nigerian_state(self) -> Self:
        if self.country == "Nigeria" and self.state not in NIGERIAN_STATES:
            raise ValueError("Choose one of the 36 states or the FCT.")
        return self


class CreateSchool(SchoolDetails):
    code: Code
    school_type: SchoolType
    features: Features
    billing: Literal["on", "free_pilot"]
    principal: PrincipalForm


class EditSchool(ApiModel):
    name: Line | None = None
    email: Email | None = None
    phone: Phone | None = None
    address: Line | None = None
    city: Line | None = None
    state: Line | None = None
    country: Line | None = None
    colour: Colour | None = None


class ChangeCode(ApiModel):
    code: Code
    confirm: bool = False


class Suspend(ApiModel):
    reason: Reason


class Levels(ApiModel):
    """The three report card toggles (F25 rule 2); Secondary covers JSS and SSS."""

    nursery: bool
    primary: bool
    secondary: bool


class LevelsChange(Levels):
    confirm: bool = False


class LevelsResult(ApiModel):
    levels: Levels
    school_type: str


class Created(ApiModel):
    id: str
    code: str


class Available(ApiModel):
    available: bool


class Subscription(ApiModel):
    billing_enabled: bool
    status: str


class SchoolRow(ApiModel):
    id: str
    code: str
    name: str
    status: str
    school_type: str
    city: str
    state: str


class SchoolDetail(SchoolRow):
    email: str
    phone: str
    address: str
    country: str
    colour: str
    features: Features
    levels: Levels
    subscription: Subscription | None


class Usage(ApiModel):
    students: int
    staff: int
    parents: int
    results_published: int
    last_activity: datetime | None


class AuditRow(ApiModel):
    id: str
    school_id: str | None
    actor_name: str | None
    actor_role: str
    action: str
    target_table: str | None
    target_id: str | None
    old_values: dict[str, object] | None
    new_values: dict[str, object] | None
    reason: str | None
    created_at: datetime


class EmailRow(ApiModel):
    """Status only (D-083): never the template data or the body."""

    id: str
    school_id: str | None
    type: str
    to_address: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


class PaymentRow(ApiModel):
    id: str
    school_id: str
    invoice_id: str
    reference: str
    amount_kobo: int
    status: str
    receipt_number: str | None
    created_at: datetime


class AdminRow(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None
    is_primary: bool
    is_active: bool
    activated: bool
    membership_status: str


class NewEmail(ApiModel):
    email: Email


class ResetLink(ApiModel):
    sign_out_all: bool = False


class TemporaryPassword(ApiModel):
    temporary_password: str


class Detail(ApiModel):
    detail: str


Limit = Annotated[int, Field(ge=1, le=200)]
