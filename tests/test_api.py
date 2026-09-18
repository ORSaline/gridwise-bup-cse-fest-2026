from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def payload():
    return {
        "scenario_id": "api-test",
        "operator_notes": ["Do not charge from 6 PM to 8 PM."],
        "hours": [
            {"hour": h, "demand_kwh": 10.0, "solar_kwh": 0.0, "tariff_bdt_per_kwh": 10.0}
            for h in range(24)
        ],
        "battery": {
            "capacity_kwh": 20.0,
            "initial_energy_kwh": 10.0,
            "minimum_energy_kwh": 0.0,
            "max_charge_kwh_per_hour": 10.0,
            "max_discharge_kwh_per_hour": 10.0,
        },
    }


def test_dashboard_and_health():
    assert client.get("/").status_code == 200
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_malformed_request_returns_400():
    response = client.post("/optimize-energy", json={"scenario_id": "x"})
    assert response.status_code == 400
    assert response.json()["error"] == "malformed_request"


def test_pipeline_uses_exact_response_contract(monkeypatch):
    from app import main
    monkeypatch.setattr(main.llm_module, "interpret_notes", lambda notes, capacity: [{
        "directive_type": "no_charge_window", "structured_adjustment": {"hours": [18, 19]}
    }])
    response = client.post("/optimize-energy", json=payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["hourly_plan"][0]) == {
        "hour", "grid_kwh", "solar_used_kwh", "battery_action", "battery_kwh", "battery_energy_after_kwh"
    }
    assert body["directive_interpretation"][0]["directive_type"] == "no_charge_window"
    assert all(body["hourly_plan"][h]["battery_action"] != "charge" for h in [18, 19])


def test_duplicate_hour_returns_400():
    data = payload()
    data["hours"][23]["hour"] = 22
    assert client.post("/optimize-energy", json=data).status_code == 400
