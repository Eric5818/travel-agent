from __future__ import annotations

from app.schemas import BudgetBreakdown, CostRange

# 单价区间（人民币）。住宿按「每晚每间」，餐饮与市内交通按「每人每天」。
LODGING_RATE: dict[str, tuple[float, float]] = {
    "经济": (200, 350),
    "舒适": (400, 700),
    "豪华": (900, 1800),
}

FOOD_RATE: dict[str, tuple[float, float]] = {
    "经济": (80, 150),
    "舒适": (150, 300),
    "豪华": (300, 600),
}

LOCAL_TRANSPORT_RATE: dict[str, tuple[float, float]] = {
    "经济": (15, 30),
    "舒适": (30, 60),
    "豪华": (60, 120),
}

# 城市等级系数：1 线城市不打折，2/3 线依次降低。
CITY_TIER_FACTOR: dict[int, float] = {1: 1.0, 2: 0.85, 3: 0.7}

BUDGET_LEVELS = tuple(LODGING_RATE)


def _range(unit_range: tuple[float, float], multiplier: float) -> CostRange:
    return CostRange(
        min=round(unit_range[0] * multiplier, 2),
        max=round(unit_range[1] * multiplier, 2),
    )


def estimate_budget(
    days: int,
    travelers: int,
    budget_level: str,
    ticket_total: float = 0,
    city_tier: int = 1,
    ticket_range: CostRange | None = None,
    lodging_range: CostRange | None = None,
) -> BudgetBreakdown:
    if days <= 0:
        raise ValueError("days 必须大于 0")
    if travelers <= 0:
        raise ValueError("travelers 必须大于 0")
    if budget_level not in LODGING_RATE:
        raise ValueError(f"未知的预算档次：{budget_level!r}")
    if city_tier not in CITY_TIER_FACTOR:
        raise ValueError(f"未知的城市等级：{city_tier!r}")

    factor = CITY_TIER_FACTOR[city_tier]
    nights = days - 1 if days > 1 else 1

    if lodging_range is not None:
        lodging = lodging_range
    else:
        lodging = _range(LODGING_RATE[budget_level], nights * factor)

    food = _range(FOOD_RATE[budget_level], days * travelers * factor)
    local_transport = _range(
        LOCAL_TRANSPORT_RATE[budget_level], days * travelers * factor
    )
    if ticket_range is not None:
        tickets = ticket_range
    else:
        tickets = CostRange(
            min=round(ticket_total, 2), max=round(ticket_total, 2)
        )

    total = CostRange(
        min=round(
            lodging.min + food.min + local_transport.min + tickets.min, 2
        ),
        max=round(
            lodging.max + food.max + local_transport.max + tickets.max, 2
        ),
    )

    return BudgetBreakdown(
        lodging=lodging,
        food=food,
        local_transport=local_transport,
        tickets=tickets,
        total=total,
    )
