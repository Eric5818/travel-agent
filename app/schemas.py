from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

DataSource = Literal["tavily", "wttr.in", "estimate"]


class CostRange(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def check_order(self) -> "CostRange":
        if self.min > self.max:
            raise ValueError("min 不能大于 max")
        return self


class Attraction(BaseModel):
    name: str
    category: str = ""
    description: str = ""
    address: str | None = None
    source_url: str = ""


class WeatherInfo(BaseModel):
    date: str
    weather_desc: str
    temp_high_c: float | None = None
    temp_low_c: float | None = None
    chance_of_rain: int | None = Field(default=None, ge=0, le=100)
    suggestion: str = ""
    unavailable: bool = False


class Activity(BaseModel):
    time: str
    name: str
    type: Literal["attraction", "transfer", "rest"]
    duration_min: int = Field(ge=0)
    description: str
    location_hint: str | None = None
    cost_estimate: CostRange | None = None
    source_url: str | None = None


class DayPlan(BaseModel):
    date: str
    day_index: int = Field(ge=1)
    theme: str
    weather: WeatherInfo | None = None
    activities: list[Activity] = Field(default_factory=list)
    accommodation: str | None = None
    daily_cost: CostRange


class BudgetBreakdown(BaseModel):
    lodging: CostRange
    food: CostRange
    local_transport: CostRange
    tickets: CostRange
    total: CostRange


class Itinerary(BaseModel):
    city: str
    start_date: date | None = None
    days: int = Field(ge=1)
    travelers: int = Field(ge=1)
    summary: str
    day_plans: list[DayPlan]
    budget: BudgetBreakdown
    tips: list[str] = Field(default_factory=list)
    data_sources: list[DataSource] = Field(default_factory=list)
