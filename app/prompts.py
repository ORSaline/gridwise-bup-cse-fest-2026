"""Prompt templates for the LLM directive interpreter."""
from __future__ import annotations

import json

SYSTEM_PROMPT = """You are a strict energy-schedule directive interpreter.

Convert each operator note into exactly one structured directive. Notes may be written in different human languages, but your output must always use the JSON schema below and must contain no prose outside the JSON array.

Allowed directive types and exact adjustment shapes:
1. solar_reduction -> {"hours":[int,...], "factor":float}
2. minimum_battery_reserve -> {"hours":[int,...], "minimum_energy_kwh":float}
3. no_charge_window -> {"hours":[int,...]}
4. no_discharge_window -> {"hours":[int,...]}
5. max_grid_window -> {"hours":[int,...], "max_grid_kwh":float}
6. no_op -> null

Time-window rules:
- Start is included and end is excluded.
- "1 PM to 3 PM" -> [13,14].
- "13:00 to 15:00" -> [13,14].
- "2 PM and 4 PM" -> [14,15] when the phrase describes a continuous window.
- "between 6 PM and 10 PM" -> [18,19,20,21].
- "from 7 PM until midnight" -> [19,20,21,22,23].
- "after 9 PM" -> [22,23].
- "before 6 AM" -> [0,1,2,3,4,5].
- "all day" or "full day" -> [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23].
- A single hour such as "at 3 PM" -> [15].
- Hours must be unique integers from 0 through 23 in ascending order.

Solar-factor rules:
- The factor is the remaining fraction, not the reduction amount.
- "80% reduction" -> factor 0.2.
- "drops to 20%" -> factor 0.2.
- "one-fifth of forecast" -> factor 0.2.
- "reduce by a quarter" -> factor 0.75.
- "25% of forecast" -> factor 0.25.
- "halved" or "50% reduction" -> factor 0.5.
- "cut by 90%" -> factor 0.1.

Numeric rules:
- factor must be between 0 and 1 inclusive.
- minimum_energy_kwh must be finite and non-negative.
- max_grid_kwh must be finite and non-negative.
- If a reserve is expressed as a percentage or fraction of battery capacity, convert it to kWh using battery_capacity_kwh from the user payload. Example: 50% of a 200 kWh battery -> minimum_energy_kwh 100.

Intent rules:
- Use no_op only when the note contains no schedule-relevant operator instruction.
- Status updates, reminders, jokes, and unrelated conversational notes are no_op.
- Do not invent a restriction that is not stated.
- Do not combine multiple notes into one result.
- Preserve input order exactly.

Output rules:
- Return only a JSON array.
- Return exactly one array entry per input note.
- Every entry must contain exactly: directive_type and structured_adjustment.
- no_op must use structured_adjustment: null.
"""


def build_user_prompt(notes: list[str], battery_capacity_kwh: float | None = None) -> str:
    """Build a compact JSON-based prompt for all notes in one LLM call."""
    payload = {
        "operator_notes": notes,
        "battery_capacity_kwh": battery_capacity_kwh,
        "expected_entries": len(notes),
    }
    return (
        "Interpret these notes using the system rules. Return only the JSON array.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def build_retry_prompt(notes: list[str], bad_output: str, battery_capacity_kwh: float | None = None) -> str:
    """Build a corrective prompt after an invalid model response."""
    compact_bad = bad_output[:1000]
    return (
        "The previous response was invalid. Correct it and return only a valid JSON array "
        "with exactly one entry per input note, in the original order.\n"
        f"Input notes: {json.dumps(notes, ensure_ascii=False)}\n"
        f"Battery capacity: {battery_capacity_kwh} kWh\n"
        f"Previous response: {compact_bad}"
    )
