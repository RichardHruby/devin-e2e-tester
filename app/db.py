import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .models import ACTIVE_STATES, Review


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT, pr_number INTEGER NOT NULL,
                head_sha TEXT NOT NULL, head_branch TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '', repo TEXT NOT NULL DEFAULT '',
                pr_url TEXT NOT NULL, title TEXT NOT NULL,
                state TEXT NOT NULL, verdict TEXT, summary TEXT, bugs TEXT NOT NULL,
                session_id TEXT, session_url TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, completed_at TEXT,
                prompt_version INTEGER NOT NULL DEFAULT 1,
                issue_url TEXT, evidence_url TEXT, acus_consumed REAL, cost_usd REAL
            )
            """
        )
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(reviews)")}
        for name, definition in (
            ("head_branch", "TEXT NOT NULL DEFAULT ''"),
            ("body", "TEXT NOT NULL DEFAULT ''"),
            ("repo", "TEXT NOT NULL DEFAULT ''"),
            ("prompt_version", "INTEGER NOT NULL DEFAULT 1"),
            ("issue_url", "TEXT"),
            ("evidence_url", "TEXT"),
            ("acus_consumed", "REAL"),
            ("cost_usd", "REAL"),
        ):
            if name not in columns:
                self.conn.execute(f"ALTER TABLE reviews ADD COLUMN {name} {definition}")
        self.conn.execute("DROP INDEX IF EXISTS review_pr_sha")
        self.conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS review_pr_sha_active
            ON reviews(pr_number, head_sha)
            WHERE state IN ('queued', 'session_created', 'running')"""
        )
        self.conn.commit()

    def _review(self, row: sqlite3.Row) -> Review:
        return Review(
            id=row["id"],
            pr_number=row["pr_number"],
            head_sha=row["head_sha"],
            head_branch=row["head_branch"],
            body=row["body"],
            repo=row["repo"],
            pr_url=row["pr_url"],
            title=row["title"],
            state=row["state"],
            verdict=row["verdict"],
            summary=row["summary"],
            bugs=json.loads(row["bugs"] or "[]"),
            session_id=row["session_id"],
            session_url=row["session_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            prompt_version=row["prompt_version"],
            issue_url=row["issue_url"],
            evidence_url=row["evidence_url"],
            acus_consumed=row["acus_consumed"],
            cost_usd=row["cost_usd"],
        )

    def create(self, pr: dict[str, Any]) -> tuple[Review, bool]:
        head = pr["head"]["sha"]
        existing = self.conn.execute(
            "SELECT * FROM reviews WHERE pr_number=? AND head_sha=?",
            (pr["number"], head),
        ).fetchone()
        if existing and existing["state"] in ACTIVE_STATES:
            return self._review(existing), False
        timestamp = now()
        try:
            cursor = self.conn.execute(
                """INSERT INTO reviews
                (pr_number, head_sha, head_branch, body, repo, pr_url, title,
                 state, bugs, created_at, updated_at, prompt_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', '[]', ?, ?, 1)""",
                (
                    pr["number"],
                    head,
                    pr["head"].get("ref", ""),
                    pr.get("body") or "",
                    pr.get("base", {}).get("repo", {}).get("full_name", ""),
                    pr.get("html_url", ""),
                    pr.get("title", ""),
                    timestamp,
                    timestamp,
                ),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            existing = self.conn.execute(
                "SELECT * FROM reviews WHERE pr_number=? AND head_sha=?",
                (pr["number"], head),
            ).fetchone()
            if existing and existing["state"] in ACTIVE_STATES:
                return self._review(existing), False
            raise
        return self.get(cursor.lastrowid), True

    def get(self, review_id: int) -> Review:
        row = self.conn.execute("SELECT * FROM reviews WHERE id=?", (review_id,)).fetchone()
        if not row:
            raise KeyError(review_id)
        return self._review(row)

    def update(self, review_id: int, **values: Any) -> Review:
        values["updated_at"] = now()
        if "bugs" in values:
            values["bugs"] = json.dumps(values["bugs"])
        assignments = ", ".join(f"{key}=?" for key in values)
        self.conn.execute(
            f"UPDATE reviews SET {assignments} WHERE id=?",
            (*values.values(), review_id),
        )
        self.conn.commit()
        return self.get(review_id)

    def active(self) -> list[Review]:
        rows = self.conn.execute(
            "SELECT * FROM reviews "
            "WHERE state IN ('queued','session_created','running') ORDER BY id"
        ).fetchall()
        return [self._review(row) for row in rows]

    def all(self) -> list[Review]:
        rows = self.conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
        return [self._review(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        rows = self.all()
        completed = [r for r in rows if r.state == "completed" and r.completed_at]
        durations = []
        for review in completed:
            start = datetime.fromisoformat(review.created_at)
            end = datetime.fromisoformat(review.completed_at)
            durations.append((end - start).total_seconds())
        bug_count = sum(r.verdict == "bug_found" for r in rows)
        costs = [r.cost_usd for r in completed if r.cost_usd is not None]
        acus = [r.acus_consumed for r in completed if r.acus_consumed is not None]
        return {
            "total_reviews": len(rows),
            "active": sum(r.state in ACTIVE_STATES for r in rows),
            "bugs_caught": bug_count,
            "avg_time_to_verdict_seconds": round(sum(durations) / len(durations), 1)
            if durations
            else 0,
            "total_acus": round(sum(acus), 3) if acus else None,
            "avg_cost_per_review_usd": round(sum(costs) / len(costs), 2) if costs else None,
            "cost_per_bug_usd": round(sum(costs) / bug_count, 2) if costs and bug_count else None,
        }
