"""FastAPI service and web dashboard for the GridWise optimizer."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import guardrail as guardrail_module
from app import llm as llm_module
from app import optimizer as optimizer_module
from app.errors import register_error_handlers
from app.logging import configure_logging
from app.replay import replay_and_measure
from app.schemas import DirectiveInterpretation, HourlyPlan, OptimizeRequest, OptimizeResponse

configure_logging()
log = logging.getLogger("gridwise")
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title="GridWise",
    version="2.0.0",
    description="LLM-assisted 24-hour campus energy scheduling and optimization.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
register_error_handlers(app)
if WEB_DIR.is_dir():
    app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_summary(scenario_id: str, total_cost: float, total_grid: float, peak_grid: float) -> str:
    return (
        f"{scenario_id}: minimum-cost 24-hour plan uses {total_grid:g} kWh from the grid, "
        f"peaks at {peak_grid:g} kWh, costs {total_cost:g} BDT, and restores the battery "
        "to its initial energy at the end of hour 23."
    )


@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy(req: OptimizeRequest) -> OptimizeResponse:
    log.info("request scenario=%s notes=%d", req.scenario_id, len(req.operator_notes))
    raw = llm_module.interpret_notes(req.operator_notes, req.battery.capacity_kwh)
    directives = guardrail_module.validate(raw, len(req.operator_notes), req.battery.capacity_kwh)
    hours_payload = [row.model_dump() for row in req.hours]
    battery_payload = req.battery.model_dump()
    optimized = optimizer_module.optimize(hours_payload, battery_payload, directives)
    plan = [HourlyPlan(**row) for row in optimized["hourly_plan"]]
    total_grid, total_cost, peak_grid = replay_and_measure(
        hours_payload,
        battery_payload,
        directives,
        [row.model_dump() for row in plan],
    )
    return OptimizeResponse(
        scenario_id=req.scenario_id,
        directive_interpretation=[DirectiveInterpretation(**row) for row in directives],
        hourly_plan=plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=_build_summary(req.scenario_id, total_cost, total_grid, peak_grid),
    )
