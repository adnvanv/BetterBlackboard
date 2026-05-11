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
