"""Exact public request and response schemas from the GridWise specification."""
from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]
BatteryAction = Literal["charge", "discharge", "idle"]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiniteModel(StrictModel):
    @field_validator("*", mode="after")
    @classmethod
    def reject_non_finite_numbers(cls, value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value


class Battery(FiniteModel):
    capacity_kwh: float = Field(gt=0)
    initial_energy_kwh: float = Field(ge=0)
    minimum_energy_kwh: float = Field(ge=0)
    max_charge_kwh_per_hour: float = Field(ge=0)
    max_discharge_kwh_per_hour: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_energy_levels(self) -> "Battery":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        if self.initial_energy_kwh < self.minimum_energy_kwh:
            raise ValueError("initial_energy_kwh cannot be below minimum_energy_kwh")
        return self


class HourData(FiniteModel):
    hour: int = Field(ge=0, le=23)
    demand_kwh: float = Field(ge=0)
    solar_kwh: float = Field(ge=0)
    tariff_bdt_per_kwh: float = Field(ge=0)


class DirectiveInterpretation(StrictModel):
    note_index: int = Field(ge=0)
    applies: bool
    directive_type: DirectiveType
    structured_adjustment: dict | None = None
    explanation: str


class HourlyPlan(FiniteModel):
    hour: int = Field(ge=0, le=23)
    grid_kwh: float = Field(ge=0)
    solar_used_kwh: float = Field(ge=0)
    battery_action: BatteryAction
    battery_kwh: float = Field(ge=0)
    battery_energy_after_kwh: float = Field(ge=0)


class OptimizeRequest(StrictModel):
    scenario_id: NonEmptyText
    operator_notes: list[NonEmptyText] = Field(min_length=1, max_length=3)
    hours: list[HourData] = Field(min_length=24, max_length=24)
    battery: Battery

    @model_validator(mode="after")
    def validate_hours(self) -> "OptimizeRequest":
        if sorted(row.hour for row in self.hours) != list(range(24)):
            raise ValueError("hours must contain each integer from 0 through 23 exactly once")
        return self


class OptimizeResponse(StrictModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourlyPlan] = Field(min_length=24, max_length=24)
    total_grid_kwh: float = Field(ge=0)
    total_cost_bdt: float = Field(ge=0)
    peak_grid_kwh: float = Field(ge=0)
    plan_summary: str
