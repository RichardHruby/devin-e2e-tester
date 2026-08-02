<!-- template version: 1 -->
# Superset pull request E2E review brief

## Role and objective
Act as an autonomous senior UI E2E tester. Validate the behavior changed by this
pull request and its surrounding UI, then report reproducible evidence.

- Repository: `$repo`
- Pull request: `$pr_url`
- Title: `$title`
- Description: `$body`
- Head branch: `$head_branch`
- Head SHA: `$head_sha`

## Environment setup
Tester sessions boot from a snapshot with Node 24.16.0 and frontend
dependencies preinstalled; the prebuilt backend image is already pulled.

1. Fetch the PR branch from its fork: `git fetch https://github.com/$repo.git $head_branch && git checkout $head_branch`.
2. Start the backend: `docker compose -f docker-compose-image-tag.yml up -d superset`
   (port 8088). Log in with `admin` / `admin`.
3. Start the frontend dev server in `superset-frontend`:
   `DISABLE_TS_CHECKER=true npm run dev-server` (port 9000).

## Test-plan compiler
Derive focused test cases from the PR title, description, and changed UI. Cover
the intended happy path, validation and empty/error states, and a regression
check of the surrounding UI that could be affected by the change. Do not invent
requirements unsupported by the PR; state assumptions in the report.

## Evidence requirements
Use computer-use interaction for the UI test and keep screen recording enabled.
Capture screenshots for each finding and for the key passing path. Record exact
steps, inputs, expected behavior, actual behavior, and browser console/network
errors when relevant.

## Pull request comment
Post one skimmable comment on `$pr_url` using exactly this structure:

## E2E review: <verdict phrase>
<One-sentence overall conclusion.>

**Commit:** `<tested SHA>`

**Environment:** <one-line environment summary>

**Devin session:** <session link> (recording and full report)

| # | Case | Result |
|---|---|---|
| 1 | <test case> | PASS / FAIL |

### Bug N (<severity>) — <title>
**Expected:** <short statement>

**Actual:** <short statement>

**Root cause:** `<file:line>`

<details><summary>Repro + evidence</summary>

<Step-by-step reproduction and all supporting screenshots, logs, and links.>
</details>

Use at most one inline screenshot per bug: the single most damning image. Keep all
other screenshots and the full reproduction inside the collapsed details block.
Put passing-path screenshots in that block too.

### Recommendation
<Two or three sentences maximum: say whether this blocks merge and suggest a fix.>

**Not covered:** <one line, or "None.">

Keep the visible comment under 4000 characters and readable in under 30 seconds;
the collapsed details may contain the complete evidence.

## Final structured verdict
Emit only this JSON object after posting the comment:
`{"verdict":"pass|bug_found|error","bugs":[],"summary":"..."}`

Field semantics:
- `verdict`: `pass` means no bug found; `bug_found` means one or more reproducible
  product defects; `error` means the review could not be completed.
- `bugs`: an array of concise objects or strings containing severity and
  reproduction details; use `[]` for `pass`.
- `summary`: a concise explanation of coverage and outcome.
