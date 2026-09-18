"""Deterministic validation and repair of LLM-produced directives."""
from __future__ import annotations

import logging
import math
from typing import Any

log = logging.getLogger("gridwise.guardrail")

ALLOWED_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


def validate(raw: list[dict[str, Any]], n_notes: int, battery_capacity: float) -> list[dict[str, Any]]:
    """Return exactly one safe interpretation entry for each operator note."""
    source = raw if isinstance(raw, list) else []
    output: list[dict[str, Any]] = []

    for note_index in range(n_notes):
        item = source[note_index] if note_index < len(source) else None
        validated = _validate_one(item, note_index, battery_capacity)
        output.append(validated)

    return output


def _validate_one(item: Any, note_index: int, battery_capacity: float) -> dict[str, Any]:
    if not isinstance(item, dict):
        return _fallback(note_index, "Missing or malformed LLM directive")

    dtype = item.get("directive_type")
    if dtype not in ALLOWED_TYPES:
        return _fallback(note_index, "Unsupported directive type")

    if dtype == "no_op":
        return {
            "note_index": note_index,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None,
            "explanation": "The note does not create a scheduling constraint.",
        }

    adjustment = item.get("structured_adjustment")
    if not isinstance(adjustment, dict):
        return _fallback(note_index, f"{dtype} has no valid structured adjustment")

    hours = _normalize_hours(adjustment.get("hours"))
    if not hours:
        return _fallback(note_index, f"{dtype} has no valid hours")

    if dtype == "solar_reduction":
        factor = _finite_number(adjustment.get("factor"))
        if factor is None or not 0 <= factor <= 1:
            return _fallback(note_index, "solar_reduction factor must be between 0 and 1")
        clean = {"hours": hours, "factor": factor}
        explanation = f"Solar availability is multiplied by {factor:g} during the specified hours."

    elif dtype == "minimum_battery_reserve":
        reserve = _finite_number(adjustment.get("minimum_energy_kwh"))
        if reserve is None or reserve < 0 or reserve > battery_capacity:
            return _fallback(
                note_index,
                "minimum_battery_reserve must be between 0 and battery capacity",
            )
        clean = {"hours": hours, "minimum_energy_kwh": reserve}
        explanation = f"Battery energy must stay at or above {reserve:g} kWh during the specified hours."

    elif dtype == "no_charge_window":
        clean = {"hours": hours}
        explanation = "Battery charging is disabled during the specified hours."

    elif dtype == "no_discharge_window":
        clean = {"hours": hours}
        explanation = "Battery discharging is disabled during the specified hours."

    elif dtype == "max_grid_window":
        maximum = _finite_number(adjustment.get("max_grid_kwh"))
        if maximum is None or maximum < 0:
            return _fallback(note_index, "max_grid_window limit must be non-negative")
        clean = {"hours": hours, "max_grid_kwh": maximum}
        explanation = f"Grid import is capped at {maximum:g} kWh during the specified hours."

    else:
        return _fallback(note_index, "Directive validation failed")

    return {
        "note_index": note_index,
        "applies": True,
        "directive_type": dtype,
        "structured_adjustment": clean,
        "explanation": explanation,
    }


def _normalize_hours(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    values: set[int] = set()
    for item in raw:
        if isinstance(item, bool):
            continue
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number) or not number.is_integer():
            continue
        hour = int(number)
        if 0 <= hour <= 23:
            values.add(hour)
    return sorted(values)


def _finite_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _fallback(note_index: int, reason: str) -> dict[str, Any]:
    log.warning("directive_fallback note_index=%d reason=%s", note_index, reason)
    return {
        "note_index": note_index,
        "applies": False,
        "directive_type": "no_op",
        "structured_adjustment": None,
        "explanation": f"Invalid directive was safely replaced with no_op: {reason}.",
    }
