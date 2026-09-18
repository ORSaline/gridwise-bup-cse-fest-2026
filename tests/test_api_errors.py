from fastapi.testclient import TestClient

from app.main import app
from tests.test_api import payload


def test_infeasible_optimizer_returns_422(monkeypatch):
    from app import main
    monkeypatch.setattr(main.llm_module, "interpret_notes", lambda notes, capacity: [{
        "directive_type": "max_grid_window",
        "structured_adjustment": {"hours": list(range(24)), "max_grid_kwh": 1.0},
    }])
    response = TestClient(app).post("/optimize-energy", json=payload())
    assert response.status_code == 422
    assert response.json()["error"] == "infeasible_schedule"


def test_unhandled_error_returns_controlled_500(monkeypatch):
    from app import main
    def fail(*_):
        raise RuntimeError("private stack detail")
    monkeypatch.setattr(main.llm_module, "interpret_notes", fail)
    response = TestClient(app, raise_server_exceptions=False).post("/optimize-energy", json=payload())
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error"}
    assert "private stack detail" not in response.text
