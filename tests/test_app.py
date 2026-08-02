import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import httpx

os.environ["DATABASE_PATH"] = "/tmp/devin-e2e-test.db"
os.environ["GITHUB_WEBHOOK_SECRET"] = "secret"
try:
    os.remove(os.environ["DATABASE_PATH"])
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.devin import DevinClient, parse_verdict
from app.main import app
from app.prompt import render_prompt
from app.worker import ReviewWorker


def payload():
    return {
        "action": "labeled",
        "label": {"name": "devin-e2e-test"},
        "pull_request": {
            "number": 7,
            "html_url": "https://github.com/x/y/pull/7",
            "title": "UI fix",
            "body": "test it",
            "head": {"ref": "feature", "sha": "abc"},
            "base": {"repo": {"full_name": "RichardHruby/superset"}},
        },
    }


def test_signature_and_label_filter():
    raw = json.dumps(payload()).encode()
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    from app import main

    async def enqueue(_: int):
        return None

    main.worker.enqueue = enqueue
    with TestClient(app) as client:
        assert (
            client.post(
                "/webhook/github", content=raw, headers={"x-hub-signature-256": signature}
            ).json()["status"]
            == "queued"
        )
        ignored = payload()
        ignored["label"]["name"] = "other"
        ignored_raw = json.dumps(ignored).encode()
        ignored_signature = "sha256=" + hmac.new(b"secret", ignored_raw, hashlib.sha256).hexdigest()
        assert (
            client.post(
                "/webhook/github",
                content=ignored_raw,
                headers={"x-hub-signature-256": ignored_signature},
            ).json()["status"]
            == "ignored"
        )
        assert (
            client.post(
                "/webhook/github", content=raw, headers={"x-hub-signature-256": "sha256=bad"}
            ).status_code
            == 401
        )
        duplicate = client.post(
            "/webhook/github", content=raw, headers={"x-hub-signature-256": signature}
        ).json()
        assert duplicate["status"] == "already_reviewing"


def test_missing_secret_skips_validation(monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "github_webhook_secret", "")

    async def enqueue(_: int):
        return None

    main.worker.enqueue = enqueue
    with TestClient(app) as client:
        response = client.post("/webhook/github", json=payload())
        assert response.status_code == 200


def test_body_marker_triggers_opened_review(monkeypatch):
    from app import main

    marked = payload()
    marked["action"] = "opened"
    marked["pull_request"]["head"]["sha"] = "opened-sha"
    marked["pull_request"]["body"] = "Please review this. [devin-e2e]"
    monkeypatch.setattr(main.settings, "review_body_marker", "[devin-e2e]")

    async def enqueue(_: int):
        return None

    main.worker.enqueue = enqueue
    raw = json.dumps(marked).encode()
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        response = client.post(
            "/webhook/github",
            content=raw,
            headers={"x-hub-signature-256": signature},
        )
    assert response.json()["status"] == "queued"


def test_verdict_parsing():
    assert (
        parse_verdict(
            {
                "structured_output": {
                    "verdict": "pass",
                    "bugs": [],
                    "summary": "Looks good",
                    "fix_pr_url": None,
                }
            }
        ).verdict
        == "pass"
    )
    result = parse_verdict(
        {
            "messages": [
                {
                    "message": 'done {"verdict":"bug_found","bugs":["x"],'
                    '"summary":"broken","fix_pr_url":null}'
                }
            ]
        }
    )
    assert result and result.verdict == "bug_found"
    assert parse_verdict({"messages": []}) is None


def test_persisted_review_renders_complete_prompt(tmp_path):
    test_db = Database(str(tmp_path / "reviews.db"))
    review, created = test_db.create(payload()["pull_request"])
    assert created
    prompt = render_prompt(review)
    assert "feature" in prompt
    assert "RichardHruby/superset" in prompt
    assert "test it" in prompt
    assert "SUPERSET_LOAD_EXAMPLES=no" in prompt


def test_terminal_review_can_be_re_run(tmp_path):
    test_db = Database(str(tmp_path / "reviews.db"))
    first, created = test_db.create(payload()["pull_request"])
    assert created
    test_db.update(first.id, state="completed", verdict="pass")
    second, created = test_db.create(payload()["pull_request"])
    assert created
    assert second.id != first.id


def test_stats_metrics():
    try:
        os.remove("/tmp/devin-stats.db")
    except FileNotFoundError:
        pass
    test_db = Database("/tmp/devin-stats.db")
    review, _ = test_db.create(payload()["pull_request"])
    test_db.update(
        review.id,
        state="completed",
        verdict="pass",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    assert test_db.stats()["pass_rate"] == 1
    with TestClient(app) as client:
        assert "total_reviews" in client.get("/metrics.json").json()
        assert "Devin E2E Reviews" in client.get("/dashboard").text


def test_bug_issue_is_filed_once(tmp_path):
    class FakeGitHub:
        def __init__(self):
            self.issue_calls = 0
            self.comment_calls = 0

        async def create_issue(self, repo, title, body, label):
            self.issue_calls += 1
            assert repo == "RichardHruby/superset"
            assert title == "[devin-e2e] Bug found in PR #7: UI fix"
            assert all(
                field in body
                for field in ("Title", "Severity", "Location", "Suggested Fix")
            )
            assert label == "devin-e2e-test"
            return "https://github.com/RichardHruby/superset/issues/8"

        async def create_issue_comment(self, repo, number, body):
            self.comment_calls += 1
            assert "issues/8" in body
            return "https://github.com/RichardHruby/superset/pull/7#issuecomment-9"

    test_db = Database(str(tmp_path / "reviews.db"))
    review, _ = test_db.create(payload()["pull_request"])
    test_db.update(
        review.id,
        verdict="bug_found",
        bugs=[
            {
                "title": "Checkbox is inverted",
                "severity": "high",
                "location": "UserListModal.tsx:117",
                "repro": "Edit an active user",
                "expected": "Checkbox is checked",
                "actual": "Checkbox is unchecked",
                "suggested_fix": "Preserve active state",
            }
        ],
        session_url="https://app.devin.ai/sessions/devin-abc",
    )
    github = FakeGitHub()
    worker = ReviewWorker(test_db, github, object(), Settings())
    updated = test_db.get(review.id)
    asyncio.run(worker._file_bug_issue(updated))
    asyncio.run(worker._file_bug_issue(test_db.get(review.id)))
    result = test_db.get(review.id)
    assert result.issue_url.endswith("/issues/8")
    assert result.evidence_url.endswith("issuecomment-9")
    assert github.issue_calls == 1
    assert github.comment_calls == 1


def test_cost_enrichment_uses_v3_org_endpoint():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"acus_consumed": 4.5})

    client = DevinClient("", org_api_key="org-key", org_id="org-123")
    client.org_client = httpx.AsyncClient(
        base_url="https://api.devin.ai",
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer org-key"},
    )
    assert asyncio.run(client.get_session_usage("devin-abc")) == 4.5
    assert requests[0].url.path == "/v3/organizations/org-123/sessions/devin-abc"
    asyncio.run(client.close())


def test_cost_enrichment_persists_acus_and_cost(tmp_path):
    class FakeDevin:
        async def get_session_usage(self, session_id):
            assert session_id == "devin-abc"
            return 4.5

    test_db = Database(str(tmp_path / "reviews.db"))
    review, _ = test_db.create(payload()["pull_request"])
    test_db.update(review.id, session_id="devin-abc")
    worker = ReviewWorker(test_db, object(), FakeDevin(), Settings())
    asyncio.run(worker._enrich_cost(test_db.get(review.id)))
    result = test_db.get(review.id)
    assert result.acus_consumed == 4.5
    assert result.cost_usd == 10.125
