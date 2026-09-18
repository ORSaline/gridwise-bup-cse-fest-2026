from app.prompts import SYSTEM_PROMPT


def test_prompt_contains_all_directive_types():
    for directive_type in (
        "solar_reduction",
        "minimum_battery_reserve",
        "no_charge_window",
        "no_discharge_window",
        "max_grid_window",
        "no_op",
    ):
        assert directive_type in SYSTEM_PROMPT


def test_prompt_contains_judge_sensitive_time_examples():
    assert '"1 PM to 3 PM" -> [13,14]' in SYSTEM_PROMPT
    assert '"2 PM and 4 PM" -> [14,15]' in SYSTEM_PROMPT
    assert '"after 9 PM" -> [22,23]' in SYSTEM_PROMPT
    assert '"before 6 AM" -> [0,1,2,3,4,5]' in SYSTEM_PROMPT


def test_prompt_contains_remaining_fraction_examples():
    assert '"80% reduction" -> factor 0.2' in SYSTEM_PROMPT
    assert '"one-fifth of forecast" -> factor 0.2' in SYSTEM_PROMPT
    assert '"reduce by a quarter" -> factor 0.75' in SYSTEM_PROMPT
    assert '"cut by 90%" -> factor 0.1' in SYSTEM_PROMPT
