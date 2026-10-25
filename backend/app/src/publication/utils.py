"""Small helpers of the publication domain, with no database (D-173)."""

import json
import re
import secrets
from decimal import Decimal
from typing import Any

# D-072: Crockford Base32 without I, L, O or U.
CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def plural(count: int) -> str:
    return f"{count} student" if count == 1 else f"{count} students"


# --- publishing -------------------------------------------------------------------------------
def new_verification_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def report_codes(
    school_code: str,
    session_name: str,
    term_number: int,
    class_name: str,
    admissions: list[str],
    kept: dict[str, str] | None = None,
    taken: set[str] | None = None,
) -> dict[str, str]:
    """GMC-2627-T1-JSS1A-014 (AT-16.2), different for every pupil.

    The last part of the admission number, or the whole of it when two pupils
    share that part; if an ID is still in use (by a classmate, or by another
    pupil of the school this term, `taken`), it gets -2, -3 and so on. A pupil
    who already has an ID this term keeps it (`kept`): the database requires
    the same ID in every revision.
    """
    kept = kept or {}
    years = session_name.split("/")
    prefix = f"{school_code}-{years[0][-2:]}{years[-1][-2:]}-T{term_number}-{compact(class_name)}"
    parts = {a: re.findall(r"[A-Z0-9]+", a.upper()) or ["PUPIL"] for a in admissions}
    counts: dict[str, int] = {}
    for found_parts in parts.values():
        counts[found_parts[-1]] = counts.get(found_parts[-1], 0) + 1
    codes = {a: kept[a] for a in admissions if a in kept}
    used = set(taken or set()) | set(codes.values())
    for admission in sorted(a for a in admissions if a not in kept):
        tail = parts[admission][-1]
        ending = tail if counts[tail] == 1 else "-".join(parts[admission])
        base = f"{prefix}-{ending}"[:64].rstrip("-")
        code, number = base, 2
        while code in used:
            suffix = f"-{number}"
            code = base[: 64 - len(suffix)].rstrip("-") + suffix
            number += 1
        used.add(code)
        codes[admission] = code
    return codes


def as_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def json_dump(value: dict[str, Any]) -> str:
    return json.dumps(value, default=str)
