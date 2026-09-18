"""Custom exceptions and FastAPI error handlers."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("gridwise")


class InfeasibleError(Exception):
    """Raised when no feasible energy schedule exists."""


def register_error_handlers(app: FastAPI) -> None:
    """Register controlled API error responses."""

    @app.exception_handler(InfeasibleError)
    async def _infeasible(_: Request, exc: InfeasibleError) -> JSONResponse:
        log.warning("infeasible_schedule: %s", exc)
        return JSONResponse(
            status_code=422,
            content={"error": "infeasible_schedule", "detail": str(exc)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=jsonable_encoder({"error": "malformed_request", "detail": exc.errors()}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error"},
        )
