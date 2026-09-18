import copy

import pytest

from app.errors import InfeasibleError
from app.optimizer import optimize
from app.replay import replay_and_measure


def _hours():
    return [
        {"hour": hour, "demand_kwh": 10.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 5.0 + hour}
        for hour in range(24)
    ]


def _battery():
    return {
        "capacity_kwh": 20.0,
        "initial_energy_kwh": 10.0,
        "minimum_energy_kwh": 0.0,
        "max_charge_kwh_per_hour": 10.0,
        "max_discharge_kwh_per_hour": 10.0,
    }


def test_replay_accepts_optimizer_plan_and_recalculates_totals():
    hours = _hours()
    battery = _battery()
    result = optimize(hours, battery, [])
    total_grid, total_cost, peak_grid = replay_and_measure(hours, battery, [], result["hourly_plan"])
    assert total_grid == pytest.approx(result["total_grid_kwh"], abs=0.001)
    assert total_cost == pytest.approx(result["total_cost_bdt"], abs=0.001)
    assert peak_grid == pytest.approx(result["peak_grid_kwh"], abs=0.001)


def test_replay_rejects_tampered_energy_balance():
    hours = _hours()
    battery = _battery()
    plan = copy.deepcopy(optimize(hours, battery, [])["hourly_plan"])
    plan[8]["grid_kwh"] += 1
    with pytest.raises(InfeasibleError, match="Energy balance"):
        replay_and_measure(hours, battery, [], plan)


def test_replay_rejects_tampered_final_battery_state():
    hours = _hours()
    battery = _battery()
    plan = copy.deepcopy(optimize(hours, battery, [])["hourly_plan"])
    plan[23]["battery_energy_after_kwh"] -= 1
    with pytest.raises(InfeasibleError, match="Battery state transition|restore"):
        replay_and_measure(hours, battery, [], plan)
