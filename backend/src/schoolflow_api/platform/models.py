"""Platform-wide settings the super admin changes (SPEC F24 rule 4).

One row per setting, like WordPress's wp_options table: a key such as
"billing.grace_period_days" and its value. The value is JSON, so a number,
text or a list all fit. Every change is audited (audit_events, migration 11).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"
    __table_args__ = (
        CheckConstraint(
            r"key ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$'",
            name="key_format",
        ),
    )

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    # The super admin who last changed it; linked to users in migration 2.
    updated_by: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
