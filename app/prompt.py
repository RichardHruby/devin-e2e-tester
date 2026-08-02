from pathlib import Path
from string import Template

from .models import Review

TEMPLATE = Path(__file__).resolve().parent.parent / "prompts" / "e2e_review.md"


def render_prompt(review: Review) -> str:
    return Template(TEMPLATE.read_text()).substitute(
        pr_url=review.pr_url,
        title=review.title,
        body=review.body or "(no description provided)",
        head_branch=review.head_branch,
        repo=review.repo,
        head_sha=review.head_sha,
    )
