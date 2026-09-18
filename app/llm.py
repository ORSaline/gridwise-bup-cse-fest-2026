"""LLM-backed interpretation of operator notes into structured directives."""
from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

import httpx

from app.config import settings
from app.prompts import SYSTEM_PROMPT, build_retry_prompt, build_user_prompt

log = logging.getLogger("gridwise.llm")

VALID_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}
_FENCE_RE = re.compile(r"```(?:json)?\s*|```", re.IGNORECASE)


def interpret_notes(notes: list[str], battery_capacity_kwh: float | None = None) -> list[dict[str, Any]]:
    """Interpret all notes in one LLM call, with controlled retries and fallback."""
    if not notes:
        return []

    if settings.llm_stub:
        log.info("LLM_STUB is enabled; returning controlled no_op directives")
        return _noop_response(len(notes))

    if not settings.llm_api_key:
        log.error("LLM_API_KEY is missing; returning controlled no_op directives")
        return _noop_response(len(notes))

    previous_output = ""
    for attempt in range(settings.llm_max_retries):
        try:
            user_prompt = (
                build_user_prompt(notes, battery_capacity_kwh)
                if attempt == 0
                else build_retry_prompt(notes, previous_output, battery_capacity_kwh)
            )
            raw = _call_llm(user_prompt)
            previous_output = raw
            parsed = _extract_json_array(raw)
            if parsed is None:
                log.warning("LLM attempt %d returned invalid JSON", attempt + 1)
                continue
            normalized = _normalize(parsed, expected_len=len(notes))
            if _semantically_valid(normalized):
                return normalized
            log.warning("LLM attempt %d returned semantically invalid directives", attempt + 1)
        except httpx.TimeoutException:
            log.warning("LLM attempt %d timed out", attempt + 1)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            log.warning("LLM attempt %d returned HTTP status %s", attempt + 1, status)
        except httpx.HTTPError as exc:
            log.warning("LLM attempt %d failed with HTTP error: %s", attempt + 1, exc)
        except Exception as exc:
            log.exception("LLM attempt %d failed unexpectedly: %s", attempt + 1, exc)

    log.error("LLM interpretation failed; using controlled no_op fallback")
    return _noop_response(len(notes))



def _semantically_valid(items: list[dict[str, Any]]) -> bool:
    """Check semantic ranges that can be validated without scenario-specific data."""
    for item in items:
        dtype = item.get("directive_type")
        if dtype == "no_op":
            if item.get("structured_adjustment") is not None:
                return False
            continue
        adjustment = item.get("structured_adjustment")
        if not isinstance(adjustment, dict):
            return False
        hours = adjustment.get("hours")
        if not isinstance(hours, list) or not hours:
            return False
        if any(not isinstance(h, int) or h < 0 or h > 23 for h in hours):
            return False
        if hours != sorted(set(hours)):
            return False
        if dtype == "solar_reduction":
            factor = adjustment.get("factor")
            if factor is None or not 0 <= factor <= 1:
                return False
        elif dtype == "minimum_battery_reserve":
            value = adjustment.get("minimum_energy_kwh")
            if value is None or value < 0:
                return False
        elif dtype == "max_grid_window":
            value = adjustment.get("max_grid_kwh")
            if value is None or value < 0:
                return False
    return True

def _call_llm(user_prompt: str) -> str:
    """Make one native Gemini generateContent request."""
    url = (
        settings.llm_base_url.rstrip("/")
        + f"/models/{settings.llm_model}:generateContent"
    )
    headers = {
        "X-goog-api-key": settings.llm_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            },
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
        },
    }

    timeout = httpx.Timeout(settings.llm_timeout_s)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    candidates = data.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response contains no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not isinstance(parts, list):
        raise ValueError("Gemini response parts are malformed")
    content = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text", ""), str)
    ).strip()
    if not content:
        raise ValueError("Gemini response contains no text")
    return content


def _extract_json_array(text: str) -> list[Any] | None:
    """Extract a top-level JSON array from clean or fenced model output."""
    if not text:
        return None
    cleaned = _FENCE_RE.sub("", text).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("result", "directives", "items"):
                candidate = parsed.get(key)
                if isinstance(candidate, list):
                    return candidate
    except json.JSONDecodeError:
        pass

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def _normalize(parsed: list[Any], expected_len: int) -> list[dict[str, Any]]:
    """Normalize model output into exactly the interface contract shape."""
    out: list[dict[str, Any]] = []
    for index in range(expected_len):
        if index >= len(parsed) or not isinstance(parsed[index], dict):
            out.append(_noop_item())
            continue

        item = parsed[index]
        dtype = item.get("directive_type")
        if dtype not in VALID_TYPES:
            out.append(_noop_item())
            continue

        if dtype == "no_op":
            out.append(_noop_item())
            continue

        adjustment = item.get("structured_adjustment")
        if not isinstance(adjustment, dict):
            out.append({"directive_type": dtype, "structured_adjustment": None})
            continue

        out.append(
            {
                "directive_type": dtype,
                "structured_adjustment": _light_sanitize(dtype, adjustment),
            }
        )
    return out


def _light_sanitize(dtype: str, adjustment: dict[str, Any]) -> dict[str, Any]:
    """Perform only safe shape normalization; strict checks belong to guardrail.py."""
    result: dict[str, Any] = {"hours": _coerce_hours(adjustment.get("hours"))}
    if dtype == "solar_reduction":
        result["factor"] = _coerce_number(adjustment.get("factor"))
    elif dtype == "minimum_battery_reserve":
        result["minimum_energy_kwh"] = _coerce_number(
            adjustment.get("minimum_energy_kwh")
        )
    elif dtype == "max_grid_window":
        result["max_grid_kwh"] = _coerce_number(adjustment.get("max_grid_kwh"))
    return result


def _coerce_hours(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    values: set[int] = set()
    for item in raw:
        if isinstance(item, bool):
            continue
        try:
            value = float(item)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or not value.is_integer():
            continue
        integer = int(value)
        if 0 <= integer <= 23:
            values.add(integer)
    return sorted(values)


def _coerce_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _noop_item() -> dict[str, Any]:
    return {"directive_type": "no_op", "structured_adjustment": None}


def _noop_response(n: int) -> list[dict[str, Any]]:
    return [_noop_item() for _ in range(n)]
