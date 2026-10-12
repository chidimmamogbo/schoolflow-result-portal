"""Sessions and account links (BUILD_PROMPT 9.1 item 2; SPEC F02, F03;
D-037, D-039, D-041, D-137, D-138).

Behaviour: sessions and activation or reset links are stored only as hashes;
each link is single use, with one live link per account and purpose;
everyone manages their own sessions; a school can end the sessions of, and
issue links for, its own people, but never for an account shared with another
school and never for another school's people; the platform can do so for
school admins only.

Token hashes here are random bytes standing in for the real HMAC-SHA256
values. All data is fictional.
"""

import secrets
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from tests.db_support import acting_as, refused, violates
from tests.factories import add_membership, create_school, create_user, parent_accepts_link

NEW_SESSION = text(
    "insert into user_sessions (user_id, token_hash, expires_at)"
    " values (:user_id, :token_hash, now() + interval '7 days') returning id"
)
NEW_LINK = text(
    "insert into account_tokens (user_id, purpose, token_hash, expires_at)"
    " values (:user_id, :purpose, :token_hash, now() + interval '1 hour') returning id"
)
SEE_SESSIONS = text("select user_id from user_sessions where user_id = :user_id")
END_SESSIONS = text("delete from user_sessions where user_id = :user_id returning user_id")


@dataclass(frozen=True)
class Accounts:
    gmc: uuid.UUID
    bsa: uuid.UUID
    ngozi: uuid.UUID  # GMC principal
    tunde: uuid.UUID  # GMC teacher
    funke: uuid.UUID  # parent at GMC only
    ikenna: uuid.UUID  # parent at GMC and BSA: a shared account
    chiamaka: uuid.UUID  # BSA principal


@pytest.fixture
def accounts(db_session: Session) -> Accounts:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    def member(
        username: str, full_name: str, school: uuid.UUID, role: str, principal: bool = False
    ) -> uuid.UUID:
        user = create_user(
            s, username=username, full_name=full_name, email=f"{username}@example.com"
        )
        add_membership(s, user, school, role, is_primary=principal)
        return user

    ngozi = member("ngozi.okeke", "Ngozi Okeke", gmc, "school_admin", principal=True)
    tunde = member("tunde.adebayo", "Tunde Adebayo", gmc, "teacher")
    funke = member("funke.adeyemi", "Funke Adeyemi", gmc, "parent")
    ikenna = member("ikenna.obi", "Ikenna Obi", gmc, "parent")
    parent_accepts_link(s, ikenna, bsa)
    chiamaka = member("chiamaka.nwafor", "Chiamaka Nwafor", bsa, "school_admin", principal=True)
    return Accounts(gmc, bsa, ngozi, tunde, funke, ikenna, chiamaka)


def new_session(session: Session, user_id: uuid.UUID, token_hash: bytes | None = None) -> uuid.UUID:
    values = {
        "user_id": user_id,
        "token_hash": secrets.token_bytes(32) if token_hash is None else token_hash,
    }
    session_id: uuid.UUID = session.scalar(NEW_SESSION, values)
    return session_id


def new_link(
    session: Session, user_id: uuid.UUID, purpose: str = "reset", token_hash: bytes | None = None
) -> uuid.UUID:
    values = {
        "user_id": user_id,
        "purpose": purpose,
        "token_hash": secrets.token_bytes(32) if token_hash is None else token_hash,
    }
    link_id: uuid.UUID = session.scalar(NEW_LINK, values)
    return link_id


def changed_ids(session: Session, statement: TextClause, **values: object) -> list[uuid.UUID]:
    """Run an UPDATE or DELETE ... RETURNING and list the rows it really changed."""
    return list(session.scalars(statement, values))


# --- what is stored ---------------------------------------------------------------


def test_sessions_and_links_hold_hashes_not_tokens(db_session: Session) -> None:
    # D-037, D-039: the browser keeps the token; the database keeps only its hash.
    columns = {
        table: set(
            db_session.scalars(
                text(
                    "select column_name from information_schema.columns"
                    " where table_schema = 'public' and table_name = :table"
                ),
                {"table": table},
            )
        )
        for table in ("user_sessions", "account_tokens")
    }

    assert columns == {
        "user_sessions": {
            "id",
            "user_id",
            "token_hash",
            "device_label",
            "ip_address",
            "created_at",
            "last_seen_at",
            "expires_at",
            "revoked_at",
        },
        "account_tokens": {
            "id",
            "user_id",
            "purpose",
            "token_hash",
            "created_at",
            "expires_at",
            "used_at",
            "cancelled_at",
        },
    }


@pytest.mark.parametrize("size", [0, 16, 64])
def test_a_session_hash_is_32_bytes(accounts: Accounts, db_session: Session, size: int) -> None:
    with violates(db_session, "ck_user_sessions_token_hash_length"):
        new_session(db_session, accounts.tunde, token_hash=b"\x01" * size)


@pytest.mark.parametrize("size", [16, 64])
def test_a_link_hash_is_32_bytes(accounts: Accounts, db_session: Session, size: int) -> None:
    with violates(db_session, "ck_account_tokens_token_hash_length"):
        new_link(db_session, accounts.funke, token_hash=b"\x01" * size)


def test_each_session_hash_is_unique(accounts: Accounts, db_session: Session) -> None:
    same = secrets.token_bytes(32)
    new_session(db_session, accounts.tunde, token_hash=same)

    with violates(db_session, "uq_user_sessions_token_hash"):
        new_session(db_session, accounts.funke, token_hash=same)


def test_each_link_hash_is_unique(accounts: Accounts, db_session: Session) -> None:
    same = secrets.token_bytes(32)
    new_link(db_session, accounts.tunde, token_hash=same)

    with violates(db_session, "uq_account_tokens_token_hash"):
        new_link(db_session, accounts.funke, token_hash=same)


def test_a_session_expires_after_it_starts(accounts: Accounts, db_session: Session) -> None:
    with violates(db_session, "ck_user_sessions_expires_after_creation"):
        db_session.execute(
            text(
                "insert into user_sessions (user_id, token_hash, expires_at)"
                " values (:user_id, :token_hash, now() - interval '1 minute')"
            ),
            {"user_id": accounts.tunde, "token_hash": secrets.token_bytes(32)},
        )


def test_a_device_label_is_short(accounts: Accounts, db_session: Session) -> None:
    with violates(db_session, "ck_user_sessions_device_label_length"):
        db_session.execute(
            text(
                "insert into user_sessions (user_id, token_hash, device_label, expires_at)"
                " values (:user_id, :token_hash, :label, now() + interval '1 day')"
            ),
            {"user_id": accounts.tunde, "token_hash": secrets.token_bytes(32), "label": "x" * 201},
        )


@pytest.mark.parametrize("purpose", ["login", "invite", ""])
def test_a_link_is_for_activation_or_reset(
    accounts: Accounts, db_session: Session, purpose: str
) -> None:
    with violates(db_session, "ck_account_tokens_purpose_allowed"):
        new_link(db_session, accounts.funke, purpose)


def test_a_link_expires_after_it_is_made(accounts: Accounts, db_session: Session) -> None:
    with violates(db_session, "ck_account_tokens_expires_after_creation"):
        db_session.execute(
            text(
                "insert into account_tokens (user_id, purpose, token_hash, expires_at)"
                " values (:user_id, 'reset', :token_hash, now())"
            ),
            {"user_id": accounts.funke, "token_hash": secrets.token_bytes(32)},
        )


def test_one_live_link_per_account_and_purpose(accounts: Accounts, db_session: Session) -> None:
    first = new_link(db_session, accounts.funke, "reset")
    new_link(db_session, accounts.funke, "activation")  # another purpose is fine

    with violates(db_session, "ix_account_tokens_one_live_link"):
        new_link(db_session, accounts.funke, "reset")

    # Resending cancels the previous link first (D-039); then a new one can be made.
    db_session.execute(
        text("update account_tokens set cancelled_at = now() where id = :id"), {"id": first}
    )
    new_link(db_session, accounts.funke, "reset")


def test_a_link_is_used_or_cancelled_never_both(accounts: Accounts, db_session: Session) -> None:
    link = new_link(db_session, accounts.funke)

    with violates(db_session, "ck_account_tokens_used_or_cancelled"):
        db_session.execute(
            text("update account_tokens set used_at = now(), cancelled_at = now() where id = :id"),
            {"id": link},
        )


# --- sessions: who may see and end them -------------------------------------------


def test_everyone_manages_their_own_sessions(accounts: Accounts, db_session: Session) -> None:
    # Log in, refresh (rotate the token), sign out of all devices: all as the person.
    with acting_as(db_session, "app_user", user_id=accounts.ikenna):
        mine = new_session(db_session, accounts.ikenna)
        rotated = changed_ids(
            db_session,
            text(
                "update user_sessions set token_hash = :token_hash, last_seen_at = now()"
                " where id = :id returning id"
            ),
            token_hash=secrets.token_bytes(32),
            id=mine,
        )
        ended = changed_ids(db_session, END_SESSIONS, user_id=accounts.ikenna)

    assert rotated == [mine]
    assert ended == [accounts.ikenna]


def test_nobody_starts_a_session_for_someone_else(accounts: Accounts, db_session: Session) -> None:
    with (
        acting_as(db_session, "app_user", school_id=accounts.gmc, user_id=accounts.ngozi),
        refused(db_session),
    ):
        new_session(db_session, accounts.tunde)


def test_a_school_ends_the_sessions_of_its_own_people(
    accounts: Accounts, db_session: Session
) -> None:
    # For example after a reset or a temporary password (D-041) or deactivation (D-037).
    new_session(db_session, accounts.tunde)

    with acting_as(db_session, "app_user", school_id=accounts.gmc, user_id=accounts.ngozi):
        ended = changed_ids(db_session, END_SESSIONS, user_id=accounts.tunde)

    assert ended == [accounts.tunde]


@pytest.mark.parametrize("school", ["gmc", "bsa"])
def test_no_school_sees_or_ends_a_shared_parents_sessions(
    accounts: Accounts, db_session: Session, school: str
) -> None:
    # Denied (D-138, AC03.9): only Ikenna manages his own sessions.
    new_session(db_session, accounts.ikenna)

    with acting_as(db_session, "app_user", school_id=getattr(accounts, school)):
        seen = list(db_session.scalars(SEE_SESSIONS, {"user_id": accounts.ikenna}))
        ended = changed_ids(db_session, END_SESSIONS, user_id=accounts.ikenna)

    assert (seen, ended) == ([], [])


def test_a_school_cannot_see_or_end_another_schools_sessions(
    accounts: Accounts, db_session: Session
) -> None:
    new_session(db_session, accounts.chiamaka)

    with acting_as(db_session, "app_user", school_id=accounts.gmc):
        seen = list(db_session.scalars(SEE_SESSIONS, {"user_id": accounts.chiamaka}))
        ended = changed_ids(db_session, END_SESSIONS, user_id=accounts.chiamaka)

    assert (seen, ended) == ([], [])


def test_the_platform_ends_school_admin_sessions_only(
    accounts: Accounts, db_session: Session
) -> None:
    # F03 rule 5: the super admin signs school admins out of all devices, nobody else.
    new_session(db_session, accounts.ngozi)
    new_session(db_session, accounts.tunde)

    with acting_as(db_session, "app_platform"):
        admin = changed_ids(db_session, END_SESSIONS, user_id=accounts.ngozi)
        teacher = changed_ids(db_session, END_SESSIONS, user_id=accounts.tunde)

    assert admin == [accounts.ngozi]
    assert teacher == []


# --- account links: activation and reset -----------------------------------------


def test_a_school_issues_and_cancels_links_for_its_own_people(
    accounts: Accounts, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=accounts.gmc, user_id=accounts.ngozi):
        link = new_link(db_session, accounts.funke, "reset")
        cancelled = changed_ids(
            db_session,
            text("update account_tokens set cancelled_at = now() where id = :id returning id"),
            id=link,
        )

    assert cancelled == [link]


@pytest.mark.parametrize("school", ["gmc", "bsa"])
def test_no_school_issues_a_link_for_a_shared_parent(
    accounts: Accounts, db_session: Session, school: str
) -> None:
    # Denied (D-138): Ikenna resets his own password with Forgot password.
    with (
        acting_as(db_session, "app_user", school_id=getattr(accounts, school)),
        refused(db_session),
    ):
        new_link(db_session, accounts.ikenna, "reset")


def test_a_school_cannot_issue_links_for_another_schools_people(
    accounts: Accounts, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=accounts.gmc), refused(db_session):
        new_link(db_session, accounts.chiamaka, "reset")


def test_a_school_cannot_read_links_of_shared_or_other_schools_accounts(
    accounts: Accounts, db_session: Session
) -> None:
    new_link(db_session, accounts.ikenna)
    new_link(db_session, accounts.chiamaka)

    with acting_as(db_session, "app_user", school_id=accounts.gmc):
        seen = list(db_session.scalars(text("select user_id from account_tokens")))

    assert seen == []


def test_the_platform_issues_links_for_school_admins_only(
    accounts: Accounts, db_session: Session
) -> None:
    with acting_as(db_session, "app_platform"):
        new_link(db_session, accounts.ngozi, "reset")
        with refused(db_session):
            new_link(db_session, accounts.tunde, "reset")


@pytest.mark.parametrize("role", ["app_user", "app_platform"])
def test_links_are_kept_not_deleted(accounts: Accounts, db_session: Session, role: str) -> None:
    # Used and cancelled links stay as a record; the app may not delete them.
    link = new_link(db_session, accounts.ngozi)

    with acting_as(db_session, role, school_id=accounts.gmc), refused(db_session):
        db_session.execute(text("delete from account_tokens where id = :id"), {"id": link})


# --- other roles and the inventory --------------------------------------------------


@pytest.mark.parametrize("table", ["user_sessions", "account_tokens"])
def test_the_verification_role_cannot_read_sessions_or_links(
    accounts: Accounts, db_session: Session, table: str
) -> None:
    statement = {
        "user_sessions": text("select count(*) from user_sessions"),
        "account_tokens": text("select count(*) from account_tokens"),
    }[table]

    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(statement)


def test_session_and_link_tables_have_row_level_security(db_session: Session) -> None:
    protected = {
        name: on
        for name, on in db_session.execute(
            text(
                "select relname, relrowsecurity from pg_class"
                " where relname in ('user_sessions', 'account_tokens')"
            )
        )
    }

    assert protected == {"user_sessions": True, "account_tokens": True}
