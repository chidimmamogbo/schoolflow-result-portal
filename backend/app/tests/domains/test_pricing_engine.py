"""The pricing engine (BUILD_PROMPT 9.2t; SPEC F19 rules 1 to 5; AC19.1 to AC19.4; D-088 to D-090).

Behaviour: the student count picks the plan and every student pays that plan's
price (volume, never graduated). With cliff protection a school never pays
more than the smallest possible bill on any higher plan. The price check lists
the ranges where a bigger school would pay less. Plans start at 1, follow on
with no gap or overlap, only the last is open-ended, prices are whole kobo
above zero and names are unique. A subscription's status follows its invoices,
the due date and the grace period. No database; all data is fictional.
"""

import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.src.billing.pricing import (
    DEFAULT_PLANS,
    Plan,
    bill_for,
    plan_problems,
    price_check,
    subscription_status,
)


def naira(amount: int) -> int:
    return amount * 100


@pytest.mark.parametrize(
    ("students", "plan", "amount"),
    [
        (499, "Basic", 499_000),
        (500, "Standard", 250_000),
        (1000, "Standard", 500_000),
        (1001, "Premium", 300_300),
    ],
)
def test_amounts_with_cliff_protection_off(students: int, plan: str, amount: int) -> None:
    """AC19.2."""
    bill = bill_for(students, DEFAULT_PLANS, cliff_protection=False)
    assert (bill.plan.name, bill.amount_kobo, bill.capped) == (plan, naira(amount), False)
    assert bill.rate_kobo == bill.plan.price_kobo


@pytest.mark.parametrize(
    ("students", "plan", "amount", "capped"),
    [
        (499, "Basic", 250_000, True),
        (580, "Standard", 290_000, False),
        (642, "Standard", 300_300, True),
        (1000, "Standard", 300_300, True),
        (1001, "Premium", 300_300, False),
        (1, "Basic", 1_000, False),
        (250, "Basic", 250_000, False),
        (251, "Basic", 250_000, True),
        (600, "Standard", 300_000, False),
        (601, "Standard", 300_300, True),
    ],
)
def test_amounts_with_cliff_protection_on(
    students: int, plan: str, amount: int, capped: bool
) -> None:
    """AC19.3, and the counts either side of each cap."""
    bill = bill_for(students, DEFAULT_PLANS, cliff_protection=True)
    assert (bill.plan.name, bill.amount_kobo, bill.capped) == (plan, naira(amount), capped)


def test_the_cap_looks_at_every_higher_plan_not_just_the_next() -> None:
    plans = (
        Plan("Small", 1, 100, naira(1000)),
        Plan("Middle", 101, 200, naira(900)),
        Plan("Large", 201, None, naira(100)),
    )
    # Middle's smallest bill is 90,900; Large's is only 20,100.
    assert bill_for(100, plans, cliff_protection=True).amount_kobo == naira(20_100)


def test_a_count_below_the_first_plan_has_no_bill() -> None:
    with pytest.raises(ValueError, match="at least one student"):
        bill_for(0, DEFAULT_PLANS, cliff_protection=True)


def test_the_price_check_lists_the_ranges_with_the_default_prices() -> None:
    """AC19.4."""
    assert price_check(DEFAULT_PLANS) == [(251, 499), (601, 1000)]


def test_fair_prices_give_an_empty_price_check() -> None:
    plans = (Plan("Basic", 1, 499, naira(500)), Plan("Standard", 500, None, naira(500)))
    assert price_check(plans) == []


@st.composite
def price_lists(draw: st.DrawFn) -> tuple[Plan, ...]:
    sizes = draw(st.lists(st.integers(1, 400), min_size=1, max_size=4))
    prices = draw(st.lists(st.integers(1, 200_000), min_size=len(sizes) + 1, max_size=5))
    plans: list[Plan] = []
    start = 1
    for number, size in enumerate(sizes):
        plans.append(Plan(f"Plan {number}", start, start + size - 1, prices[number]))
        start += size
    plans.append(Plan("Last", start, None, prices[len(sizes)]))
    return tuple(plans)


@given(price_lists(), st.integers(1, 2000))
def test_with_cliff_protection_a_bigger_school_never_pays_less(
    plans: tuple[Plan, ...], students: int
) -> None:
    for bigger in (students + 1, students + 37, students + 900):
        assert (
            bill_for(students, plans, cliff_protection=True).amount_kobo
            <= bill_for(bigger, plans, cliff_protection=True).amount_kobo
        )


@given(price_lists(), st.integers(1, 2000))
def test_the_price_check_names_exactly_the_counts_the_cap_changes(
    plans: tuple[Plan, ...], students: int
) -> None:
    flagged = any(low <= students <= high for low, high in price_check(plans))
    assert flagged == bill_for(students, plans, cliff_protection=True).capped


def test_default_plans_pass() -> None:
    assert plan_problems(DEFAULT_PLANS) == []


@pytest.mark.parametrize(
    ("plans", "problem"),
    [
        ((), "Add at least one plan."),
        (
            (Plan("Basic", 2, None, 100),),
            "Plans must start at 1 student.",
        ),
        (
            (Plan("Basic", 1, 520, 100), Plan("Standard", 500, None, 100)),
            "Standard overlaps or leaves a gap after Basic.",
        ),
        (
            (Plan("Basic", 1, 499, 100), Plan("Standard", 510, None, 100)),
            "Standard overlaps or leaves a gap after Basic.",
        ),
        (
            (Plan("Basic", 1, 499, 100), Plan("Standard", 500, 600, 100)),
            "Only the last plan has no upper limit, and it must have none.",
        ),
        (
            (Plan("Basic", 1, None, 100), Plan("Standard", 500, None, 100)),
            "Only the last plan has no upper limit, and it must have none.",
        ),
        (
            (Plan("Basic", 1, 0, 100), Plan("Standard", 1, None, 100)),
            "Basic ends before it starts.",
        ),
        ((Plan("Basic", 1, None, 0),), "Basic needs a price above zero."),
        (
            (Plan("Basic", 1, 10, 100), Plan("basic ", 11, None, 100)),
            "Each plan needs its own name.",
        ),
    ],
)
def test_bad_plans_are_named(plans: tuple[Plan, ...], problem: str) -> None:
    """AC19.1, D-090."""
    assert problem in plan_problems(plans)


TODAY = dt.date(2027, 1, 20)


@pytest.mark.parametrize(
    ("billing", "stored", "due", "grace", "expected"),
    [
        (False, "active", None, 14, "free_pilot"),
        (False, "active", dt.date(2027, 1, 1), 14, "free_pilot"),
        (True, "suspended", None, 14, "suspended"),
        (True, "suspended", dt.date(2027, 1, 1), 14, "suspended"),
        (False, "suspended", None, 14, "suspended"),
        (True, "active", None, 14, "active"),
        (True, "due", None, 14, "active"),
        (True, "active", dt.date(2027, 1, 25), 14, "due"),
        (True, "active", dt.date(2027, 1, 6), 14, "due"),  # the last day of grace
        (True, "due", dt.date(2027, 1, 5), 14, "overdue"),
        (True, "active", dt.date(2027, 1, 19), 0, "overdue"),
        (True, "active", dt.date(2027, 1, 20), 0, "due"),
    ],
)
def test_the_status_follows_the_invoices_and_the_grace_period(
    billing: bool, stored: str, due: dt.date | None, grace: int, expected: str
) -> None:
    """F19 rule 7, D-092."""
    assert subscription_status(billing, stored, due, grace, TODAY) == expected
