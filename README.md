# GridWise LLM Energy Optimizer

GridWise is a complete BUP CSE Fest 2026 preliminary-round submission: a public FastAPI service, a real LLM interpretation layer, deterministic directive guardrails, a minimum-cost linear-programming optimizer, and an operations dashboard served from the same deployment.

## What is included

- `GET /health` with the exact `{"status":"ok"}` response.
- `POST /optimize-energy` with the canonical request and response field names.
- Batched OpenAI-compatible LLM call for 1-3 operator notes.
- One corrective retry plus a controlled `no_op` fallback on model/provider failure.
- Deterministic validation of note mapping, directive type, hours, numeric ranges, and `applies` semantics.
- SciPy HiGHS LP model covering hourly balance, solar curtailment, battery bounds/rates, directive constraints, and end-of-day neutrality.
- Upload-first browser dashboard at `/`: no scenario or result is preloaded; users upload a request JSON, run it, then receive the dispatch chart, directives, replay checks, schedule, and result download.
- Independent post-solver replay validator that rejects any invalid generated schedule and recalculates every reported total from the final hourly plan.
- Official ten-case pack, offline optimal-cost validation, unit/API tests, Docker image, Render configuration, and GHCR workflow.

## Architecture

```text
Operator notes + battery capacity
           |
           v
OpenAI-compatible LLM (one batched call, temperature 0)
           |
           v
Deterministic guardrail (repair, validate, safe fallback)
           |
           v
SciPy/HiGHS linear program (minimum grid cost)
           |
           v
Replay verification + totals recalculation + exact JSON response
```

The LLM directly creates the structured interpretation used by the optimizer. It is not used only for summaries. The optimizer never trusts raw model output.

## Quick start

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Put a real provider key in `.env`, then run:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/` for the dashboard. The interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Check readiness:

```powershell
curl http://127.0.0.1:8000/health
```

Expected result:

```json
{"status":"ok"}
```

Run the included request through the complete LLM-to-optimizer path:

```powershell
curl.exe -X POST http://127.0.0.1:8000/optimize-energy `
  -H "Content-Type: application/json" `
  --data-binary "@samples/sample_request.json"
```

## Canonical API contract

`POST /optimize-energy` accepts:

- `scenario_id`: non-empty string.
- `operator_notes`: 1-3 non-empty strings.
- `hours`: exactly 24 unique entries for hours 0-23. Each entry contains `hour`, `demand_kwh`, `solar_kwh`, and `tariff_bdt_per_kwh`.
- `battery`: `capacity_kwh`, `initial_energy_kwh`, `minimum_energy_kwh`, `max_charge_kwh_per_hour`, and `max_discharge_kwh_per_hour`.

The response contains:

- `scenario_id` echoed from the request.
- One ordered `directive_interpretation` entry per note.
- Exactly 24 `hourly_plan` entries containing `hour`, `grid_kwh`, `solar_used_kwh`, `battery_action`, `battery_kwh`, and `battery_energy_after_kwh`.
- Recalculated `total_grid_kwh`, `total_cost_bdt`, `peak_grid_kwh`, and `plan_summary`.

HTTP behavior is controlled: malformed/structurally invalid input returns 400, infeasible well-formed scenarios return 422, and unexpected failures return a secret-safe 500.

## Supported directives

| Type | Structured adjustment | Optimizer effect |
|---|---|---|
| `solar_reduction` | `{"hours":[...],"factor":0.25}` | Multiplies available solar. Overlaps multiply. |
| `minimum_battery_reserve` | `{"hours":[...],"minimum_energy_kwh":120}` | Raises the hourly reserve. Overlaps use the maximum. |
| `no_charge_window` | `{"hours":[...]}` | Sets the hourly charge limit to zero. |
| `no_discharge_window` | `{"hours":[...]}` | Sets the hourly discharge limit to zero. |
| `max_grid_window` | `{"hours":[...],"max_grid_kwh":100}` | Caps hourly grid import. Overlaps use the minimum. |
| `no_op` | `null` | Leaves the optimization model unchanged. |

Time windows are start-inclusive and end-exclusive: 1 PM to 3 PM becomes `[13,14]`. Solar factors mean the fraction remaining: an 80% reduction becomes `0.2`. Percentage reserves are converted using the request's battery capacity.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `LLM_API_KEY` | Provider credential | empty |
| `LLM_BASE_URL` | OpenAI-compatible API base URL | Gemini OpenAI-compatible endpoint |
| `LLM_MODEL` | Provider model identifier | `gemini-2.5-flash` |
| `LLM_TIMEOUT_S` | Timeout per LLM attempt | `10` |
| `LLM_MAX_RETRIES` | Total model attempts | `2` |
| `LLM_STUB` | Explicit local no-model fallback | `0` |
| `LOG_LEVEL` | Application log level | `INFO` |

Production judging must use `LLM_STUB=0` with a valid key. When the provider fails or returns invalid data, the service returns controlled `no_op` interpretations rather than crashing; those fallbacks preserve availability but cannot earn interpretation credit for affected notes.

## Verification

Install test dependencies and run the suite:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

Validate the deterministic optimizer against all ten official cases. This route injects the official expected interpretations so it measures directive application, feasibility, replay validity, and optimal cost independently from the provider:

```powershell
python scripts/run_samples.py
```

With the service running and a real LLM configured, validate the complete LLM-to-optimizer pipeline:

```powershell
python scripts/run_samples.py --base-url http://127.0.0.1:8000
```

Run the release and secret-hygiene scan:

```powershell
python scripts/check_release.py
```

## Docker

```powershell
docker build -t gridwise:local .
docker run --rm -p 8000:8000 --env-file .env gridwise:local
```

The image binds to `0.0.0.0:8000`, contains the dashboard, and does not bake in credentials. The included GitHub Actions workflow builds and publishes GHCR images for `main`, commit SHA, and `latest` tags.

## Render deployment

Create a new web service from this repository or use `render.yaml`.

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health path: `/health`
- Add `LLM_API_KEY` as a secret and verify the configured base URL/model.

After deployment, test both endpoints from an external network. The judge endpoint must not require login, VPN, or manual approval.

## Reliability and security

- Pydantic forbids unknown request fields and rejects non-finite or invalid numeric values.
- Raw LLM output is parsed defensively, normalized, and validated before optimization.
- The solver result is independently replayed by `app/replay.py` before it is returned.
- The replayed `hourly_plan` is the source of truth for recalculated grid, cost, and peak totals.
- API keys are read only from environment variables; `.env` is ignored.
- Controlled errors never return stack traces or raw secrets.
- The application logs scenario identifiers and operational status, not credentials.

## Known limitations

- A real model provider and sufficient quota are required for interpretation scoring.
- The safe `no_op` fallback prioritizes service availability, but an applicable note cannot be honored when every LLM attempt fails.
- The optimization model follows the challenge specification's lossless battery accounting; it intentionally does not add efficiency losses, grid export, or demand response.
- The bundled dashboard is an operator/testing surface. The judge uses only `/health` and `/optimize-energy`.

## Repository map

```text
app/          API, LLM interpreter, guardrail, optimizer, replay validator, and dashboard
tests/        unit, schema, API, error, and official-cost tests
samples/      curl-ready request plus the canonical ten-case public pack
scripts/      offline/online sample runner and release checker
.github/      GHCR image workflow
Dockerfile    reproducible fallback container
render.yaml   deployment blueprint
SUBMISSION_INFO.template.md  external-link handoff template
```

Before final submission, add the real deployed base URL, the public-after-deadline repository URL, the exact pullable image tag/digest, and the accessible video link to the organizer form. Those external links cannot be generated by the source package itself. Do not commit any secret value.
