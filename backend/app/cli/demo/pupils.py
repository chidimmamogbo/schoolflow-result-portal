"""Pupils, pupil logins and parents for the demo (D-180).

Design brief section 12 names the first pupils of JSS 1A, Nursery 2 and
Primary 4A; the rest are invented from the name lists below, so every demo
class has 20 to 30 pupils. Chukwuemeka Obi is GMC/2026/014, and BSA's Kamsi
Okafor is 2026/014 too, to show two schools never mix (AC02.6).

Parents: Ikenna Obi has an email, so GMC adds him by a link request; he joins
from the link in that email (the app's own sender runs into a mailbox here,
nothing is sent) and later accepts BSA's request, so one account has wards in
both schools (D-138). The other parents have no email and get login slips.
"""

import re
from dataclasses import dataclass

from app.cli.demo.browser import Browser, Demo, SeedError
from app.cli.demo.schools import SETUP, key


@dataclass(frozen=True)
class Pupil:
    first_name: str
    surname: str
    gender: str
    admission_number: str


# (first name, surname, gender, admission number if the brief fixes one)
Named = tuple[str, str, str, str | None]

NAMED: dict[tuple[str, str], list[Named]] = {
    ("GMC", "JSS 1A"): [
        ("Chukwuemeka", "Obi", "male", "GMC/2026/014"),
        ("Amina", "Bello", "female", None),
        ("Tobi", "Adeyemi", "male", None),
        ("Ifeoma", "Nwankwo", "female", None),
        ("Musa", "Ibrahim", "male", None),
        ("Zainab", "Yusuf", "female", None),
        ("Chinedu", "Okafor", "male", None),
        ("Blessing", "Eze", "female", None),
        ("Daniel", "Okon", "male", None),
        ("Halima", "Garba", "female", None),
        ("Kelechi", "Uche", "male", None),
        ("Funmilayo", "Ajayi", "female", None),
    ],
    ("GMC", "JSS 3A"): [("Adaeze", "Obi", "female", None)],
    ("BSA", "Nursery 2"): [
        ("Chidera", "Okeke", "female", None),
        ("Tolu", "Bamidele", "female", None),
        ("Ebube", "Eze", "male", None),
        ("Hauwa", "Sani", "female", None),
        ("Somto", "Nnaji", "male", None),
        ("Ada", "Onuoha", "female", None),
    ],
    ("BSA", "Primary 4A"): [
        ("Kamsi", "Okafor", "male", "2026/014"),
        ("Bisi", "Adeleke", "female", None),
        ("Uche", "Mba", "male", None),
        ("Fatima", "Lawal", "female", None),
        ("David", "Ezeh", "male", None),
        ("Joy", "Akpan", "female", None),
        ("Kosi", "Obi", "female", None),
    ],
}

# How many pupils each demo class has in a full seed.
SIZES: dict[tuple[str, str], int] = {
    ("GMC", "JSS 1A"): 25,
    ("GMC", "JSS 1B"): 20,
    ("GMC", "JSS 3A"): 20,
    ("GMC", "SS 1A"): 20,
    ("BSA", "Nursery 2"): 20,
    ("BSA", "Primary 4A"): 20,
    ("RCS", "Nursery 1"): 20,
    ("RCS", "Primary 1A"): 20,
    ("RCS", "JSS 1A"): 20,
}
CLASSES = list(SIZES)

# Without the full seed, a class with no named pupils still gets a few.
FEW = 3

GIRLS = [
    "Adaeze", "Chiamaka", "Nneka", "Ebere", "Folake", "Yetunde", "Amarachi", "Chioma",
    "Rukayat", "Uju", "Kemi", "Ngozi", "Ifunanya", "Temitope", "Aisha", "Onyinye",
]  # fmt: skip
BOYS = [
    "Obinna", "Ifeanyi", "Nnamdi", "Chidi", "Bayo", "Segun", "Yusuf", "Femi", "Sani",
    "Dayo", "Emeka", "Ikechukwu", "Tochukwu", "Babatunde", "Abdullahi", "Ugochukwu",
]  # fmt: skip
# Steps through the pairs; 97 is prime and does not divide 768 (32 first names x 24 surnames).
STRIDE = 97

SURNAMES = [
    "Okoro", "Danjuma", "Etuk", "Ogunleye", "Ilori", "Udo", "Chukwu", "Nwachukwu",
    "Abubakar", "Olatunji", "Eze", "Okafor", "Agu", "Bassey", "Oyelaran", "Umeh",
    "Ekwueme", "Adebayo", "Musa", "Onyeka", "Ndukwe", "Ibe", "Salami", "Ojo",
]  # fmt: skip


def invented(code: str, arm: str, count: int, taken: set[tuple[str, str]]) -> list[Named]:
    """The same invented names on every run, in a different order for each class.

    It walks every first name and surname pair once (a stride that shares no
    factor with the number of pairs), so it always ends.
    """
    pairs = [(first, surname, "female") for first in GIRLS for surname in SURNAMES] + [
        (first, surname, "male") for first in BOYS for surname in SURNAMES
    ]
    start = sum(ord(c) for c in code + arm)
    made: list[Named] = []
    for step in range(len(pairs)):
        if len(made) == count:
            break
        first, surname, gender = pairs[(start + step * STRIDE) % len(pairs)]
        if (first, surname) in taken:
            continue
        taken.add((first, surname))
        made.append((first, surname, gender, None))
    if len(made) < count:
        raise SeedError(f"Not enough invented names for {code} {arm}.")
    return made


def numbered(code: str, named: list[Named], used: set[str]) -> list[Pupil]:
    pupils: list[Pupil] = []
    for first, surname, gender, number in named:
        if number is None:
            n = 1
            while f"{code}/2026/{n:03d}" in used:
                n += 1
            number = f"{code}/2026/{n:03d}"
        used.add(number)
        pupils.append(Pupil(first, surname, gender, number))
    return pupils


def school_pupils(code: str, *, full: bool) -> dict[str, list[Pupil]]:
    """Every demo class of one school, numbered so admission numbers never repeat."""
    arms = [arm for c, arm in CLASSES if c == code]
    lists: dict[str, list[Named]] = {}
    taken: set[tuple[str, str]] = set()
    for arm in arms:
        named = NAMED.get((code, arm), [])
        taken |= {(first, surname) for first, surname, _, _ in named}
        lists[arm] = list(named)
    for arm in arms:
        target = SIZES[(code, arm)] if full else (0 if lists[arm] else FEW)
        lists[arm] += invented(code, arm, max(0, target - len(lists[arm])), taken)
    used = {n for named in lists.values() for *_, n in named if n is not None}
    return {arm: numbered(code, named, used) for arm, named in lists.items()}


def pupils_for(code: str, arm: str, *, full: bool) -> list[Pupil]:
    return school_pupils(code, full=full)[arm]


# Pupils who get a login: (school, admission number, username).
PUPIL_LOGINS = [("GMC", "GMC/2026/014", "chukwuemeka.obi"), ("BSA", "2026/014", "kamsi.okafor")]

IKENNA_EMAIL = "ikenna.obi@home.example"
IKENNA = "ikenna.obi"

# Parents without an email: (school, full name, username, [(ward, relationship)]).
SLIP_PARENTS = [
    ("GMC", "Aisha Ibrahim", "aisha.ibrahim", [("Musa Ibrahim", "Mother")]),
    ("BSA", "Ada Okeke", "ada.okeke", [("Chidera Okeke", "Mother")]),
    ("RCS", "Peter Udo", "peter.udo", [("first pupil of Primary 1A", "Father")]),
]

JOIN_LINK = re.compile(r"/join#token=([A-Za-z0-9_\-]+)")


def enrol_pupils(demo: Demo, code: str, head: Browser) -> None:
    for arm, pupils in school_pupils(code, full=demo.full).items():
        for pupil in pupils:
            made = head.post(
                "/school/students",
                {
                    "surname": pupil.surname,
                    "first_name": pupil.first_name,
                    "admission_number": pupil.admission_number,
                    "gender": pupil.gender,
                    "arm_id": demo.ids[key(code, arm)],
                },
            )
            demo.ids[key(code, f"{pupil.first_name} {pupil.surname}")] = made["id"]
            demo.ids[key(code, pupil.admission_number)] = made["id"]
        if pupils:
            demo.ids[key(code, f"first pupil of {arm}")] = demo.ids[
                key(code, pupils[0].admission_number)
            ]


def give_pupil_logins(demo: Demo) -> None:
    for code, number, username in PUPIL_LOGINS:
        head = demo.as_(SETUP[code]["principal"])
        slip = head.post(f"/school/students/{demo.ids[key(code, number)]}/login",
                         {"username": username})  # fmt: skip
        demo.take_over(number, slip["temporary_password"], school_code=code)
        demo.people[username] = demo.people[number]


def ward_list(demo: Demo, code: str, wards: list[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        {"student_id": demo.ids[key(code, name)], "relationship": relationship}
        for name, relationship in wards
    ]


def ikenna_joins(demo: Demo) -> None:
    """GMC asks; Ikenna joins from the emailed link; BSA asks; he accepts (D-138)."""
    demo.as_("ngozi.okeke").post(
        "/school/guardians",
        {
            "full_name": "Ikenna Obi",
            "email": IKENNA_EMAIL,
            "login": "link_request",
            "wards": ward_list(
                demo, "GMC", [("Chukwuemeka Obi", "Father"), ("Adaeze Obi", "Father")]
            ),
        },
    )
    tokens = [
        match.group(1)
        for email in demo.read_mail()
        if email.to == IKENNA_EMAIL
        for match in [JOIN_LINK.search(email.text)]
        if match is not None
    ]
    if not tokens:
        raise SeedError("GMC's link request to Ikenna Obi had no join link.")
    ikenna = Browser(demo.app, demo.origin)
    ikenna.post("/auth/join", {"token": tokens[-1], "password": demo.password})
    demo.people[IKENNA] = ikenna
    demo.sign_in[IKENNA] = (IKENNA_EMAIL, None)

    demo.as_("chiamaka.nwafor").post(
        "/school/guardians",
        {
            "full_name": "Ikenna Obi",
            "email": IKENNA_EMAIL,
            "login": "link_request",
            "wards": ward_list(demo, "BSA", [("Kosi Obi", "Father")]),
        },
    )
    for request in ikenna.get("/me/link-requests"):
        if request["school_code"] == "BSA":
            ikenna.post(f"/me/link-requests/{request['id']}/accept")


def slip_parents(demo: Demo) -> None:
    for code, full_name, username, wards in SLIP_PARENTS:
        made = demo.as_(SETUP[code]["principal"]).post(
            "/school/guardians",
            {
                "full_name": full_name,
                "login": "temporary_password",
                "username": username,
                "wards": ward_list(demo, code, wards),
            },
        )
        demo.take_over(username, made["temporary_password"])


def seed_pupils(demo: Demo) -> None:
    for code, setup in SETUP.items():
        enrol_pupils(demo, code, demo.as_(setup["principal"]))
    give_pupil_logins(demo)
    ikenna_joins(demo)
    slip_parents(demo)
    # Anything else the seed queued goes into the mailbox here, never to Resend.
    demo.read_mail()
