"""Validate the official ten-case pack offline or against a running API."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.optimizer import _build_effective_limits, _normalize_hour_rows, optimize


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", help="Validate a running service instead of the offline optimizer")
    parser.add_argument("--pack", default="samples/official_public_cases.json")
    args = parser.parse_args()
    pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    failures = 0

    for case in pack["cases"]:
        try:
            request = case["input"]
            expected = case["expected_output"]
            if args.base_url:
                response = httpx.post(
                    args.base_url.rstrip("/") + "/optimize-energy",
                    json=request,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                _compare_directives(result["directive_interpretation"], expected["directive_interpretation"])
            else:
                result = optimize(request["hours"], request["battery"], expected["directive_interpretation"])
                result["directive_interpretation"] = expected["directive_interpretation"]
            _validate_response(request, result)
            if not math.isclose(float(result["total_cost_bdt"]), float(expected["total_cost_bdt"]), abs_tol=.01):
                raise AssertionError(f"cost {result['total_cost_bdt']} != {expected['total_cost_bdt']}")
            print(f"PASS {case['id']} | cost={float(result['total_cost_bdt']):.2f} BDT")
        except Exception as exc:
            failures += 1
            print(f"FAIL {case['id']} | {exc}")

    print(f"\nOfficial samples: {len(pack['cases']) - failures}/{len(pack['cases'])} passed")
    return 1 if failures else 0


def _compare_directives(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> None:
    if len(actual) != len(expected):
        raise AssertionError("interpretation count mismatch")
    for index, (got, want) in enumerate(zip(actual, expected)):
        for key in ("note_index", "applies", "directive_type", "structured_adjustment"):
            if got.get(key) != want.get(key):
                raise AssertionError(f"note {index} {key} mismatch: {got.get(key)!r} != {want.get(key)!r}")


def _validate_response(request: dict[str, Any], result: dict[str, Any]) -> None:
    plan = result["hourly_plan"]
    directives = result["directive_interpretation"]
    if len(plan) != 24 or [row["hour"] for row in plan] != list(range(24)):
        raise AssertionError("hourly_plan must contain ordered hours 0..23")
    rows = _normalize_hour_rows(request["hours"])
    limits = _build_effective_limits(rows, request["battery"], directives)
    battery = request["battery"]
    previous = float(battery["initial_energy_kwh"])
    capacity = float(battery["capacity_kwh"])
    tolerance = .001

    for hour, row in enumerate(plan):
        amount = float(row["battery_kwh"])
        action = row["battery_action"]
        charge = amount if action == "charge" else 0.0
        discharge = amount if action == "discharge" else 0.0
        if action == "idle" and abs(amount) > tolerance:
            raise AssertionError(f"idle battery amount at hour {hour}")
        grid = float(row["grid_kwh"])
        solar = float(row["solar_used_kwh"])
        energy = float(row["battery_energy_after_kwh"])
        if abs(grid + solar + discharge - charge - limits["demand"][hour]) > tolerance:
            raise AssertionError(f"energy balance at hour {hour}")
        if solar > limits["solar"][hour] + tolerance or grid > limits["grid_cap"][hour] + tolerance:
            raise AssertionError(f"source limit at hour {hour}")
        if charge > limits["max_charge"][hour] + tolerance or discharge > limits["max_discharge"][hour] + tolerance:
            raise AssertionError(f"battery rate at hour {hour}")
        if not limits["reserve"][hour] - tolerance <= energy <= capacity + tolerance:
            raise AssertionError(f"battery bounds at hour {hour}")
        if abs(energy - (previous + charge - discharge)) > tolerance:
            raise AssertionError(f"battery transition at hour {hour}")
        previous = energy
    if abs(previous - float(battery["initial_energy_kwh"])) > tolerance:
        raise AssertionError("end-of-day neutrality")


if __name__ == "__main__":
    raise SystemExit(main())
