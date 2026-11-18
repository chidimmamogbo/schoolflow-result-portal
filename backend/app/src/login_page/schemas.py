"""Request and response shapes for a school's login page settings (CHANGE C, D-182)."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, StringConstraints

from app.core.schemas import ApiModel


def blank_is_none(value: object) -> object:
    """An empty message means "show the default", stored as no message."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


Message = Annotated[
    Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\r\n]+$"
        ),
    ]
    | None,
    BeforeValidator(blank_is_none),
]


class LoginPageChange(ApiModel):
    """Layout "Half and half" or "Picture behind"; picture "Pattern", "People" or
    "Your own photo" (only once a photo is uploaded); the message over the picture."""

    layout: Literal["half", "behind"]
    picture: Literal["pattern", "people", "photo"]
    message: Message = None


class LoginPage(ApiModel):
    layout: Literal["half", "behind"]
    picture: Literal["pattern", "people", "photo"]
    message: str | None
    # The public photo route, or None before one is uploaded.
    photo_url: str | None
    # The school's own login page, for "Open login page" and "Copy link".
    link: str
