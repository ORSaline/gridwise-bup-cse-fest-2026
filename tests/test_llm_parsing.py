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
