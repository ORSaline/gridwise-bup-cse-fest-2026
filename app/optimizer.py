"""Deterministic 24-hour linear-programming optimizer for GridWise."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.optimize import linprog

from app.errors import InfeasibleError

HOURS = 24
G0, S0, C0, D0, E0 = 0, 24, 48, 72, 96
N_VARS = 120
EPS = 1e-8


def optimize(hours: list[dict[str, Any]], battery: dict[str, Any], directives: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a minimum-cost schedule satisfying every validated directive."""
    rows = _normalize_hour_rows(hours)
    limits = _build_effective_limits(rows, battery, directives)
    capacity = _number(battery, "capacity_kwh")
    initial = _number(battery, "initial_energy_kwh")
    minimum = _number(battery, "minimum_energy_kwh")

    if minimum > capacity or initial > capacity or initial + EPS < minimum:
        raise InfeasibleError("Battery energy levels are inconsistent")
    if np.any(limits["reserve"] > capacity + EPS):
        raise InfeasibleError("A reserve directive exceeds battery capacity")

    objective = np.zeros(N_VARS)
    objective[G0:S0] = limits["tariff"]
    a_eq, b_eq = _build_equalities(limits["demand"], initial)
    bounds = _build_bounds(limits, capacity)

    first = linprog(objective, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not first.success:
        raise InfeasibleError(_solver_message(first.message))

    secondary = np.zeros(N_VARS)
    secondary[G0:S0] = 1.0
    secondary[C0:E0] = 1e-3
    cost_tolerance = max(1e-7, abs(float(first.fun)) * 1e-10)
    second = linprog(
        secondary,
        A_ub=np.array([objective]),
        b_ub=np.array([float(first.fun) + cost_tolerance]),
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )
    solution = second.x if second.success else first.x
    plan = _solution_to_plan(solution)
    _verify_plan(plan, limits, capacity, initial)

    total_grid = sum(row["grid_kwh"] for row in plan)
    total_cost = sum(plan[h]["grid_kwh"] * limits["tariff"][h] for h in range(HOURS))
    peak_grid = max(row["grid_kwh"] for row in plan)
    return {
        "hourly_plan": plan,
        "total_grid_kwh": round(total_grid, 6),
        "total_cost_bdt": round(float(total_cost), 6),
        "peak_grid_kwh": round(peak_grid, 6),
    }


def _normalize_hour_rows(hours: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(hours, list) or len(hours) != HOURS:
        raise InfeasibleError("Exactly 24 hourly records are required")
    try:
        ordered = sorted(hours, key=lambda row: int(row["hour"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InfeasibleError("Hourly records contain an invalid hour") from exc
    if [int(row["hour"]) for row in ordered] != list(range(HOURS)):
        raise InfeasibleError("Hourly records must contain hours 0 through 23 exactly once")
    return ordered


def _build_effective_limits(rows: list[dict[str, Any]], battery: dict[str, Any], directives: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    demand = np.array([_row_number(row, "demand_kwh") for row in rows])
    solar = np.array([_row_number(row, "solar_kwh") for row in rows])
    tariff = np.array([_row_number(row, "tariff_bdt_per_kwh") for row in rows])
    if np.any(demand < 0) or np.any(solar < 0) or np.any(tariff < 0):
        raise InfeasibleError("Hourly values must be non-negative")

    reserve = np.full(HOURS, _number(battery, "minimum_energy_kwh"))
    max_charge = np.full(HOURS, _number(battery, "max_charge_kwh_per_hour"))
    max_discharge = np.full(HOURS, _number(battery, "max_discharge_kwh_per_hour"))
    grid_cap = np.full(HOURS, np.inf)

    for directive in directives or []:
        if not isinstance(directive, dict) or not directive.get("applies"):
            continue
        adjustment = directive.get("structured_adjustment")
        if not isinstance(adjustment, dict):
            continue
        target_hours = [h for h in adjustment.get("hours", []) if isinstance(h, int) and 0 <= h <= 23]
        dtype = directive.get("directive_type")
        if dtype == "solar_reduction":
            factor = _safe_float(adjustment.get("factor"))
            if factor is not None and 0 <= factor <= 1:
                for h in target_hours:
                    solar[h] *= factor
        elif dtype == "minimum_battery_reserve":
            value = _safe_float(adjustment.get("minimum_energy_kwh"))
            if value is not None and value >= 0:
                for h in target_hours:
                    reserve[h] = max(reserve[h], value)
        elif dtype == "no_charge_window":
            for h in target_hours:
                max_charge[h] = 0.0
        elif dtype == "no_discharge_window":
            for h in target_hours:
                max_discharge[h] = 0.0
        elif dtype == "max_grid_window":
            value = _safe_float(adjustment.get("max_grid_kwh"))
            if value is not None and value >= 0:
                for h in target_hours:
                    grid_cap[h] = min(grid_cap[h], value)

    return {
        "demand": demand,
        "solar": solar,
        "tariff": tariff,
        "grid_cap": grid_cap,
        "reserve": reserve,
        "max_charge": max_charge,
        "max_discharge": max_discharge,
    }


def _build_equalities(demand: np.ndarray, initial: float) -> tuple[np.ndarray, np.ndarray]:
    rows: list[np.ndarray] = []
    values: list[float] = []
    for h in range(HOURS):
        row = np.zeros(N_VARS)
        row[G0 + h], row[S0 + h], row[C0 + h], row[D0 + h] = 1, 1, -1, 1
        rows.append(row)
        values.append(float(demand[h]))
    for h in range(HOURS):
        row = np.zeros(N_VARS)
        row[E0 + h], row[C0 + h], row[D0 + h] = 1, -1, 1
        if h == 0:
            values.append(initial)
        else:
            row[E0 + h - 1] = -1
            values.append(0.0)
        rows.append(row)
    row = np.zeros(N_VARS)
    row[E0 + HOURS - 1] = 1
    rows.append(row)
    values.append(initial)
    return np.array(rows), np.array(values)


def _build_bounds(limits: dict[str, np.ndarray], capacity: float) -> list[tuple[float, float | None]]:
    bounds: list[tuple[float, float | None]] = []
    bounds.extend((0.0, None if math.isinf(limits["grid_cap"][h]) else float(limits["grid_cap"][h])) for h in range(HOURS))
    bounds.extend((0.0, float(limits["solar"][h])) for h in range(HOURS))
    bounds.extend((0.0, float(limits["max_charge"][h])) for h in range(HOURS))
    bounds.extend((0.0, float(limits["max_discharge"][h])) for h in range(HOURS))
    bounds.extend((float(limits["reserve"][h]), capacity) for h in range(HOURS))
    return bounds


def _solution_to_plan(solution: np.ndarray) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for h in range(HOURS):
        grid = _clean(solution[G0 + h])
        solar = _clean(solution[S0 + h])
        net = _clean(solution[C0 + h] - solution[D0 + h])
        energy = _clean(solution[E0 + h])
        if net > 1e-7:
            action, amount = "charge", net
        elif net < -1e-7:
            action, amount = "discharge", -net
        else:
            action, amount = "idle", 0.0
        plan.append({
            "hour": h,
            "grid_kwh": round(grid, 6),
            "solar_used_kwh": round(solar, 6),
            "battery_action": action,
            "battery_kwh": round(amount, 6),
            "battery_energy_after_kwh": round(energy, 6),
        })
    return plan


def _verify_plan(plan: list[dict[str, Any]], limits: dict[str, np.ndarray], capacity: float, initial: float) -> None:
    tolerance = 2e-4
    previous = initial
    for h, row in enumerate(plan):
        action = row["battery_action"]
        amount = row["battery_kwh"]
        charge = amount if action == "charge" else 0.0
        discharge = amount if action == "discharge" else 0.0
        energy = row["battery_energy_after_kwh"]
        if abs(row["grid_kwh"] + row["solar_used_kwh"] + discharge - charge - limits["demand"][h]) > tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: energy balance")
        if row["grid_kwh"] < -tolerance or row["grid_kwh"] > limits["grid_cap"][h] + tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: grid cap")
        if row["solar_used_kwh"] < -tolerance or row["solar_used_kwh"] > limits["solar"][h] + tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: solar limit")
        if charge > limits["max_charge"][h] + tolerance or discharge > limits["max_discharge"][h] + tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: battery rate")
        if energy < limits["reserve"][h] - tolerance or energy > capacity + tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: battery bounds")
        if abs(energy - (previous + charge - discharge)) > tolerance:
            raise InfeasibleError(f"Internal verification failed at hour {h}: battery state")
        previous = energy
    if abs(previous - initial) > tolerance:
        raise InfeasibleError("Internal verification failed: end-of-day battery neutrality")


def _number(mapping: dict[str, Any], key: str) -> float:
    value = _safe_float(mapping.get(key))
    if value is None:
        raise InfeasibleError(f"Missing or invalid battery field: {key}")
    return value


def _row_number(mapping: dict[str, Any], key: str) -> float:
    value = _safe_float(mapping.get(key))
    if value is None:
        raise InfeasibleError(f"Missing or invalid hourly field: {key}")
    return value


def _safe_float(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _clean(value: float) -> float:
    value = float(value)
    return 0.0 if abs(value) < 1e-8 else value


def _solver_message(message: str) -> str:
    clean = " ".join(str(message).split())
    return clean[:300] if clean else "No feasible schedule exists"
