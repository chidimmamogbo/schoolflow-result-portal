"""Results week for the demo: scores, ratings, form class entries, publishing (D-180).

Teachers enter and submit, the Sciences reviewer reviews, the principal
approves; form teachers write comments, attendance and traits; the principal
writes their comments and publishes. JSS 1A (GMC), Primary 4A and Nursery 2
(BSA) are published, so Students needing attention shows the brief's examples
(design brief section 12): Musa Ibrahim's Mathematics 38, Halima Garba's Basic
Science 35 and Mathematics 39, Daniel Okon's average 38.5 with six failed
subjects, and Hauwa Sani's "Counts 1 to 20" rated Needs improvement. JSS 1B
is left mid-week for the dashboard. Every other total is a pass.
"""

from typing import Any

from app.cli.demo.browser import Browser, Demo, SeedError
from app.cli.demo.schools import SETUP, key

# Subject totals the brief fixes (out of 100).
TOTALS: dict[tuple[str, str], int] = {
    ("Chukwuemeka Obi", "Mathematics"): 78,
    ("Musa Ibrahim", "Mathematics"): 38,
    ("Halima Garba", "Basic Science"): 35,
    ("Halima Garba", "Mathematics"): 39,
    ("Halima Garba", "English Language"): 49,
    ("Halima Garba", "Basic Technology"): 49,
    ("Halima Garba", "Agricultural Science"): 49,
    ("Halima Garba", "Computer Studies"): 49,
    ("Halima Garba", "Social Studies"): 50,
    ("Halima Garba", "Civic Education"): 50,
    # Six below 40 and an average of 38.5 over eight subjects.
    ("Daniel Okon", "Mathematics"): 30,
    ("Daniel Okon", "English Language"): 30,
    ("Daniel Okon", "Basic Science"): 30,
    ("Daniel Okon", "Basic Technology"): 30,
    ("Daniel Okon", "Agricultural Science"): 30,
    ("Daniel Okon", "Computer Studies"): 30,
    ("Daniel Okon", "Social Studies"): 64,
    ("Daniel Okon", "Civic Education"): 64,
}
# The brief's own row: CA1 16, CA2 15, Exam 47.
EXACT: dict[tuple[str, str], list[int]] = {("Chukwuemeka Obi", "Mathematics"): [16, 15, 47]}

# Ratings the brief fixes; everyone else is rated Good (G).
RATINGS: dict[tuple[str, str], str] = {
    ("Chidera Okeke", "Counts 1 to 20"): "VG",
    ("Chidera Okeke", "Recognises shapes"): "E",
    ("Hauwa Sani", "Counts 1 to 20"): "NI",
}

COMMENTS = {
    "Chukwuemeka Obi": "A focused and respectful student. Keep it up in Mathematics.",
    "Chidera Okeke": "Chidera is cheerful and eager to learn. She counts confidently and"
    " enjoys rhymes.",
}
TRAITS = {"Punctuality": 5, "Neatness": 4, "Politeness": 5, "Handwriting": 4, "Sports": 3}
OPENED = 60


def total_for(name: str, subject: str) -> int:
    """The brief's total, or a steady pass between 52 and 88 for everyone else."""
    if (name, subject) in TOTALS:
        return TOTALS[(name, subject)]
    return 52 + sum((i + 1) * ord(c) for i, c in enumerate(name + subject)) % 37


def split(total: int, columns: list[int]) -> list[int]:
    """A total shared out in proportion to each column's maximum, within every maximum."""
    parts = [min(top, total * top // 100) for top in columns]
    rest = total - sum(parts)
    for i in sorted(range(len(columns)), key=lambda i: -columns[i]):
        give = min(rest, columns[i] - parts[i])
        parts[i] += give
        rest -= give
    return parts


def teacher_of(code: str, arm: str, subject: str) -> str:
    """Who enters a subject: its own teacher, else the class teacher who teaches all."""
    for username, where, what, teaches_all in SETUP[code]["assignments"]:
        if where == arm and (what == subject or (what is None and teaches_all)):
            return str(username)
    raise SeedError(f"Nobody teaches {subject} in {code} {arm}.")


def form_teacher_of(code: str, arm: str) -> str:
    for username, where, what, _ in SETUP[code]["assignments"]:
        if where == arm and what is None:
            return str(username)
    raise SeedError(f"{code} {arm} has no form teacher.")


def reviewed_subjects(code: str) -> dict[str, str]:
    """Subject to reviewer: a sheet a reviewer covers is reviewed before approval (D-142)."""
    covers: dict[str, str] = {}
    for reviewer, department in SETUP[code]["reviewers"]:
        for subject in SETUP[code]["departments"][department]:
            covers[subject] = reviewer
    return covers


def enter_scores(demo: Demo, code: str, arm: str, subject: str, *, only_first: bool = False) -> str:
    teacher = demo.as_(teacher_of(code, arm, subject))
    body = {"arm_id": demo.ids[key(code, arm)], "subject_id": demo.ids[key(code, subject)]}
    sheet = teacher.post("/sheets", body)
    columns = sheet["columns"]
    cells: list[dict[str, Any]] = []
    for row in sheet["rows"][: 1 if only_first else None]:
        name = f"{row['first_name']} {row['surname']}"
        values = EXACT.get((name, subject)) or split(
            total_for(name, subject), [c["max_score"] for c in columns]
        )
        cells += [
            {"enrolment_id": row["enrolment_id"], "component_id": c["id"], "value": v}
            for c, v in zip(columns, values, strict=True)
        ]
    teacher.put(f"/sheets/{sheet['id']}/scores", {"scores": cells})
    return str(sheet["id"])


def submit_and_approve(demo: Demo, code: str, arm: str, subject: str, sheet: str) -> None:
    demo.as_(teacher_of(code, arm, subject)).post(f"/sheets/{sheet}/submit")
    reviewer = reviewed_subjects(code).get(subject)
    if reviewer is not None:
        demo.as_(reviewer).post(f"/sheets/{sheet}/review")
    demo.as_(SETUP[code]["principal"]).post(f"/sheets/{sheet}/approve")


def rate_area(demo: Demo, code: str, arm: str, area_id: str, teacher: Browser) -> str:
    sheet = teacher.post("/rating-sheets", {"arm_id": demo.ids[key(code, arm)],
                                            "learning_area_id": area_id})  # fmt: skip
    points = {p["code"]: p["id"] for p in sheet["scale"]}
    ratings = [
        {
            "enrolment_id": row["enrolment_id"],
            "skill_id": skill["id"],
            "point_id": points[
                RATINGS.get((f"{row['first_name']} {row['surname']}", skill["name"]), "G")
            ],
        }
        for row in sheet["rows"]
        for skill in sheet["skills"]
    ]
    teacher.put(f"/rating-sheets/{sheet['id']}/ratings", {"ratings": ratings})
    return str(sheet["id"])


def form_class_entries(demo: Demo, code: str, arm: str) -> list[str]:
    """Comments, attendance and traits for every pupil, then the section is submitted."""
    teacher = demo.as_(form_teacher_of(code, arm))
    arm_id = demo.ids[key(code, arm)]
    teacher.put(f"/form-class/{arm_id}/attendance-days", {"times_school_opened": OPENED})
    view = teacher.get(f"/form-class/{arm_id}")
    traits = {t["name"]: t["id"] for t in view["traits"]}
    enrolments: list[str] = []
    for i, pupil in enumerate(view["pupils"]):
        name = f"{pupil['first_name']} {pupil['surname']}"
        entry: dict[str, Any] = {
            "comment": COMMENTS.get(name, f"{pupil['first_name']} worked steadily this term."),
            "times_present": 57 if name == "Chukwuemeka Obi" else OPENED - i % 4,
        }
        if traits:
            entry["ratings"] = {tid: TRAITS.get(trait, 4) for trait, tid in traits.items()}
        teacher.put(f"/form-class/{arm_id}/students/{pupil['enrolment_id']}/entry", entry)
        enrolments.append(str(pupil["enrolment_id"]))
    teacher.post(f"/form-class/{arm_id}/sections/submit")
    return enrolments


def publish(demo: Demo, code: str, arm: str, enrolments: list[str]) -> None:
    head = demo.as_(SETUP[code]["principal"])
    arm_id = demo.ids[key(code, arm)]
    comments = [{"enrolment_id": e, "comment": "A good term. Keep working hard."}
                for e in enrolments]  # fmt: skip
    head.put(f"/school/publications/{arm_id}/principal-comments", {"comments": comments})
    ready = head.get(f"/school/publications/{arm_id}")
    if not ready["ready"]:
        raise SeedError(f"{code} {arm} is not ready to publish: {'; '.join(ready['problems'])}")
    head.post(f"/school/publications/{arm_id}/publish")


def publish_scores_class(demo: Demo, code: str, arm: str) -> None:
    subjects = next(s for _, name, arms, s in SETUP[code]["classes"]
                    for a in arms if f"{name}{a}" == arm)  # fmt: skip
    for subject in subjects:
        sheet = enter_scores(demo, code, arm, subject)
        submit_and_approve(demo, code, arm, subject, sheet)
    publish(demo, code, arm, form_class_entries(demo, code, arm))


def publish_ratings_class(demo: Demo, code: str, arm: str) -> None:
    teacher = demo.as_(form_teacher_of(code, arm))
    head = demo.as_(SETUP[code]["principal"])
    areas = {a["name"]: a["id"] for a in head.get("/school/learning-areas?level=nursery")}
    for name in SETUP[code]["nursery_areas"][arm]:
        sheet = rate_area(demo, code, arm, areas[name], teacher)
        teacher.post(f"/sheets/{sheet}/submit")
        head.post(f"/sheets/{sheet}/approve")
    publish(demo, code, arm, form_class_entries(demo, code, arm))


def mid_week(demo: Demo) -> None:
    """JSS 1B: Mathematics waits for review; English has only one pupil's scores."""
    maths = enter_scores(demo, "GMC", "JSS 1B", "Mathematics")
    demo.as_(teacher_of("GMC", "JSS 1B", "Mathematics")).post(f"/sheets/{maths}/submit")
    enter_scores(demo, "GMC", "JSS 1B", "English Language", only_first=True)


def save_templates(demo: Demo) -> None:
    """Two report templates, each saved from the level's defaults in a chosen style."""
    for code, level, style in (
        ("GMC", "junior_secondary", "classic"),
        ("BSA", "primary", "modern"),
    ):
        head = demo.as_(SETUP[code]["principal"])
        current = next(t for t in head.get("/school/report-templates") if t["level"] == level)
        head.put(f"/school/report-templates/{level}",
                 {"style": style, "settings": current["settings"]})  # fmt: skip


NOTICES = [
    ("GMC", {
        "title": "Inter-house sports holds on Friday, 14 November",
        "body": "Parents and guardians are welcome from 9am at the school field.",
        "pinned": True,
        "audience": {"everyone": True},
    }),
    ("BSA", {
        "title": "Parents' evening for Primary 4",
        "body": "Class teachers will meet parents on Thursday, 20 November, from 4pm.",
        "audience": {"roles": ["parent"]},
    }),
]  # fmt: skip


def post_notices(demo: Demo) -> None:
    for code, notice in NOTICES:
        demo.as_(SETUP[code]["principal"]).post("/school/notices", notice)


def seed_results(demo: Demo) -> None:
    save_templates(demo)
    publish_scores_class(demo, "GMC", "JSS 1A")
    publish_scores_class(demo, "BSA", "Primary 4A")
    publish_ratings_class(demo, "BSA", "Nursery 2")
    mid_week(demo)
    post_notices(demo)
    # The result emails go into the mailbox here, never to Resend.
    demo.read_mail()
