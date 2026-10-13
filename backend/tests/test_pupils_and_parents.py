"""Pupils, parents and enrolment (BUILD_PROMPT 9.1 item 4, first part; SPEC F05, F07,
F21; AC02.6, AC05.2; D-137, D-138, D-139, D-140).

Behaviour: each school keeps its own pupils (admission numbers unique within
the school; names as surname, first name and other names), its own record of
each parent, the links between them, the link requests waiting for a parent,
and each pupil's enrolment and subjects per session. Every row stays inside
its school; a pupil's or parent's login must really be a pupil or parent of
that school; and a pupil only takes subjects their arm offers.
All data is fictional (design brief section 12).
"""

import secrets
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_arm_subject,
    add_membership,
    add_student_subject,
    create_arm,
    create_class,
    create_department,
    create_guardian,
    create_link_request,
    create_school,
    create_session,
    create_student,
    create_subject,
    create_user,
    enrol,
    link_ward,
)

TABLES = (
    "students",
    "guardians",
    "guardian_students",
    "parent_link_requests",
    "enrolments",
    "student_subjects",
)
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608


@dataclass(frozen=True)
class World:
    gmc: uuid.UUID
    bsa: uuid.UUID
    gmc_session: uuid.UUID
    jss1a: uuid.UUID
    jss1b: uuid.UUID
    mathematics: uuid.UUID
    english: uuid.UUID
    igbo: uuid.UUID
    tunde: uuid.UUID  # GMC teacher account
    ikenna: uuid.UUID  # GMC parent account
    chukwuemeka_login: uuid.UUID  # GMC pupil account
    chukwuemeka: uuid.UUID  # GMC pupil record, GMC/2026/014
    musa: uuid.UUID  # GMC pupil without a login
    ikenna_at_gmc: uuid.UUID  # GMC's guardian record for Ikenna
    chukwuemeka_jss1a: uuid.UUID  # his 2026/2027 enrolment
    bsa_sciences: uuid.UUID
    kosi: uuid.UUID  # BSA pupil, admission number 2026/014
    bsa_primary4a: uuid.UUID
    bsa_session: uuid.UUID


@pytest.fixture
def world(db_session: Session) -> World:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    # GMC: JSS 1A takes Mathematics, English and Igbo; JSS 1B no Igbo.
    gmc_session = create_session(s, gmc)
    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a, jss1b = create_arm(s, gmc, jss1, "A"), create_arm(s, gmc, jss1, "B")
    mathematics = create_subject(s, gmc, "Mathematics")
    english = create_subject(s, gmc, "English Language")
    igbo = create_subject(s, gmc, "Igbo Language")
    for arm, subject in ((jss1a, mathematics), (jss1a, english), (jss1a, igbo)):
        add_arm_subject(s, gmc, arm, subject)
    for subject in (mathematics, english):
        add_arm_subject(s, gmc, jss1b, subject)

    tunde = create_user(s, username="tunde.adebayo", full_name="Tunde Adebayo")
    add_membership(s, tunde, gmc, "teacher")
    ikenna = create_user(
        s, username="ikenna.obi", full_name="Ikenna Obi", email="ikenna.obi@example.com"
    )
    add_membership(s, ikenna, gmc, "parent")
    chukwuemeka_login = create_user(
        s, username="chukwuemeka.obi", full_name="Chukwuemeka Obi", student_school_id=gmc
    )
    add_membership(s, chukwuemeka_login, gmc, "student")

    chukwuemeka = create_student(
        s, gmc, "GMC/2026/014", "Obi", "Chukwuemeka", user_id=chukwuemeka_login
    )
    musa = create_student(s, gmc, "GMC/2026/015", "Ibrahim", "Musa")
    ikenna_at_gmc = create_guardian(
        s, gmc, "Ikenna Obi", email="ikenna.obi@example.com", user_id=ikenna
    )
    link_ward(s, gmc, ikenna_at_gmc, chukwuemeka, "Father")
    # Musa's mother has not set up her login yet: GMC's request waits for her.
    hauwa_at_gmc = create_guardian(s, gmc, "Hauwa Ibrahim", email="hauwa.ibrahim@example.com")
    link_ward(s, gmc, hauwa_at_gmc, musa, "Mother")
    create_link_request(s, gmc, hauwa_at_gmc, "hauwa.ibrahim@example.com")
    chukwuemeka_jss1a = enrol(s, gmc, chukwuemeka, gmc_session, jss1a)
    for subject in (mathematics, english):  # he does not take Igbo
        add_student_subject(s, gmc, chukwuemeka_jss1a, subject)

    # BSA: Kosi Obi in Primary 4A; BSA's record of Ikenna waits for him (D-138, D-140).
    bsa_session = create_session(s, bsa)
    primary4 = create_class(s, bsa, "primary", "Primary 4")
    bsa_primary4a = create_arm(s, bsa, primary4, "A")
    bsa_mathematics = create_subject(s, bsa, "Mathematics")
    add_arm_subject(s, bsa, bsa_primary4a, bsa_mathematics)
    bsa_sciences = create_department(s, bsa, "Sciences")
    kosi = create_student(s, bsa, "2026/014", "Obi", "Kosi", gender="female")
    ikenna_at_bsa = create_guardian(s, bsa, "Mr. Ikenna Obi", email="ikenna.obi@example.com")
    link_ward(s, bsa, ikenna_at_bsa, kosi, "Father")
    create_link_request(s, bsa, ikenna_at_bsa, "ikenna.obi@example.com")
    kosi_primary4a = enrol(s, bsa, kosi, bsa_session, bsa_primary4a)
    add_student_subject(s, bsa, kosi_primary4a, bsa_mathematics)

    return World(
        gmc,
        bsa,
        gmc_session,
        jss1a,
        jss1b,
        mathematics,
        english,
        igbo,
        tunde,
        ikenna,
        chukwuemeka_login,
        chukwuemeka,
        musa,
        ikenna_at_gmc,
        chukwuemeka_jss1a,
        bsa_sciences,
        kosi,
        bsa_primary4a,
        bsa_session,
    )


# --- pupils ---------------------------------------------------------------------


def test_admission_numbers_are_unique_within_a_school(world: World, db_session: Session) -> None:
    with violates(db_session, "ix_students_unique_admission_number"):
        create_student(db_session, world.gmc, "gmc/2026/014", "Okafor", "Chinedu")


def test_two_schools_may_use_the_same_admission_number(world: World, db_session: Session) -> None:
    # AC02.6: GMC and BSA can both have 2026/014; logins never mix (school code first).
    create_student(db_session, world.gmc, "2026/014", "Yusuf", "Zainab", gender="female")

    count = db_session.scalar(
        text("select count(*) from students where admission_number = '2026/014'")
    )
    assert count == 2


@pytest.mark.parametrize("number", ["", " GMC/2026/016", "GMC 2026 016", "x" * 31])
def test_an_admission_number_is_short_with_no_spaces(
    world: World, db_session: Session, number: str
) -> None:
    with violates(db_session, "ck_students_admission_number_format"):
        create_student(db_session, world.gmc, number, "Bello", "Amina", gender="female")


@pytest.mark.parametrize(
    ("surname", "first_name", "rule"),
    [
        ("", "Amina", "ck_students_surname_valid"),
        ("Bello", "  ", "ck_students_first_name_valid"),
        ("B" * 61, "Amina", "ck_students_surname_valid"),
    ],
)
def test_a_pupil_has_a_surname_and_a_first_name(
    world: World, db_session: Session, surname: str, first_name: str, rule: str
) -> None:
    # D-139: surname, first name and other names.
    with violates(db_session, rule):
        create_student(db_session, world.gmc, "GMC/2026/016", surname, first_name)


def test_other_names_are_optional_but_never_blank(world: World, db_session: Session) -> None:
    with violates(db_session, "ck_students_other_names_valid"):
        db_session.execute(
            text("update students set other_names = '' where id = :id"), {"id": world.musa}
        )


@pytest.mark.parametrize("gender", ["m", "F", ""])
def test_gender_is_female_or_male(world: World, db_session: Session, gender: str) -> None:
    with violates(db_session, "ck_students_gender_allowed"):
        create_student(db_session, world.gmc, "GMC/2026/016", "Bello", "Amina", gender=gender)


def test_status_is_active_withdrawn_or_graduated(world: World, db_session: Session) -> None:
    with violates(db_session, "ck_students_status_allowed"):
        db_session.execute(
            text("update students set status = 'expelled' where id = :id"), {"id": world.musa}
        )


def test_a_pupils_login_must_be_a_pupil_of_that_school(world: World, db_session: Session) -> None:
    # Denied: a teacher's account cannot become a pupil's login.
    with violates(db_session, "students_user_id_is_student"):
        create_student(
            db_session, world.gmc, "GMC/2026/016", "Adebayo", "Tunde", user_id=world.tunde
        )


def test_one_pupil_record_per_login(world: World, db_session: Session) -> None:
    with violates(db_session, "uq_students_user_id"):
        create_student(
            db_session, world.gmc, "GMC/2026/016", "Obi", "Emeka", user_id=world.chukwuemeka_login
        )


def test_a_pupil_may_have_no_login(world: World, db_session: Session) -> None:
    # Nursery pupils usually have no login of their own (F14).
    login = db_session.scalar(
        text("select user_id from students where id = :id"), {"id": world.musa}
    )

    assert login is None


def test_a_pupils_department_is_in_the_same_school(world: World, db_session: Session) -> None:
    with violates(db_session, "fk_students_department_id_departments"):
        db_session.execute(
            text("update students set department_id = :department where id = :id"),
            {"department": world.bsa_sciences, "id": world.musa},
        )


# --- parents (the school's guardian records) --------------------------------------


def test_a_parents_login_must_be_a_parent_of_that_school(world: World, db_session: Session) -> None:
    with violates(db_session, "guardians_user_id_is_parent"):
        create_guardian(db_session, world.gmc, "Tunde Adebayo", user_id=world.tunde)


def test_one_guardian_record_per_account_per_school(world: World, db_session: Session) -> None:
    with violates(db_session, "uq_guardians_school_id_user_id"):
        create_guardian(db_session, world.gmc, "Ikenna Obi", user_id=world.ikenna)


@pytest.mark.parametrize("email", ["Ikenna.Obi@Example.com", "ikenna.obi.example.com"])
def test_a_guardian_email_is_lowercase(world: World, db_session: Session, email: str) -> None:
    with violates(db_session, "ck_guardians_email_format"):
        create_guardian(db_session, world.gmc, "Ada Eze", email=email)


@pytest.mark.parametrize("phone", ["call me", "12", "0803-CALL-NOW"])
def test_a_guardian_phone_looks_like_a_phone_number(
    world: World, db_session: Session, phone: str
) -> None:
    with violates(db_session, "ck_guardians_phone_format"):
        db_session.execute(
            text("update guardians set phone = :phone where id = :id"),
            {"phone": phone, "id": world.ikenna_at_gmc},
        )


@pytest.mark.parametrize("phone", ["08030001122", "0803 000 1122", "+234 803 000 1122"])
def test_nigerian_phone_formats_are_accepted(world: World, db_session: Session, phone: str) -> None:
    db_session.execute(
        text("update guardians set phone = :phone where id = :id"),
        {"phone": phone, "id": world.ikenna_at_gmc},
    )


def test_a_ward_link_needs_a_relationship(world: World, db_session: Session) -> None:
    with violates(db_session, "ck_guardian_students_relationship_valid"):
        link_ward(db_session, world.gmc, world.ikenna_at_gmc, world.musa, " ")


def test_a_guardian_is_linked_to_a_pupil_once(world: World, db_session: Session) -> None:
    with violates(db_session, "uq_guardian_students_guardian_id_student_id"):
        link_ward(db_session, world.gmc, world.ikenna_at_gmc, world.chukwuemeka, "Father")


def test_wards_are_in_the_same_school_as_the_guardian(world: World, db_session: Session) -> None:
    # Denied: GMC's guardian record cannot be linked to BSA's pupil.
    with violates(db_session, "fk_guardian_students_student_id_students"):
        link_ward(db_session, world.gmc, world.ikenna_at_gmc, world.kosi, "Father")


# --- link requests waiting for a parent (D-138, D-140) ----------------------------


def test_one_open_link_request_per_guardian(world: World, db_session: Session) -> None:
    ada = create_guardian(db_session, world.gmc, "Ada Eze", email="ada.eze@example.com")
    first = create_link_request(db_session, world.gmc, ada, "ada.eze@example.com")

    with violates(db_session, "ix_parent_link_requests_one_open_per_guardian"):
        create_link_request(db_session, world.gmc, ada, "ada.eze@example.com")

    # The school cancels the first request; then it can send a new one.
    db_session.execute(
        text("update parent_link_requests set cancelled_at = now() where id = :id"), {"id": first}
    )
    create_link_request(db_session, world.gmc, ada, "ada.eze@example.com")


def test_a_link_request_ends_only_once(world: World, db_session: Session) -> None:
    ada = create_guardian(db_session, world.gmc, "Ada Eze", email="ada.eze@example.com")
    request = create_link_request(db_session, world.gmc, ada, "ada.eze@example.com")

    with violates(db_session, "ck_parent_link_requests_one_outcome"):
        db_session.execute(
            text(
                "update parent_link_requests set accepted_at = now(), cancelled_at = now()"
                " where id = :id"
            ),
            {"id": request},
        )


@pytest.mark.parametrize(
    ("email", "token_hash", "rule"),
    [
        ("Ada.Eze@Example.com", None, "ck_parent_link_requests_email_format"),
        ("ada.eze@example.com", b"\x01" * 16, "ck_parent_link_requests_token_hash_length"),
    ],
)
def test_a_link_request_holds_a_lowercase_email_and_a_hash(
    world: World, db_session: Session, email: str, token_hash: bytes | None, rule: str
) -> None:
    ada = create_guardian(db_session, world.gmc, "Ada Eze")

    with violates(db_session, rule):
        create_link_request(db_session, world.gmc, ada, email, token_hash=token_hash)


def test_a_link_request_expires_after_it_is_made(world: World, db_session: Session) -> None:
    ada = create_guardian(db_session, world.gmc, "Ada Eze")

    with violates(db_session, "ck_parent_link_requests_expires_after_creation"):
        db_session.execute(
            text(
                "insert into parent_link_requests (school_id, guardian_id, email, token_hash,"
                " expires_at) values (:school, :guardian, 'ada.eze@example.com', :hash, now())"
            ),
            {"school": world.gmc, "guardian": ada, "hash": secrets.token_bytes(32)},
        )


# --- enrolment and subjects ---------------------------------------------------------


def test_one_current_enrolment_per_pupil_per_session(world: World, db_session: Session) -> None:
    with violates(db_session, "ix_enrolments_one_current_per_session"):
        enrol(db_session, world.gmc, world.chukwuemeka, world.gmc_session, world.jss1b)


def test_moving_arms_keeps_history(world: World, db_session: Session) -> None:
    # F05: he leaves JSS 1A and joins JSS 1B; both enrolments stay on record.
    db_session.execute(
        text("update enrolments set left_on = current_date where id = :id"),
        {"id": world.chukwuemeka_jss1a},
    )
    enrol(db_session, world.gmc, world.chukwuemeka, world.gmc_session, world.jss1b)

    arms = db_session.scalar(
        text("select count(distinct arm_id) from enrolments where student_id = :id"),
        {"id": world.chukwuemeka},
    )
    assert arms == 2


def test_leaving_comes_after_enrolling(world: World, db_session: Session) -> None:
    with violates(db_session, "ck_enrolments_left_after_enrolled"):
        db_session.execute(
            text("update enrolments set left_on = enrolled_on - 1 where id = :id"),
            {"id": world.chukwuemeka_jss1a},
        )


def test_an_enrolment_stays_in_the_pupils_school(world: World, db_session: Session) -> None:
    with violates(db_session, "fk_enrolments_arm_id_class_arms"):
        enrol(db_session, world.gmc, world.musa, world.gmc_session, world.bsa_primary4a)


def test_a_pupil_takes_only_subjects_their_arm_offers(world: World, db_session: Session) -> None:
    musa_jss1b = enrol(db_session, world.gmc, world.musa, world.gmc_session, world.jss1b)

    with violates(db_session, "student_subjects_subject_in_arm"):
        add_student_subject(db_session, world.gmc, musa_jss1b, world.igbo)


def test_a_pupil_takes_each_subject_once(world: World, db_session: Session) -> None:
    with violates(db_session, "uq_student_subjects_enrolment_id_subject_id"):
        add_student_subject(db_session, world.gmc, world.chukwuemeka_jss1a, world.mathematics)


def test_a_sheet_lists_only_pupils_who_take_the_subject(world: World, db_session: Session) -> None:
    # AC05.2: the Igbo Language sheet for JSS 1A does not list Chukwuemeka.
    takers = text(
        "select st.admission_number from student_subjects ss"
        " join enrolments e on e.id = ss.enrolment_id and e.left_on is null"
        " join students st on st.id = e.student_id"
        " where e.arm_id = :arm and ss.subject_id = :subject"
    )

    mathematics = list(
        db_session.scalars(takers, {"arm": world.jss1a, "subject": world.mathematics})
    )
    igbo = list(db_session.scalars(takers, {"arm": world.jss1a, "subject": world.igbo}))

    assert mathematics == ["GMC/2026/014"]
    assert igbo == []


# --- row-level security ----------------------------------------------------------


@pytest.mark.parametrize("table", TABLES)
def test_a_school_sees_only_its_own_pupils_and_parents(
    world: World, db_session: Session, table: str
) -> None:
    with acting_as(db_session, "app_user", school_id=world.gmc):
        gmc = db_session.scalar(COUNT[table])
    with acting_as(db_session, "app_user", school_id=world.bsa):
        bsa = db_session.scalar(COUNT[table])
    total = db_session.scalar(COUNT[table])

    assert gmc >= 1
    assert bsa >= 1
    assert gmc + bsa == total


def test_a_school_cannot_read_another_schools_pupil_by_id(
    world: World, db_session: Session
) -> None:
    # Denied (AT-27.1): row-level security returns nothing even if the app check were skipped.
    with acting_as(db_session, "app_user", school_id=world.bsa):
        found = db_session.scalar(
            text("select count(*) from students where id = :id"), {"id": world.chukwuemeka}
        )

    assert found == 0


@pytest.mark.parametrize("build", ["pupil", "guardian", "enrolment"])
def test_a_school_cannot_add_pupils_or_parents_to_another_school(
    world: World, db_session: Session, build: str
) -> None:
    # Denied (AT-08.8): GMC cannot create anything in BSA.
    builders = {
        "pupil": lambda: create_student(db_session, world.bsa, "2026/099", "Eze", "Ebube"),
        "guardian": lambda: create_guardian(db_session, world.bsa, "Ada Eze"),
        "enrolment": lambda: enrol(
            db_session, world.bsa, world.kosi, world.bsa_session, world.bsa_primary4a
        ),
    }
    with acting_as(db_session, "app_user", school_id=world.gmc), refused(db_session):
        builders[build]()


def test_link_requests_are_kept_not_deleted(world: World, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=world.bsa), refused(db_session):
        db_session.execute(text("delete from parent_link_requests"))


@pytest.mark.parametrize(
    "statement",
    [
        "update enrolments set arm_id = :arm",
        "update student_subjects set subject_id = :subject",
    ],
)
def test_history_is_changed_by_adding_rows_not_editing_them(
    world: World, db_session: Session, statement: str
) -> None:
    # Denied: moving arms is a new enrolment (F05 "moving arms keeps history"),
    # and changing a subject is a delete plus an insert.
    with acting_as(db_session, "app_user", school_id=world.gmc), refused(db_session):
        db_session.execute(text(statement), {"arm": world.jss1b, "subject": world.igbo})


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_pupils_or_parents(
    world: World, db_session: Session, role: str, table: str
) -> None:
    # D-051: the platform sees counts through narrow functions later, never children's records.
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
