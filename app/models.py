from dataclasses import dataclass
from typing import Any

ACTIVE_STATES = {"queued", "session_created", "running"}


@dataclass
class Verdict:
    verdict: str
    bugs: list[Any]
    summary: str


@dataclass
class Review:
    id: int
    pr_number: int
    head_sha: str
    head_branch: str
    body: str
    repo: str
    pr_url: str
    title: str
    state: str
    verdict: str | None
    summary: str | None
    bugs: list[Any]
    session_id: str | None
    session_url: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    prompt_version: int
    issue_url: str | None
    evidence_url: str | None
    acus_consumed: float | None
    cost_usd: float | None
