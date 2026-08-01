# Superset pull request E2E review

You are autonomously E2E-testing a UI pull request.

- Repository: `$repo`
- Pull request: `$pr_url`
- Title: `$title`
- Description: `$body`
- Head branch: `$head_branch`
- Head SHA: `$head_sha`

Check out the PR branch in `RichardHruby/superset`. Start the backend with
`docker compose -f docker-compose-image-tag.yml up -d superset`. Ensure
`docker/.env-local` contains `SUPERSET_LOAD_EXAMPLES=no` and a development secret
key. Start the frontend development server from this branch in `superset-frontend`.
Log in as `admin` / `admin`, derive test cases from the PR description, and test
the changed UI using computer use with screen recording. Post detailed findings,
including screenshots, as a comment on this pull request on the fork.

Finish by emitting only this structured JSON verdict:
`{"verdict":"pass|bug_found|error","bugs":[],"summary":"...","fix_pr_url":null}`
