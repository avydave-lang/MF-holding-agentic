from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql://intel:intel@localhost:5432/competitor_intel"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str = ""

    # Scraping
    scrape_timeout_seconds: int = 30
    scrape_max_retries: int = 2

    # Drift detection
    drift_threshold: float = 0.15
    drift_schedule: str = "0 2 * * *"

    # Confidence scoring thresholds
    confidence_accept: float = 0.85
    confidence_flag: float = 0.60

    # Scripts directory (generated scrape_portal.py files stored per domain)
    scripts_dir: Path = Path("scripts")

    # Escalation log
    log_escalation_path: Path = Path("escalation_logs/escalation.log")
    escalation_screenshots_dir: Path = Path("escalation_logs/screenshots")


settings = Settings()
