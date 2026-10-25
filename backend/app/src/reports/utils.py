"""Small helpers of the reports domain, with no database (D-173)."""

from typing import Any, Literal

from app.src.reports.schemas import ScoreCard, Settings, SkillsCard


def shown(settings: Settings, block: str) -> bool:
    return block in settings.blocks and block not in settings.hidden


def parse(card: Literal["scores", "skills"], raw: dict[str, Any]) -> Settings:
    model = SkillsCard if card == "skills" else ScoreCard
    return model.model_validate({**raw, "card": card})
