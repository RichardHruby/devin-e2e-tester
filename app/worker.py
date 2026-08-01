import asyncio
from datetime import datetime, timezone

from . import logging
from .config import Settings
from .db import Database
from .devin import DevinClient
from .github import GitHubClient
from .prompt import parse_verdict, render_prompt


class ReviewWorker:
    def __init__(self, db: Database, github: GitHubClient, devin: DevinClient, settings: Settings):
        self.db, self.github, self.devin, self.settings = db, github, devin, settings
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.lock = asyncio.Lock()

    async def enqueue(self, review_id: int) -> None:
        await self.queue.put(review_id)

    async def run(self) -> None:
        for review in self.db.active():
            self.db.update(review.id, state="failed", summary="Orchestrator restarted")
            logging.transition(review.id, review.pr_number, "failed", reason="restart")
        while True:
            review_id = await self.queue.get()
            try:
                await self.process(review_id)
            except Exception as exc:
                review = self.db.get(review_id)
                self.db.update(review_id, state="failed", summary=str(exc))
                logging.transition(review_id, review.pr_number, "failed", error=str(exc))
            finally:
                self.queue.task_done()

    async def process(self, review_id: int) -> None:
        review = self.db.get(review_id)
        logging.transition(review.id, review.pr_number, review.state)
        try:
            pr = {
                "number": review.pr_number,
                "head": {"sha": review.head_sha},
                "html_url": review.pr_url,
                "title": review.title,
            }
            await self.github.create_commit_status(
                self.settings.superset_repo,
                review.head_sha,
                "pending",
                None,
                "Devin E2E review is starting",
            )
            session = await self.devin.create_session(render_prompt(pr))
            self.db.update(
                review_id,
                state="session_created",
                session_id=session["session_id"],
                session_url=session["url"],
            )
            review = self.db.get(review_id)
            logging.transition(
                review_id, review.pr_number, "session_created", session_id=review.session_id
            )
            await self.github.create_issue_comment(
                self.settings.superset_repo,
                review.pr_number,
                f"Devin E2E review started: {review.session_url}",
            )
            started = datetime.now(timezone.utc)
            while (datetime.now(timezone.utc) - started).total_seconds() < (
                self.settings.review_timeout_minutes * 60
            ):
                if self.db.get(review_id).state != "running":
                    self.db.update(review_id, state="running")
                    logging.transition(
                        review_id, review.pr_number, "running", session_id=review.session_id
                    )
                session_json = await self.devin.get_session(review.session_id)
                verdict = parse_verdict(session_json)
                if verdict:
                    state = (
                        "completed"
                        if verdict.verdict == "pass"
                        else "failed"
                        if verdict.verdict == "error"
                        else "completed"
                    )
                    self.db.update(
                        review_id,
                        state=state,
                        verdict=verdict.verdict,
                        summary=verdict.summary,
                        bugs=verdict.bugs,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                    )
                    review = self.db.get(review_id)
                    await self.github.create_commit_status(
                        self.settings.superset_repo,
                        review.head_sha,
                        "success" if verdict.verdict == "pass" else "failure",
                        review.session_url,
                        f"Devin verdict: {verdict.verdict}",
                    )
                    logging.transition(
                        review_id,
                        review.pr_number,
                        state,
                        session_id=review.session_id,
                        verdict=verdict.verdict,
                    )
                    return
                await asyncio.sleep(self.settings.poll_interval)
            self.db.update(
                review_id,
                state="timed_out",
                summary="Review exceeded timeout",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            review = self.db.get(review_id)
            await self.github.create_commit_status(
                self.settings.superset_repo,
                review.head_sha,
                "failure",
                review.session_url,
                "Devin E2E review timed out",
            )
            logging.transition(
                review_id, review.pr_number, "timed_out", session_id=review.session_id
            )
        except Exception as exc:
            self.db.update(
                review_id,
                state="failed",
                summary=str(exc),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            review = self.db.get(review_id)
            try:
                await self.github.create_commit_status(
                    self.settings.superset_repo,
                    review.head_sha,
                    "failure",
                    review.session_url,
                    "Devin E2E review failed",
                )
            except Exception:
                pass
            logging.transition(
                review_id, review.pr_number, "failed", session_id=review.session_id, error=str(exc)
            )
