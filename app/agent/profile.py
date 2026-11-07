from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

BudgetLevel = Literal["经济", "舒适", "豪华"]
Accommodation = Literal["酒店", "民宿", "青旅", "不需要"]

REQUIRED_SLOTS: tuple[str, ...] = ("destination", "days", "preferences")


class TripProfile(BaseModel):
    destination: str | None = None
    days: int | None = Field(default=None, ge=1)
    preferences: list[str] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int = Field(default=1, ge=1)
    budget_level: BudgetLevel = "舒适"
    accommodation: Accommodation = "酒店"

    def missing_required(self) -> list[str]:
        missing: list[str] = []
        if not self.destination:
            missing.append("destination")
        if self.days is None:
            missing.append("days")
        if not self.preferences:
            missing.append("preferences")
        return missing

    def is_complete(self) -> bool:
        return not self.missing_required()

    def merge(self, updates: dict[str, Any]) -> "TripProfile":
        known = type(self).model_fields
        data = self.model_dump()
        for key, value in updates.items():
            if key in known and value is not None:
                data[key] = value

        start = data.get("start_date")
        end = data.get("end_date")
        if start is not None and end is not None:
            start_date = (
                start if isinstance(start, date) else date.fromisoformat(str(start))
            )
            end_date = end if isinstance(end, date) else date.fromisoformat(str(end))
            data["days"] = (end_date - start_date).days + 1

        return type(self).model_validate(data)
