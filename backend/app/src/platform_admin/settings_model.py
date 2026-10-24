"""Platform settings the super admin edits (SPEC F24 rule 4, section 12 defaults).

Stored one row per setting in platform_settings ("billing.grace_period_days"
-> 14), like WordPress options; a setting with no row has its default here.
Tabs General, Email, Billing and Security are here; School defaults arrive
with the grading module, the platform logo with uploads, and session length
and two-factor login after the core (D-037, D-043).
"""

from typing import Annotated, Any, Literal

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Email, Line, Phone


class General(ApiModel):
    platform_name: Line = "SchoolFlow"
    support_email: Email | None = None
    support_phone: Phone | None = None


class EmailSettings(ApiModel):
    sender_name: Line = "SchoolFlow"
    reply_to: Email | None = None


class Billing(ApiModel):
    grace_period_days: Annotated[int, Field(ge=0, le=90)] = 14
    invoice_due_days: Annotated[int, Field(ge=1, le=90)] = 14
    fees_paid_by: Literal["platform", "school"] = "platform"
    cliff_protection: bool = True


class Security(ApiModel):
    max_additional_admins: Annotated[int, Field(ge=0, le=10)] = 2


class PlatformSettings(ApiModel):
    general: General = General()
    email: EmailSettings = EmailSettings()
    billing: Billing = Billing()
    security: Security = Security()


def flatten(settings: PlatformSettings) -> dict[str, Any]:
    """{"general.platform_name": "SchoolFlow", ...}"""
    return {
        f"{group}.{name}": value
        for group, values in settings.model_dump(mode="json").items()
        for name, value in values.items()
    }


def load(session: Session) -> PlatformSettings:
    stored: dict[str, dict[str, Any]] = {}
    for key, value in session.execute(text("select key, value from platform_settings")):
        group, _, name = str(key).partition(".")
        if group in PlatformSettings.model_fields:
            stored.setdefault(group, {})[name] = value
    return PlatformSettings.model_validate(stored)


def merged(current: PlatformSettings, changes: dict[str, Any]) -> PlatformSettings:
    """The current settings with a partial change applied, validated as a whole."""
    data = current.model_dump(mode="json")
    for group, values in changes.items():
        if not isinstance(values, dict):
            data[group] = values  # validation below refuses it
            continue
        data.setdefault(group, {}).update(values)
    return PlatformSettings.model_validate(data)
