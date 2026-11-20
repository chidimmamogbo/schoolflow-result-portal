"""Request and response shapes for two-factor login (CHANGE D, D-043)."""

from typing import Annotated

from pydantic import Field

from app.core.schemas import ApiModel

# Six digits from the app, or a recovery code like 7KQ4M-2XDP9; spaces allowed.
Code = Annotated[str, Field(min_length=6, max_length=20)]


class CodeRequest(ApiModel):
    code: Code


class SetUp(ApiModel):
    """Shown once per set-up: the QR code to scan and the same secret as text."""

    secret: str
    qr_svg: str


class Passed(ApiModel):
    must_change_password: bool


class NewRecoveryCodes(ApiModel):
    """Shown once; only their hashes are kept."""

    recovery_codes: list[str]
    must_change_password: bool


class CodesLeft(ApiModel):
    codes_left: int
    must_change_password: bool
