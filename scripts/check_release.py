"""Static release and secret-hygiene checks."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "app/main.py", "app/schemas.py", "app/llm.py", "app/prompts.py", "app/guardrail.py",
    "app/optimizer.py", "app/web/index.html", "app/web/styles.css", "app/web/app.js",
    "samples/official_public_cases.json", "requirements.txt", "Dockerfile", ".env.example",
    ".gitignore", ".github/workflows/docker.yml", "README.md",
]
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".example", ".html", ".css", ".js"}
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-[0-9A-Za-z]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[=:]\s*['\"][A-Za-z0-9_-]{20,}['\"]"),
]


def main() -> int:
    problems = [f"Missing required file: {path}" for path in REQUIRED if not (ROOT / path).is_file()]
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", ".pytest_cache", "__pycache__", ".venv", ".sites-runtime"} for part in path.parts):
            continue
        if path.name == ".env":
            problems.append("A real .env file is present")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", ".gitignore", ".dockerignore"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"Possible secret found in: {path.relative_to(ROOT)}")

    if problems:
        print("RELEASE CHECK FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("RELEASE CHECK PASSED")
    print("- Submission files and dashboard assets are present")
    print("- No real .env file or common API-key pattern was detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
