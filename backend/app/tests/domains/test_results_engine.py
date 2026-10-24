"""The results engine (BUILD_PROMPT 9.2g; SPEC F08 rule 7, F09, F16; AC08.1, AC08.5).

Behaviour: a subject total is the sum of its component scores (the
components' maximums add up to 100, so this is the weighted total) and is
only worked out when every score is present and within its column's
maximum; missing and out-of-range scores are flagged by column; grades come
from the school's bands; positions share ties and skip ("1st, 1st, 3rd");
averages are rounded half up to two places but ties are judged on exact
values; a pupil's overall average and position need every one of their
subjects; duplicates in an import are found; every result carries the
calculation version. Pure functions: no database. All data is fictional.
"""

from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.src.grading.defaults import PRIMARY_GRADE_BANDS, SECONDARY_GRADE_BANDS
from app.src.results.engine import (
    CALCULATION_VERSION,
    Column,
    average,
    compute_class,
    duplicates,
    grade_for,
    ordinal,
    rank,
    subject_total,
)

JSS = (Column("ca1", "CA1", 20), Column("ca2", "CA2", 20), Column("exam", "Exam", 60))


# --- one subject for one pupil ---------------------------------------------------------------


def test_a_total_is_the_sum_of_complete_in_range_scores() -> None:
    result = subject_total({"ca1": 15, "ca2": 18, "exam": 49}, JSS)
    assert (result.total, result.missing, result.out_of_range) == (82, (), ())


def test_missing_and_out_of_range_scores_are_flagged_and_give_no_total() -> None:
    """F09: missing and out-of-range scores block submission and are shown by column."""
    missing = subject_total({"ca1": 15, "exam": 49}, JSS)
    assert (missing.total, missing.missing) == (None, ("CA2",))
    blank = subject_total({"ca1": 15, "ca2": None, "exam": 49}, JSS)
    assert blank.missing == ("CA2",)
    over = subject_total({"ca1": 21, "ca2": 18, "exam": -1}, JSS)
    assert (over.total, over.out_of_range) == (None, ("CA1", "Exam"))
    assert subject_total({}, JSS).missing == ("CA1", "CA2", "Exam")


def test_scores_for_columns_not_in_the_structure_are_ignored() -> None:
    assert subject_total({"ca1": 10, "ca2": 10, "exam": 40, "old": 99}, JSS).total == 60


# --- grades -----------------------------------------------------------------------------


def test_default_grades() -> None:
    """AC08.5, AT-07.6: a Primary total of 65 is a B; Secondary A1 to F9."""
    assert grade_for(65, PRIMARY_GRADE_BANDS) == ("B", "Very good")
    assert grade_for(100, SECONDARY_GRADE_BANDS) == ("A1", "Excellent")
    assert grade_for(74, SECONDARY_GRADE_BANDS) == ("B2", "Very good")
    assert grade_for(39, SECONDARY_GRADE_BANDS) == ("F9", "Fail")
    assert grade_for(0, PRIMARY_GRADE_BANDS) == ("F", "Fail")


@given(st.integers(min_value=0, max_value=100))
def test_every_total_from_0_to_100_has_exactly_one_default_grade(total: int) -> None:
    for bands in (PRIMARY_GRADE_BANDS, SECONDARY_GRADE_BANDS):
        assert sum(b.min_score <= total <= b.max_score for b in bands) == 1
        assert grade_for(total, bands) is not None


def test_a_total_outside_every_band_has_no_grade() -> None:
    assert grade_for(50, PRIMARY_GRADE_BANDS[:1]) is None


# --- positions and averages --------------------------------------------------------------------


def test_ties_share_a_position_and_the_next_is_skipped() -> None:
    """AC08.1: 1st, 1st, 3rd."""
    positions = rank({"ada": 82, "musa": 82, "chi": 75, "bisi": None, "obi": 90})
    assert positions == {"obi": 1, "ada": 2, "musa": 2, "chi": 4}
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 101, 111)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "21st",
        "22nd",
        "23rd",
        "101st",
        "111th",
    ]


@given(st.dictionaries(st.text(min_size=1, max_size=4), st.integers(0, 100), max_size=40))
def test_ranking_rules_hold_for_any_class(totals: dict[str, int]) -> None:
    positions = rank(totals)
    assert set(positions) == set(totals)
    for a, score_a in totals.items():
        better = sum(1 for score in totals.values() if score > score_a)
        assert positions[a] == better + 1  # competition ranking
        for b, score_b in totals.items():
            if score_a == score_b:
                assert positions[a] == positions[b]


def test_averages_round_half_up_but_ties_use_exact_values() -> None:
    assert average([70, 71]) == Decimal("70.50")
    assert average([2, 2, 1]) == Decimal("1.67")
    assert average([1, 2]) == Decimal("1.50")
    assert average([]) is None
    # 66.665 and 66.67 both show as 66.67, but they are not a tie.
    positions = rank({"a": Fraction(66665, 1000), "b": Fraction(6667, 100)})
    assert positions == {"b": 1, "a": 2}


# --- duplicates in an import ---------------------------------------------------------------------


def test_duplicate_rows_are_found() -> None:
    rows = [
        ("GMC/2026/014", "CA1"),
        ("GMC/2026/015", "CA1"),
        ("gmc/2026/014", "ca1"),
        ("GMC/2026/016", "Exam"),
    ]
    assert duplicates(rows) == {("gmc/2026/014", "ca1"): [1, 3]}


# --- a whole class -------------------------------------------------------------------------------


def test_a_class_with_subject_and_overall_results() -> None:
    sheets = {
        "maths": {
            "ada": {"ca1": 18, "ca2": 17, "exam": 50},  # 85
            "musa": {"ca1": 15, "ca2": 15, "exam": 40},  # 70
            "chi": {"ca1": 10, "ca2": 10, "exam": 15},  # 35
        },
        "english": {
            "ada": {"ca1": 12, "ca2": 13, "exam": 45},  # 70
            "musa": {"ca1": 18, "ca2": 17, "exam": 50},  # 85
            "chi": {"ca1": 14, "ca2": 14, "exam": 30},  # 58
        },
    }
    result = compute_class(sheets, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    assert result.calculation_version == CALCULATION_VERSION

    maths = result.subjects["maths"]
    assert {p: (r.total, r.grade, r.position) for p, r in maths.pupils.items()} == {
        "ada": (85, "A1", 1),
        "musa": (70, "B2", 2),
        "chi": (35, "F9", 3),
    }
    assert (maths.average, maths.highest, maths.lowest) == (Decimal("63.33"), 85, 35)
    assert maths.pupils["chi"].below_pass_mark is True

    ada, musa, chi = (result.pupils[p] for p in ("ada", "musa", "chi"))
    assert (ada.total, ada.average, ada.position) == (155, Decimal("77.50"), 1)
    assert (musa.total, musa.average, musa.position) == (155, Decimal("77.50"), 1)
    assert (chi.total, chi.average, chi.position) == (93, Decimal("46.50"), 3)
    assert chi.below_pass_mark == ("maths",)
    assert result.class_average == Decimal("67.17")
    assert result.class_size == 3


def test_a_pupil_missing_a_subject_total_has_no_overall_result() -> None:
    sheets = {
        "maths": {
            "ada": {"ca1": 18, "ca2": 17, "exam": 50},
            "musa": {"ca1": 15, "ca2": 15},
        },  # Exam missing
        "english": {
            "ada": {"ca1": 12, "ca2": 13, "exam": 45},
            "musa": {"ca1": 18, "ca2": 17, "exam": 50},
        },
    }
    result = compute_class(sheets, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    musa = result.pupils["musa"]
    assert (musa.total, musa.average, musa.position, musa.complete) == (None, None, None, False)
    assert result.subjects["maths"].pupils["musa"].missing == ("Exam",)
    assert result.pupils["ada"].position == 1
    assert result.subjects["maths"].average == Decimal("85.00")  # only complete totals count
    assert result.incomplete == {"musa": ("maths",)}


def test_pupils_take_different_subjects() -> None:
    """AC05.2: a pupil who does not take a subject is simply not on its sheet."""
    sheets = {
        "maths": {
            "ada": {"ca1": 20, "ca2": 20, "exam": 60},
            "musa": {"ca1": 10, "ca2": 10, "exam": 30},
        },
        "igbo": {"ada": {"ca1": 10, "ca2": 10, "exam": 30}},
    }
    result = compute_class(sheets, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    assert (result.pupils["ada"].subjects, result.pupils["musa"].subjects) == (2, 1)
    assert (result.pupils["ada"].average, result.pupils["musa"].average) == (
        Decimal("75.00"),
        Decimal("50.00"),
    )
    assert (result.pupils["ada"].position, result.pupils["musa"].position) == (1, 2)


def test_an_empty_class_gives_empty_results() -> None:
    result = compute_class({}, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    assert (result.pupils, result.subjects, result.class_average, result.class_size) == (
        {},
        {},
        None,
        0,
    )


def test_columns_must_add_up_to_100() -> None:
    with pytest.raises(ValueError, match="add up to 100"):
        compute_class({}, JSS[:2], SECONDARY_GRADE_BANDS, pass_mark=40)


@given(
    st.lists(
        st.tuples(st.integers(0, 20), st.integers(0, 20), st.integers(0, 60)),
        min_size=1,
        max_size=30,
    )
)
def test_totals_stay_within_0_to_100_and_match_the_scores(rows: list[tuple[int, int, int]]) -> None:
    sheet = {f"p{i}": {"ca1": a, "ca2": b, "exam": c} for i, (a, b, c) in enumerate(rows)}
    result = compute_class({"maths": sheet}, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    for i, (a, b, c) in enumerate(rows):
        pupil = result.subjects["maths"].pupils[f"p{i}"]
        assert pupil.total == a + b + c
        assert 0 <= (pupil.total or 0) <= 100
        assert pupil.grade is not None
        assert pupil.position is not None and 1 <= pupil.position <= len(rows)


def scores_for(total: int) -> dict[str, int | None]:
    """Fills CA1, then CA2, then the exam (each up to its maximum)."""
    ca1 = min(20, total)
    ca2 = min(20, total - ca1)
    return {"ca1": ca1, "ca2": ca2, "exam": total - ca1 - ca2}


def test_exact_halves_round_up() -> None:
    assert average([1, 0, 0, 0, 0, 0, 0, 0]) == Decimal("0.13")  # 0.125
    assert average([3, 0, 0, 0, 0, 0, 0, 0]) == Decimal("0.38")  # 0.375


def test_overall_positions_use_exact_averages_not_rounded_ones() -> None:
    """Both averages show as 60.38, but 60.385 beats 60.375."""
    eight = [63] + [60] * 7  # 483 / 8 = 60.375
    thirteen = [65] + [60] * 12  # 785 / 13 = 60.3846...
    sheets: dict[str, dict[str, dict[str, int | None]]] = {}
    for index, total in enumerate(thirteen):
        sheets.setdefault(f"s{index}", {})["bisi"] = scores_for(total)
    for index, total in enumerate(eight):
        sheets[f"s{index}"]["ada"] = scores_for(total)
    result = compute_class(sheets, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    ada, bisi = result.pupils["ada"], result.pupils["bisi"]
    assert ada.average == bisi.average == Decimal("60.38")
    assert (bisi.position, ada.position) == (1, 2)


def test_the_pass_mark_itself_is_a_pass() -> None:
    sheets = {"maths": {"ada": scores_for(40), "musa": scores_for(39)}}
    result = compute_class(sheets, JSS, SECONDARY_GRADE_BANDS, pass_mark=40)
    assert result.subjects["maths"].pupils["ada"].below_pass_mark is False
    assert result.subjects["maths"].pupils["musa"].below_pass_mark is True
    assert result.pupils["musa"].below_pass_mark == ("maths",)
