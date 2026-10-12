"""Accounts and school links (BUILD_PROMPT 9.1 item 2; SPEC section 4, F02, F03;
D-033, D-044, D-045, D-048, D-137, D-138).

Behaviour: the database keeps accounts and school links consistent and
private. Usernames and emails are unique the way D-033 says; the super admin
has no school; a student account belongs to its own school; an account is
either staff in one school or a parent in one or more (option 3A); only the
parent can link their account to another school; each school sees only its
own people; and no school can change the login of an account shared with
another school.

Rules are checked as the owner (constraints and triggers) and as the app's
roles (row-level security and grants). All data is fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from tests.db_support import acting_as, refused, violates
from tests.factories import add_membership, create_school, create_user, parent_accepts_link


@dataclass(frozen=True)
class People:
    gmc: uuid.UUID
    bsa: uuid.UUID
    super_admin: uuid.UUID
    ngozi: uuid.UUID  # GMC principal
    tunde: uuid.UUID  # GMC teacher
    funke: uuid.UUID  # parent at GMC only
    ikenna: uuid.UUID  # parent at GMC and BSA: a shared account
    chukwuemeka: uuid.UUID  # GMC student
    chiamaka: uuid.UUID  # BSA head teacher (principal)


@pytest.fixture
def people(db_session: Session) -> People:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    def person(
        username: str,
        full_name: str,
        *,
        is_super_admin: bool = False,
        student_school_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        # Pupils here have no email; everyone else has a fictional one.
        return create_user(
            s,
            username=username,
            full_name=full_name,
            email=None if student_school_id else f"{username}@example.com",
            is_super_admin=is_super_admin,
            student_school_id=student_school_id,
        )

    super_admin = person("platform.admin", "Platform Admin", is_super_admin=True)
    ngozi = person("ngozi.okeke", "Ngozi Okeke")
    add_membership(s, ngozi, gmc, "school_admin", is_primary=True)
    tunde = person("tunde.adebayo", "Tunde Adebayo")
    add_membership(s, tunde, gmc, "teacher")
    funke = person("funke.adeyemi", "Funke Adeyemi")
    add_membership(s, funke, gmc, "parent")
    ikenna = person("ikenna.obi", "Ikenna Obi")
    add_membership(s, ikenna, gmc, "parent")
    parent_accepts_link(s, ikenna, bsa)
    chukwuemeka = person("chukwuemeka.obi", "Chukwuemeka Obi", student_school_id=gmc)
    add_membership(s, chukwuemeka, gmc, "student")
    chiamaka = person("chiamaka.nwafor", "Chiamaka Nwafor")
    add_membership(s, chiamaka, bsa, "school_admin", is_primary=True)
    return People(gmc, bsa, super_admin, ngozi, tunde, funke, ikenna, chukwuemeka, chiamaka)


def visible_usernames(session: Session) -> list[str]:
    return list(session.scalars(text("select username from users order by username")))


def changed_ids(session: Session, statement: TextClause, **values: object) -> list[uuid.UUID]:
    """Run an UPDATE or DELETE ... RETURNING id and list the rows it really changed."""
    return list(session.scalars(statement, values))


# --- users: who an account is -------------------------------------------------


@pytest.mark.parametrize("username", ["ab", "ngozi okeke", "ngozi@okeke", "Ngozi.Okeke", "a" * 31])
def test_username_is_3_to_30_lowercase_letters_numbers_dots_dashes(
    db_session: Session, username: str
) -> None:
    with violates(db_session, "ck_users_username_format"):
        create_user(db_session, username=username, full_name="Test Person")


def test_staff_and_parent_usernames_are_unique_across_the_platform(db_session: Session) -> None:
    create_user(db_session, username="tunde.adebayo", full_name="Tunde Adebayo")

    with violates(db_session, "ix_users_username_platform"):
        create_user(db_session, username="tunde.adebayo", full_name="Another Tunde")


def test_student_usernames_are_unique_within_their_school(db_session: Session) -> None:
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    create_user(db_session, username="kosi.obi", full_name="Kosi Obi", student_school_id=gmc)
    # Another school may use the same student username (AC02.6).
    create_user(db_session, username="kosi.obi", full_name="Kosi Obi", student_school_id=bsa)

    with violates(db_session, "ix_users_username_per_school"):
        create_user(db_session, username="kosi.obi", full_name="Kosi Okoro", student_school_id=gmc)


def test_a_student_username_may_match_a_staff_username(db_session: Session) -> None:
    # Pupils log in on the Student tab with their school code, so this never clashes.
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")
    create_user(db_session, username="ada.eze", full_name="Ada Eze")
    create_user(db_session, username="ada.eze", full_name="Ada Eze", student_school_id=gmc)

    assert db_session.scalar(text("select count(*) from users where username = 'ada.eze'")) == 2


@pytest.mark.parametrize(
    "email", ["Ngozi.Okeke@Example.com", "ngozi.okeke.example.com", "ngozi okeke@example.com"]
)
def test_emails_are_lowercase_and_look_like_emails(db_session: Session, email: str) -> None:
    with violates(db_session, "ck_users_email_format"):
        create_user(db_session, username="ngozi.okeke", full_name="Ngozi Okeke", email=email)


def test_an_email_belongs_to_one_account_on_the_whole_platform(db_session: Session) -> None:
    create_user(
        db_session, username="ikenna.obi", full_name="Ikenna Obi", email="ikenna.obi@example.com"
    )

    with violates(db_session, "uq_users_email"):
        create_user(
            db_session, username="ikenna.o", full_name="Ikenna Obi", email="ikenna.obi@example.com"
        )


def test_the_super_admin_is_never_a_student(db_session: Session) -> None:
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")

    with violates(db_session, "ck_users_super_admin_not_student"):
        create_user(
            db_session,
            username="platform.admin",
            full_name="Platform Admin",
            is_super_admin=True,
            student_school_id=gmc,
        )


def test_a_temporary_password_must_be_changed_at_first_login(db_session: Session) -> None:
    with violates(db_session, "ck_users_temporary_password_must_change"):
        db_session.execute(
            text(
                "insert into users (username, full_name, temp_password_expires_at)"
                " values ('musa.ibrahim', 'Musa Ibrahim', now() + interval '7 days')"
            )
        )


@pytest.mark.parametrize("full_name", ["", "   "])
def test_full_name_cannot_be_blank(db_session: Session, full_name: str) -> None:
    with violates(db_session, "ck_users_full_name_valid"):
        create_user(db_session, username="musa.ibrahim", full_name=full_name)


# --- school_memberships: links between accounts and schools --------------------


@pytest.mark.parametrize("role", ["super_admin", "principal", "bursar"])
def test_a_membership_role_is_one_of_the_five_school_roles(
    people: People, db_session: Session, role: str
) -> None:
    newcomer = create_user(db_session, username="sola.bello", full_name="Sola Bello")

    with violates(db_session, "ck_school_memberships_role_allowed"):
        add_membership(db_session, newcomer, people.gmc, role)


@pytest.mark.parametrize("status", ["invited", "deleted"])
def test_a_membership_is_active_or_paused(people: People, db_session: Session, status: str) -> None:
    with violates(db_session, "ck_school_memberships_status_allowed"):
        db_session.execute(
            text("update school_memberships set status = :status where user_id = :id"),
            {"status": status, "id": people.tunde},
        )


def test_an_account_has_one_link_per_school(people: People, db_session: Session) -> None:
    with violates(db_session, "uq_school_memberships_user_id_school_id"):
        add_membership(db_session, people.funke, people.gmc, "parent")


def test_staff_work_in_one_school_only(people: People, db_session: Session) -> None:
    with violates(db_session, "ix_school_memberships_one_non_parent_school"):
        add_membership(db_session, people.tunde, people.bsa, "teacher")


def test_a_parent_can_be_linked_to_several_schools(people: People, db_session: Session) -> None:
    schools = set(
        db_session.scalars(
            text("select school_id from school_memberships where user_id = :id"),
            {"id": people.ikenna},
        )
    )

    assert schools == {people.gmc, people.bsa}


def test_an_account_is_staff_or_parent_not_both(people: People, db_session: Session) -> None:
    # Option 3A: staff who are also parents use a separate parent account for now.
    use_context(db_session, user_id=people.tunde)
    with violates(db_session, "school_memberships_parent_or_staff"):
        add_membership(db_session, people.tunde, people.bsa, "parent")

    with violates(db_session, "school_memberships_parent_or_staff"):
        add_membership(db_session, people.funke, people.bsa, "teacher")


def test_the_principal_is_a_school_admin(people: People, db_session: Session) -> None:
    emeka = create_user(db_session, username="emeka.nwosu", full_name="Emeka Nwosu")

    with violates(db_session, "ck_school_memberships_primary_is_school_admin"):
        add_membership(db_session, emeka, people.bsa, "reviewer", is_primary=True)


def test_a_school_has_one_principal(people: People, db_session: Session) -> None:
    chukwudi = create_user(db_session, username="chukwudi.eze", full_name="Chukwudi Eze")

    with violates(db_session, "ix_school_memberships_one_principal"):
        add_membership(db_session, chukwudi, people.gmc, "school_admin", is_primary=True)


def test_the_super_admin_has_no_school(people: People, db_session: Session) -> None:
    with violates(db_session, "school_memberships_not_super_admin"):
        add_membership(db_session, people.super_admin, people.gmc, "school_admin")


def test_a_student_account_is_a_student_of_its_own_school_only(
    people: People, db_session: Session
) -> None:
    with violates(db_session, "school_memberships_student_account"):
        add_membership(db_session, people.chukwuemeka, people.bsa, "student")
    with violates(db_session, "school_memberships_student_account"):
        add_membership(db_session, people.chukwuemeka, people.bsa, "parent")
    with violates(db_session, "school_memberships_student_account"):
        add_membership(db_session, people.tunde, people.bsa, "student")


def test_linking_an_account_already_in_another_school_needs_the_parent(
    people: People, db_session: Session
) -> None:
    # Denied (D-138): nobody but Funke can attach her GMC account to BSA.
    with violates(db_session, "school_memberships_link_needs_consent"):
        add_membership(db_session, people.funke, people.bsa, "parent")

    # Funke herself accepts BSA's link request.
    parent_accepts_link(db_session, people.funke, people.bsa)


# --- row-level security: what each school sees ----------------------------------


def test_a_school_sees_only_its_own_people(people: People, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=people.gmc):
        gmc = visible_usernames(db_session)
    with acting_as(db_session, "app_user", school_id=people.bsa):
        bsa = visible_usernames(db_session)

    assert gmc == ["chukwuemeka.obi", "funke.adeyemi", "ikenna.obi", "ngozi.okeke", "tunde.adebayo"]
    assert bsa == ["chiamaka.nwafor", "ikenna.obi"]


def test_everyone_sees_their_own_account(people: People, db_session: Session) -> None:
    with acting_as(db_session, "app_user", user_id=people.super_admin):
        assert visible_usernames(db_session) == ["platform.admin"]


def test_a_school_sees_its_own_links_and_a_parent_sees_all_of_theirs(
    people: People, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=people.bsa):
        bsa_links = set(db_session.scalars(text("select user_id from school_memberships")))
    with acting_as(db_session, "app_user", user_id=people.ikenna):
        ikenna_schools = set(db_session.scalars(text("select school_id from school_memberships")))

    assert bsa_links == {people.chiamaka, people.ikenna}
    assert ikenna_schools == {people.gmc, people.bsa}


# --- shared accounts: only the parent manages the login (D-138, AC03.9) ----------

LOGIN_CHANGES = {
    "temporary password": text(
        "update users set password_hash = 'not-a-real-hash', must_change_password = true"
        " where id = :id returning id"
    ),
    "new email": text(
        "update users set email = 'someone.else@example.com' where id = :id returning id"
    ),
    "deactivate": text("update users set is_active = false where id = :id returning id"),
}


@pytest.mark.parametrize("change", list(LOGIN_CHANGES))
def test_a_school_manages_the_login_of_its_own_people(
    people: People, db_session: Session, change: str
) -> None:
    with acting_as(db_session, "app_user", school_id=people.gmc):
        changed = changed_ids(db_session, LOGIN_CHANGES[change], id=people.funke)

    assert changed == [people.funke]


@pytest.mark.parametrize("change", list(LOGIN_CHANGES))
@pytest.mark.parametrize("school", ["gmc", "bsa"])
def test_no_school_can_change_a_shared_parents_login(
    people: People, db_session: Session, change: str, school: str
) -> None:
    # Denied: either school could otherwise take over a login that also opens the other's children.
    with acting_as(db_session, "app_user", school_id=getattr(people, school)):
        changed = changed_ids(db_session, LOGIN_CHANGES[change], id=people.ikenna)

    assert changed == []


def test_the_shared_parent_manages_their_own_login(people: People, db_session: Session) -> None:
    with acting_as(db_session, "app_user", user_id=people.ikenna):
        changed = changed_ids(db_session, LOGIN_CHANGES["new email"], id=people.ikenna)

    assert changed == [people.ikenna]


def test_a_school_cannot_change_another_schools_people(people: People, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=people.bsa):
        changed = changed_ids(db_session, LOGIN_CHANGES["deactivate"], id=people.tunde)

    assert changed == []


ACCOUNT_TYPE_CHANGES = {
    "make super admin": text("update users set is_super_admin = true where id = :id"),
    "move student": text("update users set student_school_id = null where id = :id"),
}


@pytest.mark.parametrize("change", list(ACCOUNT_TYPE_CHANGES))
def test_school_users_cannot_change_what_kind_of_account_it_is(
    people: People, db_session: Session, change: str
) -> None:
    with acting_as(db_session, "app_user", school_id=people.gmc), refused(db_session):
        db_session.execute(ACCOUNT_TYPE_CHANGES[change], {"id": people.chukwuemeka})


# --- school users managing links ------------------------------------------------


def test_a_school_creates_an_account_then_links_it(people: People, db_session: Session) -> None:
    # The app makes the id itself, so the insert needs no RETURNING: until the
    # link exists, row-level security hides the new account even from its school.
    emeka = uuid.uuid4()
    with acting_as(db_session, "app_user", school_id=people.gmc, user_id=people.ngozi):
        db_session.execute(
            text(
                "insert into users (id, username, full_name, email)"
                " values (:id, 'emeka.nwosu', 'Emeka Nwosu', 'emeka.nwosu@example.com')"
            ),
            {"id": emeka},
        )
        before_link = visible_usernames(db_session)
        add_membership(db_session, emeka, people.gmc, "reviewer")
        after_link = visible_usernames(db_session)

    assert "emeka.nwosu" not in before_link
    assert "emeka.nwosu" in after_link


def test_a_school_cannot_create_a_super_admin_or_another_schools_student(
    people: People, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=people.gmc):
        with refused(db_session):  # no permission on is_super_admin at all
            db_session.execute(
                text(
                    "insert into users (username, full_name, is_super_admin)"
                    " values ('fake.admin', 'Fake Admin', true)"
                )
            )
        with refused(db_session):  # row-level security: a pupil of another school
            db_session.execute(
                text(
                    "insert into users (id, username, full_name, student_school_id)"
                    " values (:id, 'kosi.obi', 'Kosi Obi', :school)"
                ),
                {"id": uuid.uuid4(), "school": people.bsa},
            )


def test_a_school_cannot_add_people_to_another_school(people: People, db_session: Session) -> None:
    newcomer = create_user(db_session, username="sola.bello", full_name="Sola Bello")

    with acting_as(db_session, "app_user", school_id=people.gmc), refused(db_session):
        add_membership(db_session, newcomer, people.bsa, "teacher")


def test_a_school_cannot_make_pause_or_remove_a_principal(
    people: People, db_session: Session
) -> None:
    # Denied (F03 rule 5, D-048): only the super admin names or changes a principal.
    chukwudi = create_user(db_session, username="chukwudi.eze", full_name="Chukwudi Eze")
    with acting_as(db_session, "app_user", school_id=people.gmc):
        with refused(db_session):  # no permission on is_primary at all
            add_membership(db_session, chukwudi, people.gmc, "school_admin", is_primary=True)
        paused = changed_ids(
            db_session,
            text(
                "update school_memberships set status = 'paused' where user_id = :id returning id"
            ),
            id=people.ngozi,
        )
        removed = changed_ids(
            db_session,
            text("delete from school_memberships where user_id = :id returning id"),
            id=people.ngozi,
        )

    assert (paused, removed) == ([], [])


def test_a_school_can_pause_its_own_link_to_a_shared_parent(
    people: People, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=people.bsa):
        paused = changed_ids(
            db_session,
            text(
                "update school_memberships set status = 'paused'"
                " where user_id = :id returning school_id"
            ),
            id=people.ikenna,
        )
    statuses = {
        school_id: status
        for school_id, status in db_session.execute(
            text("select school_id, status from school_memberships where user_id = :id"),
            {"id": people.ikenna},
        )
    }

    assert paused == [people.bsa]
    assert statuses == {people.bsa: "paused", people.gmc: "active"}


def test_a_school_can_remove_its_own_link_to_a_shared_parent(
    people: People, db_session: Session
) -> None:
    with acting_as(db_session, "app_user", school_id=people.bsa):
        removed = changed_ids(
            db_session,
            text("delete from school_memberships where user_id = :id returning school_id"),
            id=people.ikenna,
        )
    remaining = list(
        db_session.scalars(
            text("select school_id from school_memberships where user_id = :id"),
            {"id": people.ikenna},
        )
    )

    assert removed == [people.bsa]
    assert remaining == [people.gmc]


def test_only_the_parent_can_link_their_account_to_another_school(
    people: People, db_session: Session
) -> None:
    # Denied (AT-31.5): BSA's head teacher cannot attach Funke's GMC account to BSA.
    with acting_as(db_session, "app_user", school_id=people.bsa, user_id=people.chiamaka):  # noqa: SIM117
        with violates(db_session, "school_memberships_link_needs_consent"):
            add_membership(db_session, people.funke, people.bsa, "parent")

    # Funke herself accepts BSA's link request.
    with acting_as(db_session, "app_user", school_id=people.bsa, user_id=people.funke):
        add_membership(db_session, people.funke, people.bsa, "parent")


def test_nobody_can_join_a_school_as_staff_by_themselves(
    people: People, db_session: Session
) -> None:
    sola = create_user(db_session, username="sola.bello", full_name="Sola Bello")

    with acting_as(db_session, "app_user", school_id=people.bsa, user_id=sola), refused(db_session):
        add_membership(db_session, sola, people.bsa, "school_admin")


# --- the platform and verification roles ----------------------------------------


def test_the_platform_sees_admin_accounts_only(people: People, db_session: Session) -> None:
    # D-051: no teachers, parents or pupils, only school admins and the super admin.
    with acting_as(db_session, "app_platform"):
        assert visible_usernames(db_session) == ["chiamaka.nwafor", "ngozi.okeke", "platform.admin"]


def test_the_platform_creates_principals_but_no_other_roles(
    people: People, db_session: Session
) -> None:
    rcs = create_school(
        db_session, code="RCS", name="Royal Crest Schools", school_type="all_levels"
    )
    principal, teacher = uuid.uuid4(), uuid.uuid4()
    with acting_as(db_session, "app_platform"):
        for user_id, username in ((principal, "bola.adeyemi"), (teacher, "yemi.okafor")):
            db_session.execute(
                text(
                    "insert into users (id, username, full_name) values (:id, :name, 'Test Person')"
                ),
                {"id": user_id, "name": username},
            )
        add_membership(db_session, principal, rcs, "school_admin", is_primary=True)
        with refused(db_session):
            add_membership(db_session, teacher, rcs, "teacher")


@pytest.mark.parametrize("table", ["users", "school_memberships"])
def test_the_verification_role_cannot_read_accounts(
    people: People, db_session: Session, table: str
) -> None:
    statement = {
        "users": text("select count(*) from users"),
        "school_memberships": text("select count(*) from school_memberships"),
    }[table]

    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(statement)


def test_account_tables_have_row_level_security(db_session: Session) -> None:
    rows = {
        name: protected
        for name, protected in db_session.execute(
            text(
                "select relname, relrowsecurity from pg_class"
                " where relname in ('users', 'school_memberships')"
            )
        )
    }

    assert rows == {"users": True, "school_memberships": True}
