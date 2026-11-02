"""The pricing engine: pure functions, no database (BUILD_PROMPT 9.2t; SPEC F19; D-088 to D-092).

Volume pricing: the student count picks the plan and every student pays that
plan's price. With 580 students on Standard at ₦500, the bill is ₦290,000.
Cliff protection caps a bill at the smallest possible bill on any higher plan,
so a school is never better off with more students. Money is integer kobo.
"""

import datetime as dt
import itertools
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    name: str
    min_students: int
    max_students: int | None  # None: open-ended, the last plan only
    price_kobo: int


@dataclass(frozen=True)
class Bill:
    plan: Plan
    rate_kobo: int
    amount_kobo: int
    capped: bool


# SPEC F19 rule 2: used until the super admin saves a version.
DEFAULT_PLANS = (
    Plan("Basic", 1, 499, 100_000),
    Plan("Standard", 500, 1000, 50_000),
    Plan("Premium", 1001, None, 30_000),
)


def plan_for(students: int, plans: tuple[Plan, ...]) -> Plan:
    for plan in plans:
        if plan.min_students <= students and (
            plan.max_students is None or students <= plan.max_students
        ):
            return plan
    raise ValueError("A bill needs at least one student and a plan that covers them.")


def cap_for(plan: Plan, plans: tuple[Plan, ...]) -> int | None:
    """The smallest possible bill on any higher plan; None for the last plan."""
    higher = [p.min_students * p.price_kobo for p in plans if p.min_students > plan.min_students]
    return min(higher) if higher else None


def bill_for(students: int, plans: tuple[Plan, ...], *, cliff_protection: bool) -> Bill:
    plan = plan_for(students, plans)
    full = students * plan.price_kobo
    cap = cap_for(plan, plans) if cliff_protection else None
    amount = full if cap is None else min(full, cap)
    return Bill(plan, plan.price_kobo, amount, amount < full)


def price_check(plans: tuple[Plan, ...]) -> list[tuple[int, int]]:
    """The student ranges where a bigger school would pay less (F19 rule 5), first to last."""
    ranges: list[tuple[int, int]] = []
    for plan in plans:
        cap = cap_for(plan, plans)
        if cap is None or plan.max_students is None:
            continue
        low = max(plan.min_students, cap // plan.price_kobo + 1)
        if low <= plan.max_students:
            ranges.append((low, plan.max_students))
    return ranges


def plan_problems(plans: tuple[Plan, ...]) -> list[str]:
    """Why a price list cannot be saved, in plain words (AC19.1, D-090); empty when fine."""
    if not plans:
        return ["Add at least one plan."]
    problems: list[str] = []
    if plans[0].min_students != 1:
        problems.append("Plans must start at 1 student.")
    for earlier, plan in itertools.pairwise(plans):
        if earlier.max_students is not None and plan.min_students != earlier.max_students + 1:
            problems.append(f"{plan.name} overlaps or leaves a gap after {earlier.name}.")
    if plans[-1].max_students is not None or any(p.max_students is None for p in plans[:-1]):
        problems.append("Only the last plan has no upper limit, and it must have none.")
    for plan in plans:
        if plan.max_students is not None and plan.max_students < plan.min_students:
            problems.append(f"{plan.name} ends before it starts.")
        if plan.price_kobo <= 0:
            problems.append(f"{plan.name} needs a price above zero.")
    names = [plan.name.strip().lower() for plan in plans]
    if len(set(names)) != len(names):
        problems.append("Each plan needs its own name.")
    return problems


def subscription_status(
    billing_enabled: bool,
    stored: str,
    oldest_unpaid_due: dt.date | None,
    grace_days: int,
    today: dt.date,
) -> str:
    """D-092: suspension is manual and stays; the rest follows the oldest unpaid invoice."""
    if stored == "suspended":
        return "suspended"
    if not billing_enabled:
        return "free_pilot"
    if oldest_unpaid_due is None:
        return "active"
    if today > oldest_unpaid_due + dt.timedelta(days=grace_days):
        return "overdue"
    return "due"
