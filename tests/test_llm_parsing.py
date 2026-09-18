from types import SimpleNamespace

import app.llm as llm
from app.llm import _extract_json_array, _normalize


def test_extract_json_array_from_fence():
    raw = '''```json
    [{"directive_type":"no_op","structured_adjustment":null}]
    ```'''
    parsed = _extract_json_array(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["directive_type"] == "no_op"


def test_normalize_preserves_length_and_allowed_type():
    parsed = [
        {
            "directive_type": "solar_reduction",
            "structured_adjustment": {"hours": [14, 13, 13], "factor": "0.2"},
        }
    ]
    out = _normalize(parsed, expected_len=2)
    assert len(out) == 2
    assert out[0]["structured_adjustment"]["hours"] == [13, 14]
    assert out[0]["structured_adjustment"]["factor"] == 0.2
    assert out[1]["directive_type"] == "no_op"


def test_semantic_validation_rejects_out_of_range_factor():
    from app.llm import _semantically_valid

    assert not _semantically_valid(
        [
            {
                "directive_type": "solar_reduction",
                "structured_adjustment": {"hours": [13, 14], "factor": 1.5},
            }
        ]
    )


def test_native_gemini_request_and_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '[{"directive_type":"no_op",'},
                                {"text": '"structured_adjustment":null}]'},
                            ]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, headers, json):
            captured.update(url=url, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setattr(
        llm,
        "settings",
        SimpleNamespace(
            llm_base_url="https://generativelanguage.googleapis.com/v1beta/",
            llm_model="gemini-3.1-flash-lite",
            llm_api_key="test-key",
            llm_timeout_s=10,
        ),
    )
    monkeypatch.setattr(llm.httpx, "Client", FakeClient)

    result = llm._call_llm("Interpret this note")

    assert result == '[{"directive_type":"no_op","structured_adjustment":null}]'
    assert captured["url"].endswith(
        "/models/gemini-3.1-flash-lite:generateContent"
    )
    assert captured["headers"]["X-goog-api-key"] == "test-key"
    assert "Authorization" not in captured["headers"]
    assert captured["payload"]["systemInstruction"]["parts"][0]["text"]
    assert captured["payload"]["contents"][0]["parts"][0]["text"] == (
        "Interpret this note"
    )
    assert captured["payload"]["generationConfig"] == {
        "temperature": 0,
        "maxOutputTokens": 1200,
        "responseMimeType": "application/json",
    }


def test_native_gemini_rejects_empty_candidates(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": []}

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, headers, json):
            return FakeResponse()

    monkeypatch.setattr(llm.httpx, "Client", FakeClient)

    import pytest

    with pytest.raises(ValueError, match="no candidates"):
        llm._call_llm("Interpret this note")
