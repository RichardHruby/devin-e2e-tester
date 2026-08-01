import os
from dataclasses import dataclass


@dataclass
class Settings:
    devin_api_key: str = os.getenv("DEVIN_API_KEY", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    superset_repo: str = os.getenv("SUPERSET_REPO", "RichardHruby/superset")
    review_label: str = os.getenv("REVIEW_LABEL", "devin-e2e-test")
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "60"))
    review_timeout_minutes: int = int(os.getenv("REVIEW_TIMEOUT_MINUTES", "90"))
    database_path: str = os.getenv("DATABASE_PATH", "./data/reviews.db")
    github_api_url: str = "https://api.github.com"
    devin_api_url: str = "https://api.devin.ai"


settings = Settings()
