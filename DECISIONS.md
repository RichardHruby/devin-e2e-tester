# Decisions

The main design choices behind the demo. Back to the [README](./README.md).

## 1) The trigger is a GitHub Action forwarder

The Action is a short, reviewable YAML forwarder that posts a PR number to
`POST /reviews`. It holds no Devin credentials; session creation, dedupe, and write-back
stay in the tested Python service.

## 2) The `[devin-e2e]` body marker

The body marker lets external contributors opt in on a public fork because GitHub limits
who can add labels. The Action matches `[devin-e2e]` and forwards the PR number without
requiring repository permissions.

## 3) A stateful orchestrator

The Action stays a dumb forwarder; the orchestrator creates sessions, deduplicates before
spend, persists state and metrics, and writes results back to GitHub. This keeps the
workflow small and puts testable lifecycle logic in Python.

## 4) GitHub is the source of truth; SQLite is an operational cache

GitHub stores comments, statuses, issues, screenshots, and recordings. SQLite stores the
local state machine, PR+SHA dedupe key, durations, and dashboard aggregates; losing it does
not lose user-facing evidence.

## 5) Structured output, not prose parsing

The session returns `{verdict, bugs[], summary}` under a JSON schema. The orchestrator uses
that typed result for statuses and issue filing, while screenshots and recordings in the
PR comment provide the evidence a human checks.

## 6) Polling, not callbacks

The Devin API has no outbound session-completion webhook, so the worker polls. At a
60-second interval, a 15–20 minute review costs about 20 inexpensive GETs and adds at most
60 seconds of result latency.

## 7) Metrics an EM would use to decide roll-out vs kill

- **Reviews run** — the denominator for every other metric.
- **Bugs caught pre-merge** — linked to the filed issue and evidence comment.
- **Cost per review** — Enterprise orgs use v3 ACUs × plan rate; this self-serve org reports
  `acus_consumed=0.0` and has no public per-session dollar API, so the dashboard shows `n/a`.
  Usage-page measurements put a full E2E review at about `$5`.
- **Time to verdict** — the latency a PR author experiences.

Pass rate stays out of the headline because it reflects the submitted PR mix as much as
review quality.

## 8) A blueprint snapshot, not per-session setup

Sessions boot from a prebuilt snapshot with Node 24.16.0, frontend dependencies, and the
backend image already available. This keeps reviews fast and makes the environment
declarative and version-controlled.

Production would pin release images, use staging credentials from Devin organization
secrets, and build the backend image from the PR when backend changes are in scope. The
demo's prebuilt backend means only frontend changes run from the PR branch; that is a
deliberate scope cut for the demo.
