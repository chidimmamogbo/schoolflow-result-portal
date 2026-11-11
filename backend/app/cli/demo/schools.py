"""Each demo school's set-up and staff, made by its own principal (D-180).

ACCEPTANCE_TESTS fixtures: GMC's Sciences department, Tunde Adebayo
(Mathematics JSS 1A and 1B, form teacher JSS 1A), Emeka Nwosu reviewing
Sciences and vice principal Chukwudi Eze; BSA's Primary 4A class teacher
Ifeoma Chukwu (teaches all subjects) with assistant Ngozi Ani, and Nursery 2
class teacher Amaka Udeh. Everyone else is invented so each demo class has a
teacher for every subject. Staff get a temporary password on a login slip
(no email), then sign in once and change it to the demo password.
"""

from typing import Any

from app.cli.demo.browser import Browser, Demo

SESSION = {"name": "2026/2027", "starts_on": "2026-09-07", "ends_on": "2027-07-23"}
TERMS = [
    {"term_number": 1, "starts_on": "2026-09-07", "ends_on": "2026-12-11",
     "next_term_begins": "2027-01-05"},
    {"term_number": 2, "starts_on": "2027-01-05", "ends_on": "2027-04-02",
     "next_term_begins": "2027-04-26"},
    {"term_number": 3, "starts_on": "2027-04-26", "ends_on": "2027-07-23"},
]  # fmt: skip

JSS = [
    "Mathematics", "English Language", "Basic Science", "Basic Technology",
    "Agricultural Science", "Computer Studies", "Social Studies", "Civic Education",
]  # fmt: skip
SSS = ["Mathematics", "English Language", "Physics", "Chemistry", "Biology", "Economics"]
PRIMARY = ["Mathematics", "English Language", "Basic Science", "Social Studies"]

JUNIOR_COLUMNS = [
    {"name": "Continuous assessment 1", "label": "CA1", "max_score": 20},
    {"name": "Continuous assessment 2", "label": "CA2", "max_score": 20},
    {"name": "Examination", "label": "Exam", "max_score": 60},
]
SENIOR_COLUMNS = [
    {"name": "Continuous assessment 1", "label": "CA1", "max_score": 10},
    {"name": "Continuous assessment 2", "label": "CA2", "max_score": 10},
    {"name": "Continuous assessment 3", "label": "CA3", "max_score": 10},
    {"name": "Project", "label": "Project", "max_score": 10},
    {"name": "Examination", "label": "Exam", "max_score": 60},
]

# Areas with sample skills to rate (Pre-science and Handwriting start empty, D-145).
NURSERY_AREAS = [
    "Number work", "Letter work", "Phonics", "Rhymes and songs", "Creative arts",
    "Social habits",
]  # fmt: skip

# An assignment: (username, arm, subject or None for the form class, teaches all subjects).
Assignment = tuple[str, str, str | None, bool]

SETUP: dict[str, dict[str, Any]] = {
    "GMC": {
        "principal": "ngozi.okeke",
        "departments": {
            "Sciences": [
                "Mathematics",
                "Basic Science",
                "Basic Technology",
                "Agricultural Science",
                "Computer Studies",
                "Physics",
                "Chemistry",
                "Biology",
            ],
            "Languages": ["English Language"],
            "Social Sciences": ["Social Studies", "Civic Education", "Economics"],
        },
        "subjects": [],
        "classes": [
            ("junior_secondary", "JSS 1", ["A", "B"], JSS),
            ("junior_secondary", "JSS 3", ["A"], ["Mathematics", "English Language"]),
            ("senior_secondary", "SS 1", ["A"], SSS),
        ],
        "structures": {"junior_secondary": JUNIOR_COLUMNS, "senior_secondary": SENIOR_COLUMNS},
        "admins": [("Chukwudi Eze", "chukwudi.eze")],
        "staff": [
            ("Emeka Nwosu", "emeka.nwosu", "reviewer"),
            ("Tunde Adebayo", "tunde.adebayo", "teacher"),
            ("Amina Bello", "amina.bello", "teacher"),
            ("Grace Etim", "grace.etim", "teacher"),
            ("Bola Ige", "bola.ige", "teacher"),
            ("Kunle Balogun", "kunle.balogun", "teacher"),
            ("Hauwa Musa", "hauwa.musa", "teacher"),
        ],
        "reviewers": [("emeka.nwosu", "Sciences")],
        "assignments": [
            *[
                ("tunde.adebayo", arm, "Mathematics", False)
                for arm in ("JSS 1A", "JSS 1B", "JSS 3A", "SS 1A")
            ],
            *[
                ("amina.bello", arm, "English Language", False)
                for arm in ("JSS 1A", "JSS 1B", "JSS 3A", "SS 1A")
            ],
            *[
                ("grace.etim", arm, s, False)
                for arm in ("JSS 1A", "JSS 1B")
                for s in ("Basic Science", "Basic Technology")
            ],
            *[
                ("bola.ige", arm, s, False)
                for arm in ("JSS 1A", "JSS 1B")
                for s in ("Agricultural Science", "Computer Studies")
            ],
            *[
                ("kunle.balogun", arm, s, False)
                for arm in ("JSS 1A", "JSS 1B")
                for s in ("Social Studies", "Civic Education")
            ],
            ("kunle.balogun", "SS 1A", "Economics", False),
            *[("hauwa.musa", "SS 1A", s, False) for s in ("Physics", "Chemistry", "Biology")],
            ("tunde.adebayo", "JSS 1A", None, False),
            ("kunle.balogun", "JSS 1B", None, False),
            ("amina.bello", "JSS 3A", None, False),
            ("hauwa.musa", "SS 1A", None, False),
        ],
        "assistants": [],
        "nursery_areas": {},
    },
    "BSA": {
        "principal": "chiamaka.nwafor",
        "departments": {},
        "subjects": PRIMARY,
        "classes": [
            ("nursery", "Nursery 2", [""], []),
            ("primary", "Primary 4", ["A"], PRIMARY),
        ],
        "structures": {"primary": JUNIOR_COLUMNS},
        "admins": [],
        "staff": [
            ("Ifeoma Chukwu", "ifeoma.chukwu", "teacher"),
            ("Ngozi Ani", "ngozi.ani", "teacher"),
            ("Amaka Udeh", "amaka.udeh", "teacher"),
        ],
        "reviewers": [],
        "assignments": [
            ("ifeoma.chukwu", "Primary 4A", None, True),
            ("amaka.udeh", "Nursery 2", None, True),
        ],
        "assistants": [("ngozi.ani", "Primary 4A")],
        "nursery_areas": {"Nursery 2": NURSERY_AREAS},
    },
    "RCS": {
        "principal": "femi.adeyemi",
        "departments": {},
        "subjects": ["Mathematics", "English Language"],
        "classes": [
            ("nursery", "Nursery 1", [""], []),
            ("primary", "Primary 1", ["A"], ["Mathematics", "English Language"]),
            ("junior_secondary", "JSS 1", ["A"], ["Mathematics", "English Language"]),
        ],
        "structures": {"primary": JUNIOR_COLUMNS, "junior_secondary": JUNIOR_COLUMNS},
        "admins": [],
        "staff": [
            ("Kemi Adebanjo", "kemi.adebanjo", "teacher"),
            ("Tobi Ojo", "tobi.ojo", "teacher"),
            ("Segun Olawale", "segun.olawale", "teacher"),
        ],
        "reviewers": [],
        "assignments": [
            ("kemi.adebanjo", "Nursery 1", None, True),
            ("tobi.ojo", "Primary 1A", None, True),
            ("segun.olawale", "JSS 1A", "Mathematics", False),
            ("segun.olawale", "JSS 1A", "English Language", False),
            ("segun.olawale", "JSS 1A", None, False),
        ],
        "assistants": [],
        "nursery_areas": {"Nursery 1": NURSERY_AREAS},
    },
}


def key(code: str, name: str) -> str:
    """The seed's own name for a school's record, such as "GMC:JSS 1A"."""
    return f"{code}:{name}"


def make_calendar(demo: Demo, code: str, head: Browser) -> None:
    year = head.post("/school/sessions", SESSION)
    demo.ids[key(code, "session")] = year["id"]
    for term in TERMS:
        made = head.post(f"/school/sessions/{year['id']}/terms", term)
        demo.ids[key(code, f"term {term['term_number']}")] = made["id"]
    head.post(f"/school/terms/{demo.ids[key(code, 'term 1')]}/activate")


def make_subjects(demo: Demo, code: str, head: Browser, setup: dict[str, Any]) -> None:
    for department, subjects in setup["departments"].items():
        made = head.post("/school/departments", {"name": department})
        demo.ids[key(code, department)] = made["id"]
        for subject in subjects:
            row = head.post("/school/subjects", {"name": subject, "department_id": made["id"]})
            demo.ids[key(code, subject)] = row["id"]
    for subject in setup["subjects"]:
        demo.ids[key(code, subject)] = head.post("/school/subjects", {"name": subject})["id"]


def make_classes(demo: Demo, code: str, head: Browser, setup: dict[str, Any]) -> None:
    for level, name, arms, subjects in setup["classes"]:
        made = head.post("/school/classes", {"level": level, "name": name})
        demo.ids[key(code, f"class {name}")] = made["id"]
        for arm in arms:
            row = head.post(f"/school/classes/{made['id']}/arms", {"name": arm})
            demo.ids[key(code, f"{name}{arm}")] = row["id"]
            if subjects:
                ids = [demo.ids[key(code, s)] for s in subjects]
                head.put(f"/school/arms/{row['id']}/subjects", {"subject_ids": ids})
    for level, columns in setup["structures"].items():
        head.put(f"/school/assessment-structures/{level}", {"components": columns})
    for class_name, wanted in setup["nursery_areas"].items():
        areas = {a["name"]: a["id"] for a in head.get("/school/learning-areas?level=nursery")}
        ids = [areas[name] for name in wanted]
        head.put(f"/school/classes/{demo.ids[key(code, f"class {class_name}")]}/learning-areas",
                 {"learning_area_ids": ids})  # fmt: skip


def make_staff(demo: Demo, code: str, head: Browser, setup: dict[str, Any]) -> None:
    """Login slips, not emails: each person signs in once and picks the demo password."""
    for full_name, username in setup["admins"]:
        made = head.post(
            "/school/admins",
            {"full_name": full_name, "username": username, "login_method": "temporary_password"},
        )
        demo.ids[username] = made["id"]
        demo.take_over(username, made["temporary_password"])
    for full_name, username, role in setup["staff"]:
        made = head.post(
            "/school/staff",
            {
                "full_name": full_name,
                "username": username,
                "role": role,
                "login_method": "temporary_password",
            },
        )
        demo.ids[username] = made["id"]
        demo.take_over(username, made["temporary_password"])


def assign_staff(demo: Demo, code: str, head: Browser, setup: dict[str, Any]) -> None:
    assignments: list[Assignment] = setup["assignments"]
    for username, arm, subject, teaches_all in assignments:
        body: dict[str, Any] = {
            "teacher_id": demo.ids[username],
            "arm_id": demo.ids[key(code, arm)],
        }
        if subject is None:
            body |= {"is_form_teacher": True, "teaches_all_subjects": teaches_all}
        else:
            body["subject_id"] = demo.ids[key(code, subject)]
        head.post("/school/assignments", body)
    for username, arm in setup["assistants"]:
        head.post(f"/school/arms/{demo.ids[key(code, arm)]}/assistants",
                  {"user_id": demo.ids[username]})  # fmt: skip
    for username, department in setup["reviewers"]:
        head.post(f"/school/reviewers/{demo.ids[username]}/scopes",
                  {"department_id": demo.ids[key(code, department)]})  # fmt: skip


def seed_schools(demo: Demo) -> None:
    for code, setup in SETUP.items():
        head = demo.as_(setup["principal"])
        make_calendar(demo, code, head)
        make_subjects(demo, code, head, setup)
        make_classes(demo, code, head, setup)
        make_staff(demo, code, head, setup)
        assign_staff(demo, code, head, setup)
