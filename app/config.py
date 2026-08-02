import os
from dataclasses import dataclass


@dataclass
class Settings:
    devin_api_key: str = os.getenv("DEVIN_API_KEY", "")
    devin_org_api_key: str = os.getenv("DEVIN_ORG_API_KEY", "")
    devin_org_id: str = os.getenv("DEVIN_ORG_ID", "")
    acu_cost_usd: float = float(os.getenv("ACU_COST_USD", "2.25"))
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    reviews_token: str = os.getenv("REVIEWS_TOKEN", "")
    superset_repo: str = os.getenv("SUPERSET_REPO", "RichardHruby/superset")
    database_path: str = os.getenv("DATABASE_PATH", "./data/reviews.db")
    github_api_url: str = "https://api.github.com"
    devin_api_url: str = "https://api.devin.ai"


settings = Settings()
