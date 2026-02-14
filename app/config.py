"""Load config from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of app/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


# GitHub App (private key: use literal \n in .env or multi-line; we normalize \\n -> newline)
_raw_key = get_env("GITHUB_APP_PRIVATE_KEY") or ""
GITHUB_APP_ID = get_env("GITHUB_APP_ID")
GITHUB_APP_WEBHOOK_SECRET = get_env("GITHUB_APP_WEBHOOK_SECRET")
GITHUB_APP_PRIVATE_KEY = _raw_key.replace("\\n", "\n") if _raw_key else ""

# Gemini
GOOGLE_API_KEY = get_env("GOOGLE_API_KEY")

# Server
PORT = int(get_env("PORT", "8000"))
