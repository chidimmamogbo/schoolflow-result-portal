"""The platform's defaults for a new school's grading set-up (SPEC F08 rules 1, 2, 4,
5 and 6; section 12; D-135).

Copied into a school when it is set up, then the school edits its own copy.
The super admin will be able to change these defaults in Platform settings,
School defaults (F24). The A1 to F9 bands are common practice, not presented
as official WAEC mappings.
"""

from typing import NamedTuple


class GradeBand(NamedTuple):
    grade: str
    min_score: int
    max_score: int
    remark: str


class Component(NamedTuple):
    name: str
    label: str
    max_score: int


# Junior and Senior Secondary.
SECONDARY_GRADE_BANDS = (
    GradeBand("A1", 75, 100, "Excellent"),
    GradeBand("B2", 70, 74, "Very good"),
    GradeBand("B3", 65, 69, "Good"),
    GradeBand("C4", 60, 64, "Credit"),
    GradeBand("C5", 55, 59, "Credit"),
    GradeBand("C6", 50, 54, "Credit"),
    GradeBand("D7", 45, 49, "Pass"),
    GradeBand("E8", 40, 44, "Pass"),
    GradeBand("F9", 0, 39, "Fail"),
)

# Primary, and Nursery when a school puts Nursery in Scores mode.
PRIMARY_GRADE_BANDS = (
    GradeBand("A", 70, 100, "Excellent"),
    GradeBand("B", 60, 69, "Very good"),
    GradeBand("C", 50, 59, "Good"),
    GradeBand("D", 45, 49, "Fair"),
    GradeBand("E", 40, 44, "Pass"),
    GradeBand("F", 0, 39, "Fail"),
)

# Every level in Scores mode starts from this structure (F08 rule 2).
DEFAULT_COMPONENTS = (
    Component("Continuous assessment 1", "CA1", 20),
    Component("Continuous assessment 2", "CA2", 20),
    Component("Examination", "Exam", 60),
)

DEFAULT_PASS_MARK = 40

AFFECTIVE_TRAITS = (
    "Punctuality",
    "Neatness",
    "Politeness",
    "Honesty",
    "Self-control",
    "Attentiveness",
    "Leadership",
)

PSYCHOMOTOR_TRAITS = (
    "Handwriting",
    "Games and sports",
    "Verbal fluency",
    "Handling of tools",
    "Drawing and painting",
    "Crafts",
)

# The 1 to 5 key for affective and psychomotor ratings.
TRAIT_KEY = {
    5: "Excellent",
    4: "Good",
    3: "Average",
    2: "Below average",
    1: "Unsatisfactory",
}
