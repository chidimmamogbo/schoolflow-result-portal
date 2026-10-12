"""Tables for signed-in sessions and one-time account links (D-037, D-039, D-041).

Only hashes are stored. The real session token lives in the person's browser
cookie and the real link token in the email; the database keeps
HMAC-SHA256(APP_SECRET_KEY, token), so a stolen database copy cannot be used
to log in or reset a password. (WordPress stores session tokens hashed in
wp_usermeta for the same reason.)

Who may see or end which rows is row-level security in the migration
(D-137, D-138).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, one_of

# HMAC-SHA256 gives 32 bytes for every token.
TOKEN_HASH_BYTES = 32


class TokenPurpose(StrEnum):
    ACTIVATION = "activation"  # set the first password, 72 hours (D-039)
    RESET = "reset"  # forgot password or a school's reset link, 1 hour (D-041)


class UserSession(IdMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint(f"octet_length(token_hash) = {TOKEN_HASH_BYTES}", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("char_length(device_label) <= 200", name="device_label_length"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    # For "signed in on" lists, for example "Chrome on Android".
    device_label: Mapped[str | None]
    ip_address: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Idle timeout counts from here (12 hours; 1 hour for the super admin, D-037).
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Absolute end (7 days; 12 hours for the super admin, D-037).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountToken(IdMixin, Base):
    __tablename__ = "account_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        # One live link per account and purpose: resending cancels the old one first (D-039).
        Index(
            "ix_account_tokens_one_live_link",
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("used_at IS NULL AND cancelled_at IS NULL"),
        ),
        CheckConstraint(one_of("purpose", TokenPurpose), name="purpose_allowed"),
        CheckConstraint(f"octet_length(token_hash) = {TOKEN_HASH_BYTES}", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("used_at IS NULL OR cancelled_at IS NULL", name="used_or_cancelled"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str]
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
