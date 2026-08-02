import html
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import settings
from .db import Database
from .devin import DevinClient
from .github import GitHubClient
from .worker import ReviewWorker

db = Database(settings.database_path)
github = GitHubClient(settings.github_token, settings.github_api_url)
devin = DevinClient(
    settings.devin_api_key,
    settings.devin_api_url,
    settings.devin_org_api_key,
    settings.devin_org_id,
)
worker = ReviewWorker(db, github, devin, settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker.mark_stranded_reviews_failed()
    yield
    await worker.shutdown()
    await github.close()
    await devin.close()


app = FastAPI(title="Devin E2E Orchestrator", lifespan=lifespan)


async def trigger_review(pr: dict) -> dict:
    async with worker.lock:
        review, created = db.create(pr)
        if created:
            await worker.enqueue(review.id)
            return {"status": "queued", "review_id": review.id, "pr_number": review.pr_number}
        status = (
            "already_reviewing"
            if review.state in {"queued", "session_created", "running"}
            else "already_reviewed"
        )
        return {"status": status, "review_id": review.id, "state": review.state}


class SimulateRequest(BaseModel):
    pr_number: int


@app.post("/simulate")
async def simulate(request: Request, payload: SimulateRequest):
    if settings.simulate_token:
        authorization = request.headers.get("authorization")
        if authorization != f"Bearer {settings.simulate_token}":
            raise HTTPException(status_code=401, detail="Unauthorized")
    pr = await github.get_pr(settings.superset_repo, payload.pr_number)
    return await trigger_review(pr)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/metrics.json")
async def metrics():
    return db.stats()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    stats = db.stats()
    cards = "".join(
        f'<div class="card"><b>{html.escape(str(value))}</b><span>{html.escape(label)}</span></div>'
        for label, value in [
            ("Reviews run", stats["total_reviews"]),
            ("Bugs caught (pre-merge)", stats["bugs_caught"]),
            (
                "Cost / review",
                f"${stats['avg_cost_per_review_usd']:.2f}"
                if stats["avg_cost_per_review_usd"] is not None
                else "n/a",
            ),
            ("Avg time to verdict", f"{stats['avg_time_to_verdict_seconds'] / 60:.1f}m"),
            ("Active", stats["active"]),
        ]
    )
    rows = []
    for review in db.all():
        started = datetime.fromisoformat(review.created_at)
        finished = (
            datetime.fromisoformat(review.completed_at)
            if review.completed_at
            else datetime.now(timezone.utc)
        )
        duration = (finished - started).total_seconds() / 60
        session = (
            f'<a href="{html.escape(review.session_url)}">Open session</a>'
            if review.session_url
            else "—"
        )
        verdict = html.escape(review.verdict or "—")
        badge_class = (
            "pass"
            if review.verdict == "pass"
            else "bug_found"
            if review.verdict == "bug_found"
            else "error"
            if review.state in {"failed", "timed_out"}
            else "active"
        )
        summary = html.escape((review.summary or "No summary")[:120])
        bug_count = len(review.bugs)
        findings = summary + f"<br><small>{bug_count} bug(s)</small>"
        if review.issue_url:
            findings += f' · <a href="{html.escape(review.issue_url)}">Issue</a>'
        if review.evidence_url:
            findings += f' · <a href="{html.escape(review.evidence_url)}">Evidence</a>'
        cost = f"${review.cost_usd:.2f}" if review.cost_usd is not None else "n/a"
        rows.append(
            f'<tr><td><a href="{html.escape(review.pr_url)}">PR #{review.pr_number}: '
            f'{html.escape(review.title)}</a></td><td><span class="badge {badge_class}">'
            f"{html.escape(review.state)}</span></td><td>{verdict}</td><td>{session}</td>"
            f"<td>{findings}</td><td>{cost}</td><td>{duration:.1f}m</td></tr>"
        )
    return f"""<!doctype html><html><head><meta http-equiv="refresh" content="15">
<title>Devin E2E Reviews</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fb;color:#172033;font:15px
Inter,system-ui,sans-serif}}main{{max-width:1200px;margin:0 auto;padding:42px 28px}}
h1{{margin:0 0 8px;font-size:30px}}.sub{{color:#667085;margin-bottom:28px}}
.cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}.card{{background:white;
border:1px solid #e6eaf0;border-radius:12px;padding:18px 22px;min-width:145px;
box-shadow:0 2px 8px #1720330b}}.card b{{display:block;font-size:25px}}.card span{{color:#667085}}
.panel{{background:white;border:1px solid #e6eaf0;border-radius:12px;overflow:hidden}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:15px 18px;text-align:left;
border-bottom:1px solid #edf0f4}}th{{font-size:12px;text-transform:uppercase;color:#667085}}
a{{color:#315efb;text-decoration:none}}.badge{{padding:5px 9px;border-radius:99px;
font-size:12px;font-weight:600;background:#eef2f7}}.pass{{background:#dcfce7;color:#166534}}
.bug_found{{background:#fef3c7;color:#92400e}}.error{{background:#fee2e2;color:#991b1b}}
.active{{background:#dbeafe;color:#1d4ed8}}
</style></head><body><main><h1>Devin E2E Reviews</h1><div class="sub">Autonomous UI validation for Superset pull requests · refreshes every 15 seconds</div>
<div class="cards">{cards}</div><div class="panel"><table><thead><tr><th>Pull request</th><th>State</th><th>Verdict</th><th>Devin session</th><th>Findings</th><th>Cost</th><th>Duration</th></tr></thead>
<tbody>{"".join(rows) or '<tr><td colspan="7">No reviews yet.</td></tr>'}</tbody></table></div></main></body></html>"""
