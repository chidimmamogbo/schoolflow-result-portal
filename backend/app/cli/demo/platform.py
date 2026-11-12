"""The platform part of the demo: price list, schools and principals (D-180).

ACCEPTANCE_TESTS fixtures: GMC is Secondary only with every feature on and
billing on; BSA is Nursery and Primary with the Correction queue off on a free
pilot; RCS has all three levels. All names, phones and emails are fictional
(`.example` addresses never reach a real inbox).
"""

from typing import Any

from app.cli.demo.browser import Demo, SeedError

SUPER_ADMIN = "platform.admin"

ALL_ON = {
    "results": True,
    "report_cards": True,
    "parent_portal": True,
    "correction_queue": True,
    "notice_board": True,
    "email_notifications": True,
}

SCHOOLS: list[dict[str, Any]] = [
    {
        "name": "Greenfield Model College",
        "email": "office@gmc.example",
        "phone": "08030001122",
        "address": "14 Chime Avenue, Independence Layout",
        "city": "Enugu",
        "state": "Enugu",
        "code": "GMC",
        "school_type": "secondary_only",
        "colour": "#1E6B45",
        "features": ALL_ON,
        "billing": "on",
        "principal": {
            "full_name": "Ngozi Okeke",
            "username": "ngozi.okeke",
            "email": "ngozi.okeke@gmc.example",
        },
    },
    {
        "name": "Bright Stars Academy",
        "email": "office@bsa.example",
        "phone": "08010000002",
        "address": "3 University Road",
        "city": "Nsukka",
        "state": "Enugu",
        "code": "BSA",
        "school_type": "nursery_primary",
        "colour": "#7A1F2B",
        "features": {**ALL_ON, "correction_queue": False},
        "billing": "free_pilot",
        "principal": {
            "full_name": "Chiamaka Nwafor",
            "username": "chiamaka.nwafor",
            "email": "chiamaka.nwafor@bsa.example",
        },
    },
    {
        "name": "Royal Crest Schools",
        "email": "office@rcs.example",
        "phone": "08010000003",
        "address": "Trans-Ekulu",
        "city": "Enugu",
        "state": "Enugu",
        "code": "RCS",
        "school_type": "all_levels",
        "colour": "#1D3A6E",
        "features": ALL_ON,
        "billing": "on",
        "principal": {
            "full_name": "Femi Adeyemi",
            "username": "femi.adeyemi",
            "email": "femi.adeyemi@rcs.example",
        },
    },
]


def save_default_prices(owner: Any) -> int:
    """The default price list as version 1, unless a version is saved already."""
    page = owner.get("/platform/pricing")
    if page["version"] is not None:
        return int(page["version"])
    return int(owner.post("/platform/pricing", {"plans": page["plans"]})["version"])


def check_nothing_seeded(owner: Any) -> None:
    """Only an empty database: the seed reads all queued mail, which must all be its own."""
    if owner.get("/platform/schools"):
        raise SeedError("The database already has schools. Seed an empty database.")


def create_schools(demo: Demo, owner: Any) -> None:
    """Each school and its principal, who signs in once with a temporary password."""
    for form in SCHOOLS:
        made = owner.post("/platform/schools", form)
        school_id = made["id"]
        demo.ids[form["code"]] = school_id
        username = form["principal"]["username"]
        admins = owner.get(f"/platform/schools/{school_id}/admins")
        principal = next(a for a in admins if a["username"] == username)
        demo.ids[username] = principal["id"]
        slip = owner.post(
            f"/platform/schools/{school_id}/admins/{principal['id']}/temporary-password"
        )
        demo.take_over(username, slip["temporary_password"])


def seed_platform(demo: Demo) -> None:
    owner = demo.as_(SUPER_ADMIN)
    check_nothing_seeded(owner)
    save_default_prices(owner)
    create_schools(demo, owner)
