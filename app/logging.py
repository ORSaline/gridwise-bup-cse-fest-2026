"""Structured JSON logging for local and hosted execution."""
from __future__ import annotations

import json
import logging
import sys
import time

from app.config import settings


class JsonFormatter(logging.Formatter):
    """Render each log record as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    """Configure the root logger exactly once for stdout JSON logs."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
