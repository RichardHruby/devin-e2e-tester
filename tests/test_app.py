import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

os.environ["DATABASE_PATH"] = "/tmp/devin-e2e-test.db"
os.environ["GITHUB_WEBHOOK_SECRET"] = "secret"
try:
    os.remove(os.environ["DATABASE_PATH"])
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient

from app.db import Database
from app.main import app
from app.prompt import parse_verdict


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
