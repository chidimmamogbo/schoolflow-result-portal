"""Staff assignments (BUILD_PROMPT 9.1 item 4, second part; SPEC F06; AC06.1, AC06.2,
AT-08.3, AT-31.1, AT-31.3; D-049, D-137).

Behaviour: each school records who teaches what. One teacher per subject in
an arm, and only a subject the arm takes; one form teacher per arm, and a
teacher is form teacher of one arm at most; "Teaches all subjects" gives the
class teacher every subject of the arm, including subjects added later
(AC06.2), except a subject given to a specialist teacher; at most two class
assistants per arm (AT-31.3); a reviewer's scope is a department, or chosen
subjects and classes. Only teachers are assigned, only reviewers are scoped,
all within the same school. All data is fictional (design brief section 12).
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_arm_subject,
    add_assistant,
    add_membership,
    add_reviewer_scope,
    assign_teacher,
    create_arm,
    create_class,
    create_department,
    create_school,
    create_subject,
    create_user,
)

TABLES = ("teacher_assignments", "class_assistants", "reviewer_scopes", "teacher_subjects")
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608
SUBJECTS_OF = text(
    "select s.name from teacher_subjects ts join subjects s on s.id = ts.subject_id"
    " where ts.teacher_id = :teacher and ts.arm_id = :arm order by s.name"
)


@dataclass(frozen=True)
class Staff:
    gmc: uuid.UUID
    bsa: uuid.UUID
    jss1: uuid.UUID
    jss1a: uuid.UUID
    jss1b: uuid.UUID
    mathematics: uuid.UUID
    english: uuid.UUID
    igbo: uuid.UUID
    sciences: uuid.UUID
    tunde: uuid.UUID  # GMC teacher: Mathematics JSS 1A and 1B, form teacher of JSS 1A
    grace: uuid.UUID  # GMC teacher: English JSS 1A
    emeka: uuid.UUID  # GMC reviewer (HOD Sciences)
    primary4a: uuid.UUID
    bsa_english: uuid.UUID
    bsa_mathematics: uuid.UUID
    ifeoma: uuid.UUID  # BSA class teacher of Primary 4A, teaches all subjects
    chika: uuid.UUID  # BSA specialist: Igbo in Primary 4A
    ngozi_ani: uuid.UUID  # BSA assistant in Primary 4A
    obinna: uuid.UUID  # BSA reviewer


@pytest.fixture
def staff(db_session: Session) -> Staff:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    def member(username: str, full_name: str, school: uuid.UUID, role: str) -> uuid.UUID:
        user = create_user(s, username=username, full_name=full_name)
        add_membership(s, user, school, role)
        return user

    # GMC: JSS 1A takes Mathematics, English and Igbo; JSS 1B takes Mathematics and English.
    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a, jss1b = create_arm(s, gmc, jss1, "A"), create_arm(s, gmc, jss1, "B")
    sciences = create_department(s, gmc, "Sciences")
    mathematics = create_subject(s, gmc, "Mathematics", department_id=sciences)
    english = create_subject(s, gmc, "English Language")
    igbo = create_subject(s, gmc, "Igbo Language")
    for arm, subject in ((jss1a, mathematics), (jss1a, english), (jss1a, igbo)):
        add_arm_subject(s, gmc, arm, subject)
    for subject in (mathematics, english):
        add_arm_subject(s, gmc, jss1b, subject)

    tunde = member("tunde.adebayo", "Tunde Adebayo", gmc, "teacher")
    grace = member("grace.etim", "Grace Etim", gmc, "teacher")
    emeka = member("emeka.nwosu", "Emeka Nwosu", gmc, "reviewer")
    assign_teacher(s, gmc, tunde, jss1a, mathematics)
    assign_teacher(s, gmc, tunde, jss1b, mathematics)
    assign_teacher(s, gmc, tunde, jss1a, form_teacher=True)
    assign_teacher(s, gmc, grace, jss1a, english)
    add_reviewer_scope(s, gmc, emeka, department_id=sciences)
    bola = member("bola.ige", "Bola Ige", gmc, "teacher")
    add_assistant(s, gmc, jss1a, bola)  # helps Tunde with JSS 1A

    # BSA: Ifeoma teaches all of Primary 4A except Igbo, which Chika teaches.
    primary4 = create_class(s, bsa, "primary", "Primary 4")
    primary4a = create_arm(s, bsa, primary4, "A")
    bsa_english = create_subject(s, bsa, "English Studies")
    bsa_mathematics = create_subject(s, bsa, "Mathematics")
    bsa_science = create_subject(s, bsa, "Basic Science and Technology")
    bsa_igbo = create_subject(s, bsa, "Igbo Language")
    for subject in (bsa_english, bsa_mathematics, bsa_science, bsa_igbo):
        add_arm_subject(s, bsa, primary4a, subject)

    ifeoma = member("ifeoma.chukwu", "Ifeoma Chukwu", bsa, "teacher")
    chika = member("chika.okoye", "Chika Okoye", bsa, "teacher")
    ngozi_ani = member("ngozi.ani", "Ngozi Ani", bsa, "teacher")
    obinna = member("obinna.eze", "Obinna Eze", bsa, "reviewer")
    assign_teacher(s, bsa, ifeoma, primary4a, form_teacher=True, teaches_all_subjects=True)
    assign_teacher(s, bsa, chika, primary4a, bsa_igbo)
    add_assistant(s, bsa, primary4a, ngozi_ani)
    add_reviewer_scope(s, bsa, obinna, subject_id=bsa_mathematics, class_id=primary4)

    return Staff(
        gmc,
        bsa,
        jss1,
        jss1a,
        jss1b,
        mathematics,
        english,
        igbo,
        sciences,
        tunde,
        grace,
        emeka,
        primary4a,
        bsa_english,
        bsa_mathematics,
        ifeoma,
        chika,
        ngozi_ani,
        obinna,
    )


def new_teacher(session: Session, school_id: uuid.UUID, username: str) -> uuid.UUID:
    return new_member(session, school_id, username, "teacher")


def new_member(
    session: Session, school_id: uuid.UUID, username: str, role: str, *, principal: bool = False
) -> uuid.UUID:
    user = create_user(session, username=username, full_name="Test Person")
    add_membership(session, user, school_id, role, is_primary=principal)
    return user


# --- teacher assignments -----------------------------------------------------------


def test_a_teacher_teaches_only_subjects_the_arm_takes(staff: Staff, db_session: Session) -> None:
    # JSS 1B does not take Igbo, so nobody can be assigned to teach it there.
    with violates(db_session, "fk_teacher_assignments_arm_id_arm_subjects"):
        assign_teacher(db_session, staff.gmc, staff.grace, staff.jss1b, staff.igbo)


def test_one_teacher_per_subject_per_arm(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "ix_teacher_assignments_one_teacher_per_subject"):
        assign_teacher(db_session, staff.gmc, staff.grace, staff.jss1a, staff.mathematics)


def test_one_form_teacher_per_arm(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "ix_teacher_assignments_one_form_teacher_per_arm"):
        assign_teacher(db_session, staff.gmc, staff.grace, staff.jss1a, form_teacher=True)


def test_a_teacher_is_form_teacher_of_one_arm_at_most(staff: Staff, db_session: Session) -> None:
    # F06 rule 1: "optionally become form teacher of one arm".
    with violates(db_session, "ix_teacher_assignments_one_form_arm_per_teacher"):
        assign_teacher(db_session, staff.gmc, staff.tunde, staff.jss1b, form_teacher=True)


@pytest.mark.parametrize(
    ("with_subject", "form_teacher"),
    [(True, True), (False, False)],
)
def test_a_row_is_either_a_subject_or_the_form_teacher(
    staff: Staff, db_session: Session, with_subject: bool, form_teacher: bool
) -> None:
    subject = staff.mathematics if with_subject else None
    with violates(db_session, "ck_teacher_assignments_subject_or_form_teacher"):
        assign_teacher(
            db_session, staff.gmc, staff.grace, staff.jss1b, subject, form_teacher=form_teacher
        )


def test_teaches_all_subjects_belongs_to_the_form_teacher(
    staff: Staff, db_session: Session
) -> None:
    with violates(db_session, "ck_teacher_assignments_teaches_all_needs_form_teacher"):
        assign_teacher(
            db_session,
            staff.gmc,
            staff.grace,
            staff.jss1b,
            staff.english,
            teaches_all_subjects=True,
        )


def test_staff_who_also_teach_can_be_assigned(staff: Staff, db_session: Session) -> None:
    # D-144 and AT-14.3: a principal or an HOD who also teaches gets teacher assignments.
    ngozi = new_member(db_session, staff.gmc, "ngozi.okeke", "school_admin", principal=True)

    assign_teacher(db_session, staff.gmc, ngozi, staff.jss1b, staff.english)
    assign_teacher(db_session, staff.gmc, staff.emeka, staff.jss1b, form_teacher=True)


def test_only_staff_are_assigned(staff: Staff, db_session: Session) -> None:
    # Denied: a parent's or pupil's login never gets teaching assignments.
    funke = new_member(db_session, staff.gmc, "funke.adeyemi", "parent")

    with violates(db_session, "teacher_assignments_teacher_id_is_staff"):
        assign_teacher(db_session, staff.gmc, funke, staff.jss1b, staff.english)


def test_an_assignment_stays_in_its_school(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "fk_teacher_assignments_arm_id_class_arms"):
        assign_teacher(db_session, staff.gmc, staff.grace, staff.primary4a, staff.bsa_english)


# --- what each teacher teaches (D-049: worked out when asked) -------------------------


def test_explicit_assignments_show_in_teacher_subjects(staff: Staff, db_session: Session) -> None:
    arms = set(
        db_session.scalars(
            text(
                "select arm_id from teacher_subjects where teacher_id = :teacher"
                " and subject_id = :subject"
            ),
            {"teacher": staff.tunde, "subject": staff.mathematics},
        )
    )

    assert arms == {staff.jss1a, staff.jss1b}


def test_teaches_all_subjects_covers_every_subject_of_the_arm(
    staff: Staff, db_session: Session
) -> None:
    before = list(
        db_session.scalars(SUBJECTS_OF, {"teacher": staff.ifeoma, "arm": staff.primary4a})
    )

    # AC06.2 and AT-31.1: a subject added later is hers straight away.
    computer = create_subject(db_session, staff.bsa, "Computer Studies")
    add_arm_subject(db_session, staff.bsa, staff.primary4a, computer)
    after = list(db_session.scalars(SUBJECTS_OF, {"teacher": staff.ifeoma, "arm": staff.primary4a}))

    assert before == ["Basic Science and Technology", "English Studies", "Mathematics"]
    assert after == [
        "Basic Science and Technology",
        "Computer Studies",
        "English Studies",
        "Mathematics",
    ]


def test_a_specialist_keeps_their_subject(staff: Staff, db_session: Session) -> None:
    # Igbo in Primary 4A belongs to Chika, not to the class teacher.
    teachers = list(
        db_session.scalars(
            text(
                "select u.username from teacher_subjects ts join users u on u.id = ts.teacher_id"
                " join subjects s on s.id = ts.subject_id"
                " where ts.arm_id = :arm and s.name = 'Igbo Language'"
            ),
            {"arm": staff.primary4a},
        )
    )

    assert teachers == ["chika.okoye"]


# --- class teacher assistants ------------------------------------------------------


def test_at_most_two_assistants_per_arm(staff: Staff, db_session: Session) -> None:
    # AT-31.3 and SPEC section 12: up to 2 per arm.
    add_assistant(
        db_session, staff.bsa, staff.primary4a, new_teacher(db_session, staff.bsa, "bisi.adeleke")
    )
    third = new_teacher(db_session, staff.bsa, "kemi.ajayi")

    with violates(db_session, "class_assistants_at_most_two"):
        add_assistant(db_session, staff.bsa, staff.primary4a, third)


def test_an_assistant_is_added_once_per_arm(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "uq_class_assistants_arm_id_assistant_id"):
        add_assistant(db_session, staff.bsa, staff.primary4a, staff.ngozi_ani)


def test_staff_who_also_teach_can_be_assistants(staff: Staff, db_session: Session) -> None:
    # D-144: BSA's reviewer helps in Primary 4A as its second assistant.
    add_assistant(db_session, staff.bsa, staff.primary4a, staff.obinna)


def test_only_staff_are_assistants(staff: Staff, db_session: Session) -> None:
    ada = new_member(db_session, staff.bsa, "ada.eze", "parent")

    with violates(db_session, "class_assistants_assistant_id_is_staff"):
        add_assistant(db_session, staff.bsa, staff.primary4a, ada)


# --- reviewer scopes -----------------------------------------------------------------


@pytest.mark.parametrize("kind", ["both", "neither"])
def test_a_scope_is_a_department_or_subjects_and_classes(
    staff: Staff, db_session: Session, kind: str
) -> None:
    department = staff.sciences
    subject = staff.mathematics if kind == "both" else None
    with violates(db_session, "ck_reviewer_scopes_department_or_subjects"):
        add_reviewer_scope(
            db_session,
            staff.gmc,
            staff.emeka,
            department_id=department if kind == "both" else None,
            subject_id=subject,
        )


def test_a_reviewer_can_have_a_subject_and_class_scope(staff: Staff, db_session: Session) -> None:
    # AT-08.3 alternative: Mathematics in JSS 1 only.
    add_reviewer_scope(
        db_session, staff.gmc, staff.emeka, subject_id=staff.mathematics, class_id=staff.jss1
    )


def test_a_reviewer_gets_each_scope_once(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "ix_reviewer_scopes_unique_scope"):
        add_reviewer_scope(db_session, staff.gmc, staff.emeka, department_id=staff.sciences)


def test_only_reviewers_get_a_scope(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "reviewer_scopes_reviewer_id_is_reviewer"):
        add_reviewer_scope(db_session, staff.gmc, staff.tunde, department_id=staff.sciences)


def test_a_scope_stays_in_its_school(staff: Staff, db_session: Session) -> None:
    with violates(db_session, "fk_reviewer_scopes_subject_id_subjects"):
        add_reviewer_scope(db_session, staff.gmc, staff.emeka, subject_id=staff.bsa_mathematics)


# --- row-level security ------------------------------------------------------------


@pytest.mark.parametrize("table", TABLES)
def test_a_school_sees_only_its_own_staff_assignments(
    staff: Staff, db_session: Session, table: str
) -> None:
    with acting_as(db_session, "app_user", school_id=staff.gmc):
        gmc = db_session.scalar(COUNT[table])
    with acting_as(db_session, "app_user", school_id=staff.bsa):
        bsa = db_session.scalar(COUNT[table])
    total = db_session.scalar(COUNT[table])

    assert gmc >= 1
    assert bsa >= 1
    assert gmc + bsa == total


def test_a_school_manages_its_own_assignments(staff: Staff, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=staff.gmc):
        assignment = assign_teacher(db_session, staff.gmc, staff.grace, staff.jss1b, staff.english)
        removed = list(
            db_session.scalars(
                text("delete from teacher_assignments where id = :id returning id"),
                {"id": assignment},
            )
        )

    assert removed == [assignment]


def test_a_school_cannot_assign_another_schools_teacher(staff: Staff, db_session: Session) -> None:
    # Denied: GMC cannot see BSA's staff at all, so to GMC Ifeoma is not staff.
    with (
        acting_as(db_session, "app_user", school_id=staff.gmc),
        violates(db_session, "teacher_assignments_teacher_id_is_staff"),
    ):
        assign_teacher(db_session, staff.bsa, staff.ifeoma, staff.primary4a, staff.bsa_english)


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_assignments(
    staff: Staff, db_session: Session, role: str, table: str
) -> None:
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
