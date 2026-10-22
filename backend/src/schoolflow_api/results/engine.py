"""The results engine: totals, grades, averages and positions (SPEC F08 rule 7; D-166).

Pure functions with no database, like a calculator: the score entry,
broadsheet and publishing code read the raw scores and the school's set-up,
call these, and store only what publication needs (the snapshot keeps the
results with CALCULATION_VERSION, so an old report can always say how it was
worked out).

Rules:
- A subject total is the sum of the component scores. The components'
  maximums add up to 100, so this is already the weighted total (CA1 /20 +
  CA2 /20 + Exam /60). A total exists only when every score is present and
  within its column's maximum; otherwise the missing and out-of-range
  columns are listed and the total is None.
- Grades come from the school's bands for the level.
- Positions share ties and skip the next places ("1st, 1st, 3rd", AC08.1).
  Ties are judged on exact values (fractions), never on rounded ones.
- Averages are shown rounded half up to two decimal places (77.50).
- A pupil's overall total, average and position need a total in every
  subject they take; otherwise they are listed as incomplete.
- The class average is the average of the pupils' averages.
"""

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import NamedTuple, Protocol

# Bump when any rule below changes what a result would be.
CALCULATION_VERSION = "1.0"
TWO_PLACES = Decimal("0.01")

Scores = Mapping[str, int | None]
Number = int | Fraction


class Band(Protocol):
    @property
    def grade(self) -> str: ...
    @property
    def min_score(self) -> int: ...
    @property
    def max_score(self) -> int: ...
    @property
    def remark(self) -> str: ...


class Column(NamedTuple):
    """One component of the assessment structure: its id, column label and maximum."""

    key: str
    label: str
    max_score: int


class Grade(NamedTuple):
    grade: str
    remark: str


@dataclass(frozen=True)
class SubjectTotal:
    total: int | None
    missing: tuple[str, ...]
    out_of_range: tuple[str, ...]


@dataclass(frozen=True)
class PupilSubject:
    total: int | None
    grade: str | None
    remark: str | None
    position: int | None
    below_pass_mark: bool
    missing: tuple[str, ...]
    out_of_range: tuple[str, ...]


@dataclass(frozen=True)
class SubjectResult:
    pupils: dict[str, PupilSubject]
    average: Decimal | None
    highest: int | None
    lowest: int | None


@dataclass(frozen=True)
class PupilResult:
    subjects: int
    complete: bool
    total: int | None
    average: Decimal | None
    position: int | None
    below_pass_mark: tuple[str, ...]


@dataclass(frozen=True)
class ClassResult:
    subjects: dict[str, SubjectResult]
    pupils: dict[str, PupilResult]
    class_average: Decimal | None
    class_size: int
    # Pupil -> subjects without a total (they have no overall result yet).
    incomplete: dict[str, tuple[str, ...]]
    calculation_version: str = CALCULATION_VERSION


# --- the small rules --------------------------------------------------------------------------


def subject_total(scores: Scores, columns: Sequence[Column]) -> SubjectTotal:
    missing = tuple(c.label for c in columns if scores.get(c.key) is None)
    out_of_range = tuple(
        c.label
        for c in columns
        if (value := scores.get(c.key)) is not None and not 0 <= value <= c.max_score
    )
    if missing or out_of_range:
        return SubjectTotal(None, missing, out_of_range)
    return SubjectTotal(sum(int(scores[c.key] or 0) for c in columns), (), ())


def grade_for(total: int, bands: Iterable[Band]) -> Grade | None:
    for band in bands:
        if band.min_score <= total <= band.max_score:
            return Grade(band.grade, band.remark)
    return None


def rank[K: Hashable](values: Mapping[K, Number | None]) -> dict[K, int]:
    """Competition ranking: equal values share a place and the next places are skipped."""
    present = {key: value for key, value in values.items() if value is not None}
    ordered = sorted(present.values(), reverse=True)
    first_place: dict[Number, int] = {}
    for place, value in enumerate(ordered, start=1):
        first_place.setdefault(value, place)
    return {key: first_place[value] for key, value in present.items()}


def ordinal(place: int) -> str:
    """1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st."""
    if 11 <= place % 100 <= 13:
        return f"{place}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")
    return f"{place}{suffix}"


def exact_average(values: Sequence[int]) -> Fraction | None:
    return Fraction(sum(values), len(values)) if values else None


def shown(value: Fraction | None) -> Decimal | None:
    """Rounded half up to two places, for display and the snapshot."""
    if value is None:
        return None
    return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )


def average(values: Sequence[int]) -> Decimal | None:
    return shown(exact_average(values))


def duplicates(rows: Iterable[tuple[str, ...]]) -> dict[tuple[str, ...], list[int]]:
    """Rows (1-based) that repeat the same key, ignoring capitals: an import's double entries."""
    seen: dict[tuple[str, ...], list[int]] = {}
    for number, row in enumerate(rows, start=1):
        seen.setdefault(tuple(part.strip().lower() for part in row), []).append(number)
    return {key: numbers for key, numbers in seen.items() if len(numbers) > 1}


# --- a whole class ------------------------------------------------------------------------------


def compute_class(
    sheets: Mapping[str, Mapping[str, Scores]],
    columns: Sequence[Column],
    bands: Sequence[Band],
    *,
    pass_mark: int,
) -> ClassResult:
    """Every subject's results and every pupil's overall result for one class (arm) and term.

    `sheets` maps a subject to its pupils' scores by column key; a pupil who
    does not take a subject is simply not on that sheet (AC05.2).
    """
    if sum(c.max_score for c in columns) != 100:
        raise ValueError("The columns' maximums must add up to 100.")

    subjects: dict[str, SubjectResult] = {}
    totals_by_pupil: dict[str, dict[str, int | None]] = {}
    for subject, pupils in sheets.items():
        totals = {pupil: subject_total(scores, columns) for pupil, scores in pupils.items()}
        positions = rank({pupil: t.total for pupil, t in totals.items()})
        rows: dict[str, PupilSubject] = {}
        for pupil, t in totals.items():
            grade = grade_for(t.total, bands) if t.total is not None else None
            rows[pupil] = PupilSubject(
                total=t.total,
                grade=grade.grade if grade else None,
                remark=grade.remark if grade else None,
                position=positions.get(pupil),
                below_pass_mark=t.total is not None and t.total < pass_mark,
                missing=t.missing,
                out_of_range=t.out_of_range,
            )
            totals_by_pupil.setdefault(pupil, {})[subject] = t.total
        complete = [t.total for t in totals.values() if t.total is not None]
        subjects[subject] = SubjectResult(
            pupils=rows,
            average=average(complete),
            highest=max(complete, default=None),
            lowest=min(complete, default=None),
        )

    exact: dict[str, Fraction | None] = {}
    incomplete: dict[str, tuple[str, ...]] = {}
    for pupil, by_subject in totals_by_pupil.items():
        lacking = tuple(sorted(s for s, total in by_subject.items() if total is None))
        if lacking:
            incomplete[pupil] = lacking
            exact[pupil] = None
        else:
            exact[pupil] = exact_average([t for t in by_subject.values() if t is not None])
    positions = rank(exact)
    pupils = {
        pupil: PupilResult(
            subjects=len(by_subject),
            complete=pupil not in incomplete,
            total=None if pupil in incomplete else sum(t or 0 for t in by_subject.values()),
            average=shown(exact[pupil]),
            position=positions.get(pupil),
            below_pass_mark=tuple(
                sorted(s for s, t in by_subject.items() if t is not None and t < pass_mark)
            ),
        )
        for pupil, by_subject in totals_by_pupil.items()
    }
    complete_averages = [value for value in exact.values() if value is not None]
    class_average = (
        shown(sum(complete_averages, Fraction(0)) / len(complete_averages))
        if complete_averages
        else None
    )
    return ClassResult(
        subjects=subjects,
        pupils=pupils,
        class_average=class_average,
        class_size=len(pupils),
        incomplete=incomplete,
    )
