"""Requests and responses of the files routes (D-173)."""

from app.core.schemas import ApiModel


class StoredFileOut(ApiModel):
    id: str
    purpose: str
    content_type: str
    size_bytes: int
