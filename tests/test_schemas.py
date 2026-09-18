import pytest
from pydantic import ValidationError

from app.schemas import OptimizeRequest
from tests.test_api import payload


def test_official_schema_is_accepted():
    request = OptimizeRequest.model_validate(payload())
    assert request.hours[0].solar_kwh == 0


def test_duplicate_hour_and_blank_note_are_rejected():
    data = payload()
    data["hours"][23]["hour"] = 22
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(data)
    data = payload()
    data["operator_notes"] = ["  "]
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(data)


def test_non_spec_fields_are_rejected():
    data = payload()
    data["hours"][0]["grid_cap_kwh"] = 50
    with pytest.raises(ValidationError):
        OptimizeRequest.model_validate(data)
