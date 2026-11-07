from datetime import date

import pytest
from pydantic import ValidationError

from app.agent.profile import TripProfile


def test_missing_required_lists_days_and_preferences():
    profile = TripProfile(destination="北京")

    assert profile.missing_required() == ["days", "preferences"]
    assert profile.is_complete() is False


def test_optional_slots_have_defaults():
    profile = TripProfile(destination="北京")

    assert profile.travelers == 1
    assert profile.budget_level == "舒适"
    assert profile.accommodation == "酒店"
    assert profile.start_date is None


def test_dates_derive_days_inclusive():
    profile = TripProfile(destination="北京").merge(
        {"start_date": "2026-11-20", "end_date": "2026-11-22"}
    )

    assert profile.days == 3
    assert profile.start_date == date(2026, 11, 20)


def test_merge_keeps_existing_fields():
    profile = TripProfile(destination="北京", days=3, preferences=["历史"])

    merged = profile.merge({"travelers": 2})

    assert merged.destination == "北京"
    assert merged.days == 3
    assert merged.preferences == ["历史"]
    assert merged.travelers == 2
    assert merged is not profile


def test_complete_when_required_slots_present():
    profile = TripProfile(destination="北京", days=3, preferences=["历史"])

    assert profile.is_complete() is True
    assert profile.missing_required() == []


def test_invalid_budget_level_is_rejected():
    with pytest.raises(ValidationError):
        TripProfile(destination="北京", budget_level="奢侈")
