"""Environment configuration for the GridWise service."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_s: float
    llm_max_retries: int
    llm_stub: bool
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv(
                "LLM_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ).strip(),
            llm_model=os.getenv("LLM_MODEL", "gemini-2.5-flash").strip(),
            llm_timeout_s=float(os.getenv("LLM_TIMEOUT_S", "10")),
            llm_max_retries=max(1, int(os.getenv("LLM_MAX_RETRIES", "2"))),
            llm_stub=_env_bool("LLM_STUB", False),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )


settings = Settings.from_env()
