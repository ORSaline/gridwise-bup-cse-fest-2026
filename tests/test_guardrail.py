from app.guardrail import validate


def test_guardrail_repairs_hours_and_coerces_numbers():
    raw = [
        {
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [14, "13", 14, 99], "factor": "0.25"},
        }
    ]
    out = validate(raw, n_notes=1, battery_capacity=100)
    assert out[0]["applies"] is True
    assert out[0]["directive_type"] == "solar_reduction"
    assert out[0]["structured_adjustment"] == {"hours": [13, 14], "factor": 0.25}


def test_guardrail_invalid_reserve_falls_back_to_noop():
    raw = [
        {
            "directive_type": "minimum_battery_reserve",
            "structured_adjustment": {"hours": [1], "minimum_energy_kwh": 120},
        }
    ]
    out = validate(raw, n_notes=1, battery_capacity=100)
    assert out[0]["directive_type"] == "no_op"
    assert out[0]["applies"] is False
    assert out[0]["structured_adjustment"] is None


def test_guardrail_pads_missing_entries():
    out = validate([], n_notes=3, battery_capacity=100)
    assert len(out) == 3
    assert all(row["directive_type"] == "no_op" for row in out)
