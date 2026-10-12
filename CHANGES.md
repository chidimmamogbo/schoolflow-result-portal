# CHANGES.md

Every approved change to something already built: code, configuration, schema or a decision. The block is written and approved **before** the change is made (BUILD_PROMPT section 10). Newest at the bottom. Decisions themselves live in `DECISIONS.md`; the diary in `LOG.md`.

```
### CHANGE: <short title>
- Before: what existed and how it behaved
- Why it must change: the problem, bug, new requirement or risk
- When: why now (or the trigger that should make us change it later)
- What changes: files, functions, tables, migrations affected
- After: how it behaves once changed
- Proof: which tests cover it (new or updated) and the command to run them
```

---

## Recorded retroactively on 2026-10-12

These seven changes were made during Phase 4 (2026-10-11 to 2026-10-12). Chidimma approved each one in the session (step by step, option choices and the banner wording) and each passed tests and CI, but the block was not written and approved **before** the change, as the protocol requires. They are recorded here after the fact so the history is complete. From 2026-10-12 every change gets its block first.

### CHANGE: CI typecheck generates Next.js route types first (PR #4, before merge)
- Before: `bun run typecheck` ran `tsc --noEmit` only.
- Why it must change: CI failed with `Cannot find name 'LayoutProps'`; Next.js generates that type into `.next/types`, which a fresh CI machine does not have. It passed locally only because of a leftover `.next` folder.
- When: on the first CI run.
- What changes: `frontend/package.json` script `typecheck`.
- After: `next typegen && tsc --noEmit`, as the Next.js 16.4 CLI docs recommend; same result locally and in CI.
- Proof: `bun run typecheck` from a clean folder (no `.next`); CI job "Frontend".

### CHANGE: CI builds and smoke-tests the backend container (PR #5)
- Before: CI had four jobs; the `Dockerfile.vercel` image was not built in CI.
- Why it must change: D-117 requires a Docker build of `Dockerfile.vercel`; the image is what Vercel runs.
- When: when the Dockerfile was added for the staging deploy.
- What changes: `.github/workflows/ci.yml` new job "Backend image (Docker build and smoke test)".
- After: CI builds the image, checks `/api/v1/health` returns `{"status":"ok"}` and that the container is not running as root.
- Proof: CI job "Backend image".

### CHANGE: Required checks on main go from four to five (after PR #5)
- Before: branch protection on `main` required four checks.
- Why it must change: the new Backend image job must also block merges.
- When: right after the job first passed.
- What changes: GitHub branch protection, `required_status_checks` (all pinned to GitHub Actions, app 15368).
- After: five required checks, strict (branch up to date before merge).
- Proof: `gh api repos/chidimmamogbo/schoolflow-result-portal/branches/main/protection --jq '.required_status_checks'`.

### CHANGE: CI deploys the staging branch (PR #7)
- Before: CI only checked code; nothing deployed.
- Why it must change: BUILD_PROMPT Phase 4 step 6 and D-123 (deploy the skeleton to staging after CI).
- When: Phase 4, once the Vercel project and staging domain existed.
- What changes: `.github/workflows/ci.yml` new job "Deploy to staging" (pushes to `staging` only, GitHub environment `staging`).
- After: a push to `staging` runs all checks, then deploys, aliases `staging.schoolflow.meritiaa.com` and checks health.
- Proof: CI run on `staging`; `curl https://staging.schoolflow.meritiaa.com/api/v1/health`.

### CHANGE: Deploy job guards empty secrets and fixes the uv cache path (PR #8)
- Before: an empty `VERCEL_TOKEN` failed with a confusing CLI error; the uv cache path was doubled (`backend/backend/uv.lock`).
- Why it must change: the token secret was saved empty twice (Git Bash `< /dev/clipboard` gives Windows programs nothing); the cache warning hid a real misconfiguration.
- When: during the first staging runs.
- What changes: `.github/workflows/ci.yml`: new step "Check the deploy secrets are set"; `cache-dependency-glob: uv.lock`. (This PR also added `--scope` to the Vercel commands, which failed and was removed in PR #9.)
- After: an empty secret stops the job with a clear message; the uv cache works.
- Proof: CI run on `staging` ("Check the deploy secrets are set" passes); no cache warning in the Backend job.

### CHANGE: Staging alias assigned through Vercel's REST API (PR #9)
- Before: `vercel alias set` (and, briefly, `--scope`) in the deploy job.
- Why it must change: with the project-scoped token those commands fail with "User not found"; widening the token would let it reach the other projects on the account.
- When: first staging runs, 2026-10-11 (D-131).
- What changes: `.github/workflows/ci.yml`: `--scope` removed; alias step calls `POST https://api.vercel.com/v2/deployments/{url}/aliases?teamId=...` with curl.
- After: the narrow token deploys and aliases staging.
- Proof: CI run on `staging`, steps "Point the staging address at this deployment" and the health check.

### CHANGE: Staging banner and noindex (PR #12)
- Before: staging looked exactly like production and could be indexed by search engines.
- Why it must change: D-121 ("Staging" banner, noindex).
- When: Phase 4, once staging was live.
- What changes: new `frontend/src/components/staging-banner.tsx`; `frontend/src/app/layout.tsx` renders it; `frontend/src/app/globals.css` gains the two warning colour tokens; `vercel.json` gains an `X-Robots-Tag: noindex, nofollow` header for the staging host only; `ci.yml` checks both on live staging; Vercel env `APP_ENV` (Preview `staging`, Production `production`).
- After: staging shows "Staging site: test data only" (wording approved 2026-10-12) and is not indexed; production shows neither.
- Proof: `bun run test` (4 banner tests incl. never in production); CI step "Staging is marked as staging".

---

## 2026-10-12

### CHANGE: Report card template: gaps from the Nigerian report card research (approved by Chidimma, `ok`)
- Before: no Department for SSS students and no subject grouping on the report card; no Marks obtainable or highest and lowest average in class in the summary; default grade bands, affective and psychomotor traits and the trait key described but not written down; default nursery learning areas without Pre-science and Handwriting.
- Why it must change: the Ogun State and FCT UBEB formats and the vendor templates show these items; Phase 5 item 8 and AC12.1 need real formats to be reproducible (`docs/REPORT_CARD_RESEARCH.md`).
- When: before Phase 6 acceptance tests and the Phase 7 data model, so no migration is needed later.
- What changes: `docs/SPEC.md` and `design/docs/SPEC.md` (v0.5.1: F04, F05, F08 rules 5 and 6, F12 block settings, F26 rule 1, section 9 data model, section 12), `design/docs/DESIGN_BRIEF.md` 10.2, `design/NAVIGATION_AND_SETTINGS.md` (template editor switches), `DECISIONS.md` (D-135), `docs/UI_REVIEW.md` item 8.
- After: switches "Department", "Group subjects by category", "Marks obtainable", "Highest average in class", "Lowest average in class" (all off by default, so existing boards are unchanged); new schools get the written Nigerian defaults; the Ogun and FCT layouts can be reproduced with switches alone.
- Proof: AC12.1 (Phase 6) previews an Ogun-style JSS card and an FCT-style primary card with seeded fictional data; Phase 7 unit tests for summary maths and default seeds (`uv run pytest`, `bun run test`).

### CHANGE: Working pace in AGENT.md rule 1 (requested by Chidimma, 2026-10-12)
- Before: "One step at a time."
- Why it must change: Chidimma: "we are wasting lots of time so let's try to do two or three things at a time instead of our usual one" and "move to building code".
- When: from Phase 5 on; written into AGENT.md at the end of Session 4 so new sessions follow it.
- What changes: `AGENT.md` working rule 1; `MEMORY.md` fact "Pace".
- After: two or three related steps per turn; still stops for decisions, change protocol approvals, secrets and outward-facing actions.
- Proof: not code; reviewed in the session handover.

### CHANGE: Pass mark error label follows the spec (Chidimma, 2026-10-12)
- Before: approved label "Pass mark must be a whole number from 0 to 100." (NAVIGATION section 5).
- Why it must change: SPEC section 12 says 1 to 99.
- When: found while writing AT-07.5.
- What changes: `docs/UI_REVIEW.md` section 4; `docs/ACCEPTANCE_TESTS.md` AT-07.5.
- After: "Pass mark must be a whole number from 1 to 99."
- Proof: AT-07.5 (Phase 7 API test).
