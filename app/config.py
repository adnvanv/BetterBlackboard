import json
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    BLACKBOARD_URL: str = ""
    BLACKBOARD_USER: str = ""
    BLACKBOARD_PASS: str = ""

    BB_DB_PATH: str = "betterblackboard.db"
    BB_STORAGE_STATE: str = "storage_state.json"
    BB_HEADLESS: bool = True
    BB_SCRAPE_CONCURRENCY: int = 3

    # Shared secret used by the login_client GUI to upload a fresh storage_state.json.
    # Set to a long random string. If empty, the upload endpoint is disabled.
    BB_UPLOAD_TOKEN: str = ""

    # Daily auto-scrape — set BB_SCHEDULE to empty string to disable.
    # Hour and minute are in BB_TIMEZONE (default America/New_York).
    BB_SCHEDULE: str = "0 5 * * *"  # cron-style: min hour dom mon dow
    BB_TIMEZONE: str = "America/New_York"


settings = Settings()


def _credentials_path() -> str:
    base = os.path.dirname(os.path.abspath(settings.BB_STORAGE_STATE)) or "."
    return os.path.join(base, "credentials.json")


def get_credentials() -> tuple[str, str]:
    """Return (username, password) for Blackboard.

    Prefers `credentials.json` (written by the login_client upload) over the
    .env defaults, so creds can be refreshed at runtime without an env edit
    or container restart. Falls back to BLACKBOARD_USER / BLACKBOARD_PASS.
    """
    cpath = _credentials_path()
    if os.path.exists(cpath):
        try:
            with open(cpath, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            user = (data.get("blackboard_user") or "").strip()
            password = data.get("blackboard_pass") or ""
            if user or password:
                return user or settings.BLACKBOARD_USER, password or settings.BLACKBOARD_PASS
        except Exception:
            pass
    return settings.BLACKBOARD_USER, settings.BLACKBOARD_PASS
