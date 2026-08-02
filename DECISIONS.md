# Decisions

Every decision that shaped this system: what I chose, why, and what I rejected. Skim the
headings; read a section only if you care about that call. Back to the
[README](./README.md).

## 1) The trigger is a GitHub Action forwarder, not a raw webhook

Both paths exist. `/webhook/github` with HMAC verification is the production path and still
works. But for this assignment the Action wins, because the trigger becomes **30 lines of
reviewable YAML that live in the repo** instead of a URL and a secret buried in repository
settings that nobody reviewing this can see. The Action never checks out PR code and holds
no credentials — it POSTs a PR number.

The orchestrator doesn't care which one fired: both funnel into the same
`trigger_review(pr)` path, so the trigger is swappable without touching the review logic.

**Rejected:** webhook-only (invisible to a reviewer, and needs a secret exchange before
anyone can try it).

## 2) The `[devin-e2e]` body marker, instead of a label

I started with a `devin-e2e-test` label, then hit GitHub's permission model: **only users
with triage access can add labels.** On a public fork, an external contributor — the exact
person whose PR most needs an unattended review — cannot opt in. So the marker: put
`[devin-e2e]` in the PR body and the Action fires. It's the same permissionless-opt-in
pattern as `/retest` or `[skip ci]`, and it costs one `contains()` in the workflow
condition. The label path stayed, for maintainers who prefer it.

In production I'd expect **no opt-in at all**: fire on every PR touching
`superset-frontend/**` via a `paths` filter. That alternative is written out, commented, in
the workflow file. Opt-in is a demo affordance so a reviewer can choose when to spend a
session — not the end state.

**Rejected:** label-only (locks out external contributors); a magic comment
(`/devin-e2e` as a follow-up comment — works, but it's a second step after opening the PR,
and `issue_comment` events fire on every comment in the repo).

## 3) A stateful orchestrator, instead of doing it all in GitHub Actions

This was the real architecture question. Three options:

| | Session created by | Tracked by | Verdict logic in |
|---|---|---|---|
| **A (chosen)** | orchestrator | orchestrator | tested Python |
| B — all-in-GHA | the workflow job | the job itself | YAML + bash |
| C — split | the workflow job | orchestrator | tested Python |

**B is genuinely viable** and I want to be honest about that: a job can create the session,
poll for 15–20 minutes, and post the results — GitHub even pays for the runner. It fails on
two things. Each run is an isolated VM, so *aggregate* facts — bugs caught, cost per review,
time to verdict, how many reviews are in flight — have nowhere to live; the whole "how would
I know this is working" question goes unanswered. And the verdict handling, issue filing,
and dedupe would be bash inside YAML, which I can't unit-test.

**C is dominated by A.** It splits the Devin key across two holders (the fork's Actions
secrets *and* the orchestrator), it can orphan a paid session if registration fails after
creation, and dedupe has to happen *before* the session exists — which means the thing that
knows about duplicates has to be the thing that creates sessions.

So: **A — the Action is a dumb forwarder; the orchestrator creates, tracks, writes back, and
reports.** One key holder, dedupe before spend, and the state machine lives in Python with
tests.

## 4) GitHub is the source of truth; SQLite is an operational cache

Everything a human acts on — the review comment, the `devin/e2e-review` commit status, the
filed bug issue, the screenshots and recording — lives on GitHub, written through its API.
**Delete `reviews.db` and nothing user-facing is lost.**

SQLite holds what GitHub can't serve: the state machine
(`queued → session_created → running → completed | failed | timed_out`), the PR+SHA dedupe
key, per-review durations, and the aggregates behind the dashboard. That's an operational
cache, and treating it as one is what lets the service run on a free Render instance with a
small disk and no backup story.

**Rejected:** a real database (nothing here needs concurrent writers or durability beyond
one process); keeping state only in memory (a redeploy would lose the metrics that justify
the pilot).

## 5) Structured output, not prose parsing

The session is configured with a JSON schema, so a review is effectively **a typed async
function: PR in, `{verdict, bugs[], summary}` out.** The orchestrator branches on an enum
instead of grepping an essay for the word "fail", and `bugs[]` is what auto-populates the
filed issue.

The important framing: **the verdict is a claim, not proof.** What makes it trustworthy is
the screenshots and recording attached to the PR comment, which a human can check in thirty
seconds. The structured output is for the machine; the evidence is for the person. There's
also a regex fallback that scrapes a trailing JSON object out of the session messages, so a
session that reports its verdict in chat rather than in structured output still lands.

**Rejected:** parsing the final message with an LLM (another model call, another failure
mode, to recover data the API can type for us); a verdict-only boolean (the bug details are
what make the auto-filed issue useful).

## 6) Polling, not callbacks

I checked rather than assumed: the Devin API has **no outbound session-completion webhook**.
v1 and v3 are poll-only, and Automations are inbound triggers — they start sessions, they
don't notify you when one ends. So the worker polls.

At a 60s interval on a review that takes 15–20 minutes, polling costs ~20 cheap GETs and
adds at most 60s of latency to a 20-minute feedback loop. That's negligible, and it has a
property callbacks don't: **the orchestrator can't miss a completion it slept through.**

The evolution I'd document rather than build here: have the session itself POST its verdict
to the orchestrator as its final step, and keep polling as the crash fallback — a session
that dies mid-review will never call you back, so the poller has to stay either way.

## 7) Metrics an EM would use to decide roll-out vs kill

I picked these by imagining the person piloting this on one repo, three months in, deciding
whether to expand it or turn it off:

- **Reviews run** — the denominator. Without it every other number is unreadable.
- **Bugs caught pre-merge**, each with one-click links to the filed issue and the evidence
  comment. This is the entire value proposition, and it has to be *checkable*, not asserted.
- **Cost per review, in dollars** — ACUs from the v3 org API × the plan's ACU rate. It shows
  `n/a` until billing data exists, deliberately: a fake `$0.00` would be worse than a blank,
  because someone would quote it.
- **Time to verdict** — the latency a PR author actually feels, and the number that decides
  whether people wait for the review or merge past it.

**Deliberately cut from the headline: pass rate.** It's ambiguous in both directions — a
high pass rate means either the code is good or the reviews are shallow, and it moves with
what people submit, not with how well the system works.

## 8) A blueprint snapshot, not per-session setup

Sessions boot from a prebuilt snapshot defined by a per-repo blueprint (Node 24.16.0,
frontend dependencies installed, backend image pulled), rebuilt when the blueprint changes.
Warm boot is ~45s to a healthy backend, versus the many minutes a cold `npm install` plus
image pull would cost **on every review** — and every one of those minutes is ACUs spent
watching a progress bar instead of testing the PR.

This is also the production-realistic shape: setup is declarative and version-controlled
rather than improvised in a prompt, which means it's reviewable and fixable in one place
when it breaks.

What production would change: pin release images instead of `latest`, use staging
credentials stored as Devin organization secrets rather than `admin`/`admin`, and build a
backend image from the PR when backend changes are in scope.

**Honest caveat:** the demo's backend image is prebuilt, so only the frontend runs from the
PR branch. Backend changes are not exercised. For a frontend-heavy repo like Superset this
covers most UI PRs, but it's a real limit, not a rounding error.
