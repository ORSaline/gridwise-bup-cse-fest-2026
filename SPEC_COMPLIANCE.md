# GridWise Specification Compliance Map

This document maps the supplied GridWise requirements to the implementation and local verification points.

## 1. LLM directive interpretation

- Production interpretation uses an OpenAI-compatible LLM call in `app/llm.py`.
- All operator notes are sent in one batch call.
- Only the six allowed directive types are accepted.
- Time windows are start-inclusive and end-exclusive.
- Solar-reduction factors represent the remaining fraction.
- Malformed model output is parsed defensively, retried, and finally replaced with controlled `no_op` entries rather than crashing.
- The returned raw list always has exactly one entry per input note, in the original order.
- Battery capacity is included in the LLM context so percentage-based reserve notes are converted to kWh.

Verification: `tests/test_llm_parsing.py`, `tests/test_prompt_contract.py`.

## 2. Deterministic guardrail

- `app/guardrail.py` validates directive types, hours, factor range, reserve range, grid caps, and numeric finiteness.
- Hours are converted to unique ascending integers from 0 through 23.
- `no_op` always becomes `applies=false` with a null adjustment.
- Valid non-`no_op` directives always become `applies=true`.
- Invalid directives become controlled `no_op` entries with an explanation.

Verification: `tests/test_guardrail.py`.

## 3. Optimization

- `app/optimizer.py` uses `scipy.optimize.linprog(method="highs")`.
- The primary objective minimizes total grid cost over 24 hours.
- Energy balance is enforced every hour.
- Solar use cannot exceed effective solar availability.
- Grid import is unbounded by default and is capped only by validated `max_grid_window` directives.
- Battery charge/discharge rates are enforced.
- Battery energy remains between the effective reserve and capacity.
- End-of-day battery energy equals the initial battery energy.
- Overlapping solar reductions multiply.
- Overlapping reserves use the maximum.
- Overlapping grid caps use the minimum.
- Charge/discharge prohibition windows form unions.
- The returned plan is verified inside the optimizer and then independently replayed by `app/replay.py` before the API responds.

Verification: `tests/test_optimizer.py`, `tests/test_replay.py`, including all ten official optimal reference costs and deliberate plan-tampering tests.

## 4. Public API contract

- `GET /health` returns exactly `{"status":"ok"}`.
- `POST /optimize-energy` uses the fixed request/response field names.
- Exactly 24 unique hours numbered 0 through 23 are required.
- Malformed requests return HTTP 400.
- Infeasible schedules return HTTP 422.
- Unexpected failures return a controlled HTTP 500 body without a stack trace.
- Reported grid, cost, and peak totals are recalculated from the returned hourly plan.

Verification: `tests/test_api.py`, `tests/test_api_errors.py`, `tests/test_schemas.py`.

## 5. Deployment and reliability

- `Dockerfile` binds the service to `0.0.0.0:8000` and does not bake secrets into the image.
- `.env.example` documents runtime variables without real credentials.
- `render.yaml` contains a Render web-service definition.
- `.github/workflows/docker.yml` builds and publishes the container to GHCR from `main`.
- Logging uses JSON lines for hosted environments.

## 6. Local sample replay

`scripts/run_samples.py` reads the bundled official ten-case pack. By default it injects the organizer interpretations directly into the deterministic optimizer; with `--base-url`, it tests the complete deployed LLM pipeline. It checks:

- 24 hourly plan rows;
- one interpretation entry per note in order;
- hourly energy balance;
- effective solar limits;
- effective grid caps;
- charge/discharge rate limits;
- battery reserve and capacity;
- battery state progression;
- end-of-day neutrality;
- total grid, total cost, and peak-grid consistency;
- reference total cost when an `expected_output.total_cost_bdt` value is present.

The exact organizer-provided case pack is included at `samples/official_public_cases.json`. A single curl-ready request is included at `samples/sample_request.json`; the upload-first dashboard intentionally preloads no scenario or result.
