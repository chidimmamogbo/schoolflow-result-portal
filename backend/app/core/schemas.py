"""The parent of every request and response schema (D-016).

`extra="forbid"` refuses any field the schema does not list, so a request
cannot sneak in `is_admin: true` or `school_id` (like WordPress rejecting
unknown form fields, but enforced for every endpoint at once).
"""

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
