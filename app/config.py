import os
from dataclasses import dataclass


@dataclass
class Settings:
    devin_api_key: str = os.getenv("DEVIN_API_KEY", "")
    devin_org_api_key: str = os.getenv("DEVIN_ORG_API_KEY", "")
    devin_org_id: str = os.getenv("DEVIN_ORG_ID", "")
    acu_cost_usd: float = float(os.getenv("ACU_COST_USD", "2.25"))
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    superset_repo: str = os.getenv("SUPERSET_REPO", "RichardHruby/superset")
    review_label: str = os.getenv("REVIEW_LABEL", "devin-e2e-test")
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "60"))
    review_timeout_minutes: int = int(os.getenv("REVIEW_TIMEOUT_MINUTES", "90"))
    max_concurrent_reviews: int = int(os.getenv("MAX_CONCURRENT_REVIEWS", "3"))
    review_body_marker: str = os.getenv("REVIEW_BODY_MARKER", "[devin-e2e]")
    database_path: str = os.getenv("DATABASE_PATH", "./data/reviews.db")
    github_api_url: str = "https://api.github.com"
    devin_api_url: str = "https://api.devin.ai"


settings = Settings()
