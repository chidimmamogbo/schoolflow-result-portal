"""The platform's defaults for skill ratings (SPEC F26 rules 1 and 2; D-135;
NAVIGATION_AND_SETTINGS.md "Learning areas and skills"; design brief section 12).

Copied into a school when it is set up; the school then edits its own copy.
Pre-science and Handwriting have no sample skills in the documents, so
schools add their own until default wording is approved.
"""

from typing import NamedTuple


class ScalePoint(NamedTuple):
    name: str
    code: str


# Best point first (the design: "List the best point first"). The documents give
# no default descriptions; schools add their own.
RATING_SCALE = (
    ScalePoint("Excellent", "E"),
    ScalePoint("Very good", "VG"),
    ScalePoint("Good", "G"),
    ScalePoint("Fair", "F"),
    ScalePoint("Needs improvement", "NI"),
)

# Pupils rated at or below this point appear in Students needing attention (F23 rule 8).
ATTENTION_POINT = "NI"

# Learning areas for a level in Skill ratings mode, in order, with sample skills.
LEARNING_AREAS: dict[str, tuple[str, ...]] = {
    "Number work": ("Counts 1 to 20", "Recognises shapes"),
    "Letter work": ("Recognises letters A to Z", "Writes own name"),
    "Phonics": ("Sounds letters correctly",),
    "Rhymes and songs": ("Recites rhymes",),
    "Pre-science": (),
    "Handwriting": (),
    "Creative arts": ("Colours within lines",),
    "Social habits": ("Shares with others", "Greets politely"),
    "Health habits": ("Washes hands",),
    "Physical development": ("Hops on one foot",),
}
