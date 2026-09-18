"""Independent schedule replay and totals calculation for GridWise."""
from __future__ import annotations

import math
from typing import Any

from app.errors import InfeasibleError

HOURS = 24
TOLERANCE = 2e-4


def replay_and_measure(
    hours: list[dict[str, Any]],
    battery: dict[str, Any],
    directives: list[dict[str, Any]],
    plan: list[dict[str, Any]],
) -> tuple[float, float, float]:
    """Replay a generated plan independently and return grid, cost, and peak totals."""
    rows = _ordered_hours(hours)
    if not isinstance(plan, list) or len(plan) != HOURS:
        raise InfeasibleError("Generated plan must contain exactly 24 rows")

    capacity = _number(battery, "capacity_kwh")
    initial = _number(battery, "initial_energy_kwh")
    base_minimum = _number(battery, "minimum_energy_kwh")
    max_charge = _number(battery, "max_charge_kwh_per_hour")
    max_discharge = _number(battery, "max_discharge_kwh_per_hour")

    solar_limit = [_row_number(row, "solar_kwh") for row in rows]
    reserve = [base_minimum] * HOURS
    charge_limit = [max_charge] * HOURS
    discharge_limit = [max_discharge] * HOURS
    grid_limit = [math.inf] * HOURS
    _apply_directives(
        directives,
        solar_limit,
        reserve,
        charge_limit,
        discharge_limit,
        grid_limit,
    )

    previous = initial
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for hour in range(HOURS):
        item = plan[hour]
        if not isinstance(item, dict) or item.get("hour") != hour:
            raise InfeasibleError(f"Generated plan has an invalid hour at index {hour}")

        grid = _row_number(item, "grid_kwh")
        solar = _row_number(item, "solar_used_kwh")
        amount = _row_number(item, "battery_kwh")
        energy = _row_number(item, "battery_energy_after_kwh")
        action = item.get("battery_action")
        if action not in {"charge", "discharge", "idle"}:
            raise InfeasibleError(f"Generated plan has an invalid battery action at hour {hour}")
        if min(grid, solar, amount, energy) < -TOLERANCE:
            raise InfeasibleError(f"Generated plan contains a negative value at hour {hour}")

        charging = amount if action == "charge" else 0.0
        discharging = amount if action == "discharge" else 0.0
        if action == "idle" and amount > TOLERANCE:
            raise InfeasibleError(f"Idle battery amount is non-zero at hour {hour}")
        if charging > charge_limit[hour] + TOLERANCE:
            raise InfeasibleError(f"Charge limit is violated at hour {hour}")
        if discharging > discharge_limit[hour] + TOLERANCE:
            raise InfeasibleError(f"Discharge limit is violated at hour {hour}")
        if grid > grid_limit[hour] + TOLERANCE:
            raise InfeasibleError(f"Grid cap is violated at hour {hour}")
        if solar > solar_limit[hour] + TOLERANCE:
            raise InfeasibleError(f"Solar availability is violated at hour {hour}")
        if energy < reserve[hour] - TOLERANCE or energy > capacity + TOLERANCE:
            raise InfeasibleError(f"Battery bounds are violated at hour {hour}")

        expected_energy = previous + charging - discharging
        if abs(energy - expected_energy) > TOLERANCE:
            raise InfeasibleError(f"Battery state transition is invalid at hour {hour}")
        demand = _row_number(rows[hour], "demand_kwh")
        if abs(grid + solar + discharging - demand - charging) > TOLERANCE:
            raise InfeasibleError(f"Energy balance is invalid at hour {hour}")

        tariff = _row_number(rows[hour], "tariff_bdt_per_kwh")
        total_grid += grid
        total_cost += grid * tariff
        peak_grid = max(peak_grid, grid)
        previous = energy

    if abs(previous - initial) > TOLERANCE:
        raise InfeasibleError("Generated plan does not restore the initial battery energy")

    return round(total_grid, 3), round(total_cost, 3), round(peak_grid, 3)


def _ordered_hours(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(hours, list) or len(hours) != HOURS:
        raise InfeasibleError("Exactly 24 hourly records are required")
    try:
        rows = sorted(hours, key=lambda row: int(row["hour"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InfeasibleError("Hourly records contain an invalid hour") from exc
    if [int(row["hour"]) for row in rows] != list(range(HOURS)):
        raise InfeasibleError("Hourly records must contain hours 0 through 23 exactly once")
    return rows


def _apply_directives(
    directives: list[dict[str, Any]],
    solar: list[float],
    reserve: list[float],
    charge: list[float],
    discharge: list[float],
    grid: list[float],
) -> None:
    for directive in directives or []:
        if not isinstance(directive, dict) or not directive.get("applies"):
            continue
        adjustment = directive.get("structured_adjustment")
        if not isinstance(adjustment, dict):
            continue
        target_hours = [h for h in adjustment.get("hours", []) if isinstance(h, int) and 0 <= h < HOURS]
        kind = directive.get("directive_type")
        if kind == "solar_reduction":
            factor = _safe_number(adjustment.get("factor"))
            if factor is not None and 0 <= factor <= 1:
                for hour in target_hours:
                    solar[hour] *= factor
        elif kind == "minimum_battery_reserve":
            value = _safe_number(adjustment.get("minimum_energy_kwh"))
            if value is not None:
                for hour in target_hours:
                    reserve[hour] = max(reserve[hour], value)
        elif kind == "no_charge_window":
            for hour in target_hours:
                charge[hour] = 0.0
        elif kind == "no_discharge_window":
            for hour in target_hours:
                discharge[hour] = 0.0
        elif kind == "max_grid_window":
            value = _safe_number(adjustment.get("max_grid_kwh"))
            if value is not None:
                for hour in target_hours:
                    grid[hour] = min(grid[hour], value)


def _safe_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _number(mapping: dict[str, Any], key: str) -> float:
    value = _safe_number(mapping.get(key))
    if value is None:
        raise InfeasibleError(f"Missing or invalid battery field: {key}")
    return value


def _row_number(mapping: dict[str, Any], key: str) -> float:
    value = _safe_number(mapping.get(key))
    if value is None:
        raise InfeasibleError(f"Missing or invalid numeric field: {key}")
    return value
