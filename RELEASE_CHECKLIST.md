# Release Checklist

Run these checks before submission.

- [ ] `python -m pytest -q` passes.
- [ ] Start the API with a real LLM key and `LLM_STUB=0`.
- [ ] `GET /health` returns exactly `{"status":"ok"}`.
- [ ] A real operator-note request produces one interpretation per note.
- [ ] Run all official public sample cases offline with `python scripts/run_samples.py`.
- [ ] Run the complete live LLM path with `python scripts/run_samples.py --base-url <URL>`.
- [ ] Confirm every schedule passes balance, battery, solar, grid, rate, and neutrality checks.
- [ ] Confirm totals recalculate from `hourly_plan`.
- [ ] Confirm malformed requests return 400.
- [ ] Confirm an infeasible schedule returns 422.
- [ ] Confirm unexpected server errors return only the controlled 500 body.
- [ ] Build the Docker image locally.
- [ ] Run the Docker image and test `/health` from the host.
- [ ] Confirm no API key is present in tracked files or Git history.
- [ ] Deploy and test from an external network.
- [ ] Open `/` and verify the dashboard loads, sample preview renders, and a live request completes.
- [ ] Confirm the container image is pullable from GHCR.
- [ ] Keep the contest repository private during the event and change visibility only when the event rules permit it.
