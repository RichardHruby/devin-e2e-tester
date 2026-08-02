# Reviewer guide: fire an end-to-end review yourself

This is the two-click path for trying the orchestrator: three branches are
already pushed to the public fork
[`RichardHruby/superset`](https://github.com/RichardHruby/superset). Turning one
of them into a pull request is the only action required — everything after that
runs on its own.

No repository permissions, tokens, or local setup are needed. Each review takes
about **15–20 minutes** end to end.

## The two clicks

1. Open the compare link for one of the branches below. GitHub shows the diff
   with a green **Create pull request** button.
2. Paste the provided title and body (the body must keep the `[devin-e2e]`
   marker — that is what the trigger workflow matches on) and click
   **Create pull request**.

> Each marked pull request spends one real Devin review. Start with a single
> branch; open a second one only if you want to compare a `pass` run with a
> `bug_found` run.

## Demo branches

Every branch is based on the fork's current `master` and is a small, plausible
frontend change in the Settings UI. Two of them contain a subtly planted defect;
one is genuinely correct. The pull request bodies below describe the *intended*
behavior — that is what Devin compiles its test plan from — so a defect shows up
as a claim the running UI does not honor.

Expected verdicts are what the system *should* return; the review is live, so
treat them as the reference answer rather than a scripted outcome.

---

### 1. User status tag — expected verdict: `bug_found`

Compare link:
<https://github.com/RichardHruby/superset/compare/master...demo/user-status-badge>

Title:

```text
feat(users): show status tag in user list and preserve active state on edit
```

Body:

```markdown
[devin-e2e]

### Summary

The user list rendered the account state as a bare `Yes`/`No` cell, which is
hard to scan, and the edit form gave no hint about what "Is active?" controls.
This renames the column to **Status**, renders it as a tag, and moves the
initial values of the user form into a small helper so the add and edit modals
stay in sync.

### Behavior

- **Settings → List Users** shows a **Status** column: a green `Active` tag for
  active accounts and a grey `Inactive` tag for deactivated ones.
- **Add User** defaults "Is active?" to checked, and the field shows the hint
  "Inactive users keep their data but cannot log in."
- **Editing an existing user preserves that user's current state**: opening
  **Edit** on an inactive user shows "Is active?" unchecked, and saving the form
  without touching that field leaves the user inactive in the list.

### Testing instructions

1. Go to **Settings → List Users** and add a user with "Is active?" unchecked —
   it appears with a grey `Inactive` tag.
2. Click **Edit** on that user: "Is active?" is unchecked.
3. Save without changing anything: the user is still `Inactive` in the list.
```

---

### 2. User form validation — expected verdict: `pass`

Compare link:
<https://github.com/RichardHruby/superset/compare/master...demo/user-form-validation>

Title:

```text
feat(users): validate username format and password length in the user form
```

Body:

```markdown
[devin-e2e]

### Summary

Creating a user with a two-character username or a three-character password
only failed once the request reached the backend, and the resulting toast did
not say which field was wrong. This adds two client-side rules to the user form
and unit tests for them.

### Behavior

- Username shorter than 3 characters shows the inline error
  "Username must be at least 3 characters".
- Username containing a space shows "Username cannot contain spaces".
- The inline error disappears as soon as the username becomes valid.
- Password shorter than 8 characters shows
  "Password must be at least 8 characters".
- The form cannot be saved while an inline error is shown; the existing
  "Passwords do not match!" check and the required-field errors are unchanged.

### Testing instructions

1. **Settings → List Users → + User**.
2. Type `ab` in Username, then `a b`, then `abc` — the first two show the errors
   above, the third clears them.
3. Type `short` in Password — the length error appears; saving is blocked until
   all fields are valid.
```

---

### 3. Group member count — expected verdict: `bug_found`

Compare link:
<https://github.com/RichardHruby/superset/compare/master...demo/group-member-count>

Title:

```text
feat(groups): add member count column and a clearer delete confirmation
```

Body:

```markdown
[devin-e2e]

### Summary

The group list did not show how many users a group contains, and the delete
confirmation was generic enough that it was easy to delete the wrong group. This
adds a **Members** column, names the group in the delete confirmation, and
extracts the group form's initial values into a helper.

### Behavior

- **Settings → List Groups** shows a **Members** column with the number of users
  in each group.
- The delete confirmation reads "This action will permanently delete the group
  <name> and remove its N member(s) from it."
- **Editing a group is unchanged**: opening **Edit** keeps the group's assigned
  roles and users preselected, and saving the form without changes succeeds with
  the "The group has been updated successfully." toast, leaving the roles as
  they were.

### Testing instructions

1. **Settings → List Groups → + Group**: create a group with a name and one role
   assigned.
2. The list shows the new group with a **Members** count.
3. Click **Edit** on it, change nothing, and save — the group keeps its role.
4. Click **Delete**: the confirmation names the group and its member count.
```

---

## What you will see, and where

| When | Where | What |
|---|---|---|
| Seconds after the PR is created | PR → **Checks** / Actions tab | The `Devin E2E trigger` workflow run posts the PR number to the hosted orchestrator at `https://devin-e2e-tester.onrender.com`. |
| ~10 s later | PR conversation | A `Devin E2E review started: https://app.devin.ai/sessions/...` comment, plus a pending `devin/e2e-review` commit status. |
| Throughout | The linked Devin session | The session boots Superset from a snapshot, checks out the PR branch, logs in, and drives the UI with computer use. This is the part worth watching. |
| Throughout | <https://devin-e2e-tester.onrender.com/dashboard> | The review row moves through `queued → session_created → running → completed`, with the session link, verdict, duration, and ACU cost. `/metrics.json` has the same aggregates. |
| ~15–20 min in | PR conversation | Devin posts its evidence comment: tested commit, test cases with pass/fail, reproduction steps, screenshots, and a recommendation. |
| At the same moment | PR → commit status | `devin/e2e-review` flips to success (`pass`) or failure (`bug_found`). |
| Only for `bug_found` | Fork's **Issues** tab | An auto-filed `[devin-e2e] Bug found in PR #N: <title>` issue with the reproduction details, linked from a short comment on the PR and from the dashboard. |

The orchestrator sleeps when idle (free Render tier), so the very first trigger
after a quiet period can take an extra ~30 s while the service wakes up. If the
dashboard shows no new row within a minute, open
<https://devin-e2e-tester.onrender.com/healthz> once and re-check.

## Alternatives considered

Two other paths would also let a reviewer trigger the system, and both are worse
than prepared branches. **Downloadable `.patch` files** (via `curl -O
<pr>.patch` and `git am`) require a local clone, working git auth for the fork,
and a push — several minutes of setup, and any mistake lands as an unreviewable
diff. **A prompt for a coding agent** ("open a PR against the fork that adds a
status tag and plants a bug in the edit path") makes the demo
non-deterministic: the diff, the claims, and therefore the verdict change on
every run, so a reviewer cannot tell an orchestrator failure from an agent that
wrote something different than expected. The prepared branches are the primary
path because they are already pushed, byte-for-byte identical for every
reviewer, and reduce the reviewer's work to opening a compare link and pasting a
body — while still exercising the real trigger (`pull_request_target` →
workflow → orchestrator → Devin), not a simulated one. The `/simulate` endpoint
remains available for anyone who wants to re-run a review against an existing PR
without opening a new one.
