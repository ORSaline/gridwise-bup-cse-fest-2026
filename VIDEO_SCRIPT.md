# GridWise 3-Minute Demo Script

## 0:00-0:25 - Problem

GridWise receives a 24-hour energy scenario containing demand, solar forecast, grid tariff, grid limits, battery specifications, and one to three natural-language operator notes. The goal is to return the cheapest valid schedule while proving that the natural-language notes are interpreted by an LLM and enforced by deterministic optimization logic.

## 0:25-0:55 - Architecture

The service uses three layers. First, the LLM converts each note into one of six allowed directive types. Second, a deterministic guardrail validates hours, numbers, directive shapes, and battery-capacity limits. Third, a SciPy HiGHS linear program finds the minimum-cost schedule while enforcing energy balance, battery limits, grid caps, solar limits, and end-of-day neutrality.

## 0:55-1:25 - LLM interpretation

Show `app/prompts.py` and `app/llm.py`. Point out that all notes are sent in one LLM call, temperature is zero, time windows are start-inclusive and end-exclusive, solar factors are remaining fractions, JSON parsing is defensive, and failures fall back safely instead of crashing the API.

## 1:25-1:55 - Guardrail and optimizer

Show `app/guardrail.py`, then `app/optimizer.py`. Demonstrate that invalid hours or numeric values are rejected to `no_op`, while valid directives modify the optimizer arrays. Explain the overlap rules: multiply solar factors, take the maximum reserve, take the minimum grid cap, and union no-charge or no-discharge windows.

## 1:55-2:25 - API demo

Call `GET /health` and show the exact `{"status":"ok"}` response. Then call `POST /optimize-energy` with a sample request. Show `directive_interpretation`, the 24 hourly rows, and the recalculated totals.

## 2:25-2:50 - Reliability

Run `pytest -q`. Mention the controlled HTTP status codes: 400 for malformed requests, 422 for infeasible schedules, and sanitized 500 responses for unexpected failures. Show that the Dockerfile runs as a non-root user and binds to `0.0.0.0`.

## 2:50-3:00 - Close

End with the public Render URL, the GitHub repository, and the pullable GHCR image. State that the LLM performs interpretation, while all safety checks and optimization are deterministic and reproducible.
