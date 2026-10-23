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

## Phase 7

### CHANGE: Backend gets database libraries, CI gets a Postgres 17 service, env names for migrations and tests (Chidimma `ok`, 2026-10-12)
- Before: `backend/pyproject.toml` depends only on `fastapi[standard]`; the CI "Backend" job runs pytest with no database; `backend/.env.example` lists `DATABASE_URL`, `DATABASE_URL_PLATFORM`, `DATABASE_URL_VERIFIER` and says migration credentials live only in GitHub secrets.
- Why it must change: Phase 7 step 1 needs fail-fast settings (D-020), SQLAlchemy 2 + psycopg 3 (D-017), Alembic (D-023) and tests on real Postgres in CI (D-030). Without a database in CI the first database test fails every pull request.
- When: now, the first database code.
- What changes: (1) `backend/pyproject.toml` and `uv.lock`: pydantic-settings>=2.15.0, sqlalchemy>=2.1.4, psycopg[binary]>=3.3.6, alembic>=1.20.0 (PyPI, checked 2026-10-12); (2) `.github/workflows/ci.yml` "Backend" job: a `postgres:17.11-trixie` service with a health check and throwaway CI-only env values; (3) `backend/.env.example`: `DATABASE_URL_MIGRATIONS` (owner role, Alembic only, local and CI/deploy, never on Vercel) and `TEST_DATABASE_URL`, comment reworded.
- After: `uv sync` installs the database stack; `uv run pytest` runs against real Postgres locally and in CI; still five required checks.
- Proof: `uv run pytest` (settings and database fixture tests, red then green); CI "Backend" job green on the PR.

### CHANGE: Row-level security and least-privilege roles are built with each migration, starting now (Chidimma `ok`, 2026-10-12)
- Before: BUILD_PROMPT 9.1 puts RLS, the app database role and immutability last (item 12). Migration 1's tables have no RLS; `db.py` has no tenant setting; tests run as the owner (a superuser), which skips RLS.
- Why it must change: if RLS waits until item 12, every module is written and tested as a role that skips RLS; switching it on at the end would break untested queries and hide missing policies.
- When: now, before the first accounts table exists.
- What changes: a new migration creates the roles `app_user`, `app_platform` and `app_verifier`, the `app_current_school_id()` helper, and RLS policies and grants on `schools`, `school_features`, `school_levels` and `platform_settings`; `db.py` gets a per-transaction hook that sets `app.school_id` from the session; `tests/db_support.py` gets a helper to run test queries as `app_user` or `app_platform`. Item 12 becomes the final audit, with a test that fails if any table with `school_id` lacks RLS (D-137).
- After: every new school table ships with its RLS policies and denied-case tests; a connection with no school sees nothing.
- Proof: `tests/test_tenant_isolation.py` (role attributes, own school only, no leak between pooled connections, school users cannot write platform data, RLS inventory); `uv run pytest`.

### CHANGE: Parent accounts can be linked to several schools with the parent's consent (amends D-044) (Chidimma `ok`, 2026-10-12, options 2A and 3A)
- Before: D-044 option A, one school per account. With D-033 (emails unique across the platform), a parent with children in two SchoolFlow schools needs a second account with another email, or none.
- Why it must change: Chidimma, 2026-10-12: one email and one login per parent, all their children visible across SchoolFlow schools, and every notice and email shows which school sent it.
- When: now, before the account tables (migration 2) and login (9.2b) are built.
- What changes: D-138 amends D-044 (parents only, consent, shared-account protections); D-033 stays. SPEC v0.5.2: sections 4, 8, 9, 12, 14, 16 and 19, F03 (rules 8 and 9, AC03.7 to AC03.10), F07, F14 (AC14.2), F17 (AC17.3), F18 (AC18.2); `design/docs/SPEC.md` copied. Acceptance tests AT-31.4 to AT-31.7 and AT-33.4, with Ikenna Obi also linked by BSA to Kosi Obi. Step 2 schema: memberships with a status, one per school per account; non-parents limited to one school; the per-transaction hook also sets `app.user_id`.
- After: one parent account shows every linked child, grouped by school. Each school sees and manages only its own link. Once an account is shared, only the parent manages its login details.
- Proof: step 2 database tests run as `app_user` (memberships, consent, shared-account protections, isolation); auth and provisioning API tests later; the new acceptance tests.

### CHANGE: Pupil name fields and the parent login method (Chidimma, 2026-10-13, D-139 and D-140)
- Before: the Add student design has one "Name" box; SPEC F03 rule 4 lets every create form offer an activation email or a temporary password, parents included.
- Why it must change: Nigerian records sort by surname and the verify page masks the first name and surname separately (D-139); under D-138 option 2A a slip for a parent with an email would reveal whether that email already uses SchoolFlow (D-140).
- When: now, before the `students` and `guardians` tables are built (BUILD_PROMPT 9.1 item 4).
- What changes: SPEC v0.5.3 (F03 rule 4, F05, section 9) and its design copy; DECISIONS D-139 and D-140; MEMORY lists the Add student form as an approved difference from the design; the `students` table gets `surname`, `first_name`, `other_names`.
- After: pupils have three name fields; a parent with an email is always added through the link request, and slips are only for parents without an email.
- Proof: `tests/test_pupils_and_parents.py` (name fields, link requests); provisioning API tests when F03 is built.

### CHANGE: The test database connection gives up after 10 seconds (Chidimma `ok`, 2026-10-13)
- Before: `tests/conftest.py` connected to the test database with no time limit; with Docker Desktop's engine stopped, `uv run pytest` hung for minutes.
- Why it must change: a stopped database should fail at once with the existing message ("Start it from the repo root with: docker compose up -d --wait").
- When: 2026-10-13, after the engine stopped overnight; done at the start of step 4b.
- What changes: `tests/conftest.py` only: the test connection gets `connect_timeout=10`.
- After: with the database unreachable, pytest stops after about 20 seconds (libpq tries twice) and prints how to start it.
- Proof: a run against an unreachable address printed the message after 22 seconds; the normal suite stays green.

### CHANGE: Staff who also teach, approving without a reviewer, and when a score change needs a reason (Chidimma, 2026-10-13, D-142 to D-144)
- Before: only accounts with the teacher role could hold teacher assignments or assistant places (migration 8); SPEC section 8 let a school admin approve only Reviewed sheets; F09 rule 4 asked for a reason for every change of a saved score.
- Why it must change: principals, vice principals and HODs often teach (AT-14.3 expects "a school admin who also teaches"); BSA has no reviewers yet demo step 32 has its head teacher approve submitted sheets; a reason for every draft edit is heavy for teachers entering marks over several days.
- When: now, before result sheets and scores are built (BUILD_PROMPT 9.1 item 6).
- What changes: a new migration lets `check_member_role()` accept a list of roles and makes the assignment and assistant login rules accept teacher, school admin and reviewer (constraint names `teacher_assignments_teacher_id_is_staff`, `class_assistants_assistant_id_is_staff`); `tests/test_staff_assignments.py` updated to match (denied cases now use a parent's login); SPEC v0.5.4 (section 5 note, F06 rule 1, F09 rule 4, section 8, section 19) and its design copy; DECISIONS D-142 to D-144.
- After: school admins and reviewers can be given subjects, form classes or assistant places and act as teachers on those sheets only; separation of duties still stops them reviewing or approving what they submitted; a sheet no reviewer covers can be approved straight from Submitted; reasons are required once a sheet has been submitted at least once.
- Proof: updated `tests/test_staff_assignments.py`; new tests for result sheets and scores (approval without review, separation of duties, reasons).

### CHANGE: Rating sheets join the sheet workflow (Chidimma `ok`, 2026-10-13, item 6a)
- Before: `result_sheets` had a `learning_area_id` column with no link and no rating checks (migration 11 planned it for 6a); `teacher_assignments` held subject rows and form teacher rows only (migration 8); the `teacher_subjects` view and the submit checks in `check_sheet_transition()` covered subjects only.
- Why it must change: F26 rules 3 and 4: one rating sheet per learning area per class or arm, "assigned like subjects (usually to the class teacher)", on the same workflow, review, approval and revisions as score sheets; submission needs every skill rated (AC26.2).
- When: now, with the skill rating tables (BUILD_PROMPT 9.1 item 6a).
- What changes (one new migration, nothing that has run is edited): `result_sheets.learning_area_id` gets its same-school link and a rating sheet's area must be assigned to the arm's class; `teacher_assignments` gets a third kind of row, a learning area in an arm (exactly one kind per row; one teacher per area per arm); the `teacher_subjects` view gains `learning_area_id`, and "Teaches all subjects" also covers the class's learning areas except an area given to a specialist; `check_sheet_transition()` checks the assigned teacher and that every pupil of the arm has a rating for every skill before a rating sheet is submitted. `tests/test_staff_assignments.py` follows the renamed row-kind rule.
- After: rating sheets follow exactly the same moves, comments, separation of duties and revisions as score sheets; skill ratings follow the score rules (locked once submitted, a reason after a return or reopen, an author on each).
- Proof: `tests/test_skill_ratings.py`; `tests/test_result_sheets.py` and `tests/test_staff_assignments.py` stay green.

### CHANGE: Each score or rating change brings its own reason (Chidimma `ok`, 2026-10-13, before item 6b)
- Before: once a sheet has been submitted, `check_score()` (migration 11) and `check_skill_rating()` (migration 12) refused a change with no reason (D-143), but accepted whatever reason was already on the row. A probe on 2026-10-13: after Musa's CA2 went from 12 to 14 with "Corrected transcription error", a second change to 15 with no reason of its own was accepted under the old reason, and the reason was then rewritten on its own ("Rewritten later") with the score unchanged.
- Why it must change: the audit trail would show a reason nobody gave for that change, or a reason edited after the fact; corrections are what head teachers and parents need to trust.
- When: now, before the results API (9.2) writes scores and before the audit trail (item 11) reads reasons.
- What changes: new migration 13 replaces `check_score()` and `check_skill_rating()`: a reason counts only if it comes with the change (repeating the stored reason counts as giving none), and a reason cannot change on its own (new rules `scores_reason_comes_with_a_change` and `skill_ratings_reason_comes_with_a_change`). First-draft changes still need no reason. Area comments are not affected.
- After: every change after a submission carries the reason given with it, and reasons cannot be edited later. Trade-off (the same as reviewer comments): the same words twice in a row for the same cell are refused, so the teacher rewords them.
- Proof: new tests in `tests/test_result_sheets.py` and `tests/test_skill_ratings.py` (a second change without its own reason, a reason edited on its own, first draft still free), red first: `cd backend && uv run pytest tests/test_result_sheets.py tests/test_skill_ratings.py -q`.

### CHANGE: A class keeps its level once results work has started (Chidimma `ok`, 2026-10-13, before item 6b)
- Before: a school could change a class's level; migration 6 only checks that the new level is switched on. The rules that match sheets and learning areas to a level run only when those rows are added. A probe on 2026-10-13 moved JSS 1 to Senior Secondary while it had 3 JSS score sheets.
- Why it must change: a moved class's sheets keep the old level's structure and grading, and its learning areas belong to another level, with nothing to flag it.
- When: now, while the result tables are new and before any screen offers a level change.
- What changes: migration 13 adds a trigger on `classes`, rule `classes_level_fixed_once_used`: the level can change only while no arm of the class has a result sheet and the class has no learning areas.
- After: JSS 1 cannot move once it has a sheet; Nursery 2 cannot move once it has a learning area; a class set up on the wrong level can still be fixed before results work starts.
- Proof: new tests in `tests/test_result_sheets.py` (a class with sheets keeps its level) and `tests/test_skill_ratings.py` (a class with learning areas keeps its level; a class nothing uses can still move), red first; same command as above.

### CHANGE: Rating traits get a same-school key (Chidimma `ok`, 2026-10-14, item 6b)
- Before: `rating_traits` (migration 9) had no `UNIQUE (id, school_id)`, so other tables could link to a trait only by its id.
- Why it must change: a pupil's trait ratings must point at a trait of the same school; the project's pattern is the two-column link `(trait_id, school_id)`, which needs that unique pair.
- When: now, with the trait ratings table (BUILD_PROMPT 9.1 item 6b).
- What changes: migration 14 adds `UNIQUE (id, school_id)` to `rating_traits` (and the same line in `grading/models.py`); nothing else.
- After: no change in behaviour (ids were already unique); trait ratings can only point at their own school's traits.
- Proof: `tests/test_class_sections.py` (a rating that points at another school's trait is refused); `tests/test_grading_and_assessment.py` stays green.

### CHANGE: The school logo links to the files table (Chidimma `ok`, 2026-10-14, item 8)
- Before: `schools.logo_file_id` (migration 1) had no link; its comment said the files table and its link would arrive with file storage.
- Why it must change: a logo must point at a real file of the same school, never another school's file.
- When: now, as the `files` table arrives (BUILD_PROMPT 9.1 item 8, D-057).
- What changes: migration 16 adds a foreign key from `(logo_file_id, id)` to `files(id, school_id)` (and the same line in `schools/models.py`); nothing else.
- After: a school's logo can only be one of that school's own files, and a file in use as a logo cannot be deleted.
- Proof: `tests/test_corrections.py` (a school pointing its logo at another school's file is refused); `tests/test_schools_schema.py` stays green.

### CHANGE: A public route serves the school's logo for the login page (Chidimma `ok`, 2026-10-22, 9.2e part 2b)
- Before: `GET /auth/schools/{code}/public` returned code, name and colour with `logo_url` always empty (D-159), and logos were served only to signed-in members through `GET /files/{id}` (D-163). `PUBLIC_ROUTES` (D-160) listed seven routes.
- Why it must change: F02 rule 2 and AT-09.6: the school's own login link (`/login/GMC`) shows the school's name and logo before anyone signs in; D-056 already planned "School logos only through the public school endpoint".
- When: now, with the first uploads merged (PR #37).
- What changes: migration 23 adds `auth_school_logo(code)` (owner-run, callable only by `app_user`), which returns the storage key, type and hash of an active school's logo and nothing else; a new public route `GET /auth/schools/{code}/logo` (rate limited per IP like the school page) serves it with `Cache-Control: public, max-age=3600` and an ETag; `school_public` fills `logo_url` when a logo exists; `PUBLIC_ROUTES` and its test gain this eighth route. Signatures, stamps and attachments stay private.
- After: the login page can show the logo of an active school to anyone who knows its code (the code is printed on login slips, and the name is already public on that page); a suspended or unknown school, or a school without a logo, answers 404.
- Proof: new tests in `tests/test_auth.py` (logo served, 304 with the ETag, no logo, suspended, unknown, a signature is never served here) and the updated public-route test in `tests/test_authz.py`.

### CHANGE: Upgrade Next.js to 16.4.2 for three security advisories (Chidimma `ok`, 2026-10-23)
- Before: `frontend/package.json` pinned `next` and `eslint-config-next` at 16.4.0.
- Why it must change: advisories published 2026-10-22 affect Next.js 16.0.0 to 16.4.0: GHSA-2464-fhr4-w9xw and GHSA-673q-mjm6-r5xr (critical, unauthenticated remote code execution) and GHSA-p3m5-59mp-jv5r (high, denial of service with Server Actions). CI's `bun audit` failed on PR #44 and would fail every PR.
- When: now, before merging anything else.
- What changes: `next` and `eslint-config-next` move to 16.4.2 (16.4.1 is the first patched release; 16.4.2 was the latest patch, released 2026-10-15); `bun.lock` updated; nothing else.
- After: `bun audit` finds no vulnerabilities (one documented ignore, D-130); the frontend skeleton behaves the same.
- Proof: `bun run format:check`, `lint`, `typecheck`, `test` (6 passed), `build` and `audit` locally, then the five required checks in CI.
