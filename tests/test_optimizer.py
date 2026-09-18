import json
import math
from pathlib import Path

from app.optimizer import optimize


def hours():
    return [
        {"hour": h, "demand_kwh": 10.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 20.0 if h == 18 else 5.0}
        for h in range(24)
    ]


def battery():
    return {
        "capacity_kwh": 20.0, "initial_energy_kwh": 10.0, "minimum_energy_kwh": 0.0,
        "max_charge_kwh_per_hour": 10.0, "max_discharge_kwh_per_hour": 10.0,
    }


def directive(kind, adjustment, index=0):
    return {"note_index": index, "applies": True, "directive_type": kind, "structured_adjustment": adjustment, "explanation": "test"}


def test_optimizer_shifts_energy_and_restores_battery():
    plan = optimize(hours(), battery(), [])["hourly_plan"]
    assert plan[18]["grid_kwh"] < 10.0
    assert math.isclose(plan[-1]["battery_energy_after_kwh"], 10.0, abs_tol=2e-4)


def test_all_directive_types_are_enforced():
    rows = hours()
    rows[12]["solar_kwh"] = 20.0
    directives = [
        directive("solar_reduction", {"hours": [12], "factor": .25}, 0),
        directive("minimum_battery_reserve", {"hours": [18], "minimum_energy_kwh": 8}, 1),
        directive("no_charge_window", {"hours": [2, 3, 4]}, 2),
        directive("no_discharge_window", {"hours": [19]}, 3),
        directive("max_grid_window", {"hours": [18], "max_grid_kwh": 8}, 4),
    ]
    plan = optimize(rows, battery(), directives)["hourly_plan"]
    assert plan[12]["solar_used_kwh"] <= 5.0002
    assert plan[18]["battery_energy_after_kwh"] >= 7.9998
    assert all(plan[h]["battery_action"] != "charge" for h in [2, 3, 4])
    assert plan[19]["battery_action"] != "discharge"
    assert plan[18]["grid_kwh"] <= 8.0002


def test_all_ten_official_samples_match_optimal_cost():
    pack = json.loads((Path(__file__).parents[1] / "samples" / "official_public_cases.json").read_text(encoding="utf-8"))
    for case in pack["cases"]:
        result = optimize(case["input"]["hours"], case["input"]["battery"], case["expected_output"]["directive_interpretation"])
        assert math.isclose(result["total_cost_bdt"], case["expected_output"]["total_cost_bdt"], abs_tol=.01), case["id"]
