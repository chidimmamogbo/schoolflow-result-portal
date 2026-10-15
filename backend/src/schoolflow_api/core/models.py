"""The rate limit counters (D-021, D-042; migration 19).

One row per keyed hash ("login:ip:..." after HMAC): when the current window
started and how many hits it has had. No app role can read or write the
table; they call the owner-run function rate_limit_hit() instead.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        CheckConstraint("octet_length(key_hash) = 32", name="key_hash_length"),
        CheckConstraint("hits >= 1", name="hits_positive"),
    )

    key_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hits: Mapped[int]
