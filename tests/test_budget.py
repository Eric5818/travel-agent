import pytest

from app.agent.tools.budget import estimate_budget
from app.schemas import BudgetBreakdown


def test_budget_levels_increase_lodging():
    economy = estimate_budget(3, 1, "经济")
    comfort = estimate_budget(3, 1, "舒适")
    luxury = estimate_budget(3, 1, "豪华")

    assert economy.lodging.max < comfort.lodging.max < luxury.lodging.max


def test_travelers_scale_food_and_transport_but_not_lodging():
    one = estimate_budget(3, 1, "舒适")
    two = estimate_budget(3, 2, "舒适")

    assert two.lodging == one.lodging
    assert two.food.max == pytest.approx(one.food.max * 2)
    assert two.local_transport.max == pytest.approx(one.local_transport.max * 2)


def test_ticket_total_is_passed_through():
    result = estimate_budget(3, 2, "舒适", ticket_total=350)

    assert result.tickets.min == 350
    assert result.tickets.max == 350


def test_total_is_sum_of_parts():
    result = estimate_budget(3, 2, "舒适", ticket_total=350)

    assert result.total.min == pytest.approx(
        result.lodging.min
        + result.food.min
        + result.local_transport.min
        + result.tickets.min
    )
    assert result.total.max == pytest.approx(
        result.lodging.max
        + result.food.max
        + result.local_transport.max
        + result.tickets.max
    )


def test_days_must_be_positive():
    with pytest.raises(ValueError):
        estimate_budget(0, 1, "舒适")


def test_unknown_budget_level_raises():
    with pytest.raises(ValueError):
        estimate_budget(3, 1, "奢侈")


def test_city_tier_2_is_cheaper_than_tier_1():
    tier1 = estimate_budget(3, 1, "舒适", city_tier=1)
    tier2 = estimate_budget(3, 1, "舒适", city_tier=2)

    assert tier2.total.max < tier1.total.max


def test_returns_budget_breakdown():
    assert isinstance(estimate_budget(3, 1, "舒适"), BudgetBreakdown)
