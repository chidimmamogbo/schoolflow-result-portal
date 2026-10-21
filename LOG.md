# LOG.md

The day-by-day diary of the build: what we did, what changed, issues we hit and how we fixed them, test status, and the exact next step. Newest day at the top. Current state lives in `MEMORY.md`; decisions in `DECISIONS.md`; approved changes in `CHANGES.md`.

Entry template:

```
## YYYY-MM-DD (Session N)
### What we did
### What changed (files)
### Issues and fixes
### Tests
### Next step
### Blockers
### Roughly left
```

---

## 2026-10-22 (Session 5, continued)

### What we did
- **9.2d, the platform (super admin) module, test-first in one batch.** Platform routes check the super admin through the normal chain, then work through a second session as `app_platform` (D-051), which itself refuses anyone else.
- Migration 21: `platform_school_usage`, `platform_unpublished_classes`, `platform_username_taken`, `platform_email_taken`, owner-run and callable only by `app_platform` (numbers and names, never records).
- Endpoints: create school (school, features, levels from the school type, subscription, principal, `activation` and `school_setup` emails, audit; taken code, username or email refused with a field error), list, detail, edit, change code (confirmed), suspend with a reason and reactivate, resend the set-up email, usage, activity, features, levels (at least one on; confirmation naming classes with unpublished results; school type worked out), school admins and their login support (email, reset link, temporary password shown once, sign out, deactivate, reactivate, make principal), platform settings (General, Email, Billing, Security, audited), audit log, email log (status only) and payments.
- Temporary passwords: four words from EFF's short word list (`auth/temporary.py`), reusable by 9.2e.
- Defaults recorded as D-161.

### What changed (files)
- New: migration 21, `platform/{deps,schemas,settings_model,routes}.py`, `auth/temporary.py`, `auth/temporary_words.txt`, `tests/test_platform.py`.
- Updated: `settings.py` (optional `DATABASE_URL_PLATFORM`), `main.py` (includes the platform router), `tests/auth_support.py` (`build_platform_app`, `PlatformAsRole`), `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- **Two roles, one test transaction:** the platform session must see the test's uncommitted data, so tests wrap the same session and switch role and context around each platform statement (`PlatformAsRole`); production uses a real second connection.
- **Making `DATABASE_URL_PLATFORM` required** outside local would break an existing settings test (staging settings without it), so it stays optional (503 without it) until a CHANGE.
- **Lowercase school codes were refused instead of read as uppercase:** Pydantic checks the pattern before `to_upper`. Fix: uppercase in a before-validator.
- **Equal timestamps:** audit events in one test transaction share `created_at`; tests compare actions as sets.
- **Deliberate breaks:** 17. 15 caught at once. "Platform session for anyone" survived because each route's permission check refuses first; a new test calls a test route that uses only the platform session, and it now catches it. "Login support reaches any member" is redundant with row-level security (the platform role sees only school admin accounts, and an account is staff or parent, never both), so it changes nothing. The deactivate test was strengthened before the run to check that the session rows are gone.

### Tests
- Full backend suite: 1104 passed (about 8 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: BUILD_PROMPT 9.2e, school administration, test-first.

### Blockers
- None.

### Roughly left
- Phase 7: 9.2e to 9.2j2 plus reports, verify, notices, emails, billing and files. Then Phases 8 to 11.

---

## 2026-10-15 to 2026-10-21 (Session 5, continued)

### What we did
- PR #33 (9.2a, the API core) merged on Chidimma's `merge`; staging not touched.
- **9.2b and 9.2c in one batch, test-first** (Chidimma's faster pace). Migration 20: `login_throttles` and narrow owner-run functions for what happens before sign-in (find the login's account, a session's account, use up a link, queue reset and "password changed" emails, an active school's public details), callable only by `app_user`.
- `auth/`: Argon2id via pwdlib (OWASP setting), password rules (15, 10 for students, 128 at most, 9,126 common passwords blocked, different from the current one), session and CSRF tokens (hash only stored; CSRF token tied to the session), growing login delays, and the routes: login, school login page, logout, logout-all, refresh, me, change password, activate, forgot and reset. No register route.
- `authz/deps.py`: the chain (session with CSRF and Origin, membership and school active, temporary password changed, feature, permission) and route helpers (level on, not found, workflow state, separation of duties).
- Defaults recorded as D-159 and D-160 instead of questions.

### What changed (files)
- New: migration 20, `auth/{passwords,tokens,throttle,schemas,routes}.py`, `auth/common_passwords.txt`, `authz/deps.py`, `tests/{auth_support,test_auth,test_authz}.py`.
- Updated: `auth/models.py` (new `LoginThrottle` model), `main.py` (includes the auth router), `pyproject.toml` and `uv.lock` (`pwdlib[argon2]`), `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- **Argon2 too slow with pwdlib's defaults** (about 2 seconds a check here, with the CPU near 95%). Fix: OWASP's first Argon2id setting; hashes upgrade if the cost is raised later (D-159).
- **pytest would have shipped in the app:** a test helper briefly lived in `passwords.py` and imported pytest (a dev-only package). Moved to `tests/auth_support.py`.
- **Route coverage test saw no routes:** FastAPI 0.143 keeps included routers nested (`_IncludedRouter`), so `app.routes` no longer lists them. Fix: the test reads the app's OpenAPI description and calls every route without a session, expecting 401 outside the public list.
- **One failed request wiped the test's set-up:** the test override rolled back the whole session. Fix: each request gets its own savepoint.
- **Docker Desktop stuck on "starting"** twice; fixed by restarting it by hand.
- **CI dependency audit failed on PR #34:** a new advisory (GHSA-6q48-6c7w-9gw2) against `certifi` 2026.7.22, which bundled root certificates from a CA with compromised intermediate keys. Fix: `uv lock --upgrade-package certifi` to 2026.10.19 (lockfile only; `certifi` comes in through httpx). PR #34 merged on Chidimma's `merge`.
- **Deliberate breaks:** 21. 19 caught at once. "No dummy hash check" survived because the test counted calls to our own function; the test now counts real Argon2 checks inside the hasher, and catches it. "Admission number from any school" changes nothing (the account is already tied to the code's school, and a pupil record links only to an account of its own school), so it is a redundant safeguard, not a gap.

### Tests
- Full backend suite: 1076 passed (about 7 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: BUILD_PROMPT 9.2d, the platform module (super admin), test-first.

### Blockers
- None.

### Roughly left
- Phase 7: 9.2d to 9.2j2 (platform, school administration, grading set-up, results engine, score entry, rating sheets, form teacher, approval and publishing, audit, attention, plus reports, verify, notices, emails, billing and files). Then Phases 8 to 11.

---

## 2026-10-12 to 2026-10-15 (Session 5)

### What we did
- **Phase 7 started.** Step 1 (PR #18, merged): PostgreSQL 17.11 in Docker (`compose.yaml`, databases `schoolflow` and `schoolflow_test`), fail-fast settings (D-020), SQLAlchemy 2.1 + psycopg 3 engine with hidden SQL parameters, Alembic (pyproject template), a test fixture that rebuilds the test database from the migrations and rolls back every test, and migration 1 (`schools`, `school_features`, `school_levels`, `platform_settings`, D-136 four level rows).
- Chidimma chose: Claude runs branch, commit, push and PR, and stops before merge and staging.
- **D-137** (CHANGE approved): RLS and least-privilege roles arrive with every migration. Migration 2: roles `app_user`, `app_platform`, `app_verifier` (no BYPASSRLS, checked by the migration), `app_current_school_id()` and `app_current_user_id()`, RLS on migration 1's tables, `db.use_context()` setting the school and user at the start of every transaction.
- **D-138** (Chidimma's idea, CHANGE approved with 2A and 3A): one parent account across schools, linked only after the parent accepts; schools get the same response for every email; shared accounts managed only by the parent; school name on notices and emails. SPEC v0.5.2, acceptance tests AT-31.4 to AT-31.7 and AT-33.4 (133 cases, 57 denied). Option 3B (staff who are also parents) kept in MEMORY as a future upgrade.
- Migration 3: `users` and `school_memberships` with the trigger rules (super admin has no school, pupils in their own school, staff or parent, consent), the shared-account check, RLS for each role and column grants. PR #19 merged.
- Migration 4: `user_sessions` and `account_tokens` (32-byte hashes only, one live link per account and purpose, used or cancelled, never deleted by the app); a school ends sessions and issues links only for its own, unshared people; the platform only for school admins.
- Migration 5: `roles`, `permissions`, `role_permissions` (45 permissions, 66 rows) from `authz/permissions.py`, which a test compares with the SPEC section 5 table and with the database. BUILD_PROMPT 9.1 item 2 complete. PR #20 merged.
- Migration 6 (9.1 item 3): `academic_sessions` (named like 2026/2027), `terms` (three per session, one active per school, AC04.1), `classes` (a trigger refuses a level that is switched off, AC04.2, AC25.3; existing classes stay, AT-04.3), `class_arms`, `departments`, `subjects` (optional category), `arm_subjects`. Every child row repeats `school_id` with a two-column foreign key, so it can only point at its own school's rows. The platform reads sessions and terms only (billing). PR #21 merged.
- 2026-10-13: Chidimma chose three name fields for pupils (D-139) and the link request as the only method for parents with an email (D-140); SPEC v0.5.3.
- Migration 7 (9.1 item 4, first part): `students`, `guardians`, `guardian_students`, `parent_link_requests`, `enrolments`, `student_subjects`. A reusable `check_member_role()` trigger makes sure a pupil's or parent's login really is a pupil or parent of that school; a pupil only takes subjects their arm offers; moving arms adds an enrolment (the arm cannot be edited); link requests are never deleted; the platform and verification roles see no children's records. PR #22 merged.
- Approved CHANGE: the test database connection gives up after 10 seconds.
- Migration 8 (9.1 item 4, second part): `teacher_assignments` (one teacher per subject in an arm, only subjects the arm takes; one form teacher per arm; form teacher of one arm at most), `class_assistants` (at most two per arm, locked against two admins adding at once), `reviewer_scopes` (a department, or subjects and classes), and the `teacher_subjects` view for "Teaches all subjects" (subjects added later included, AC06.2; a specialist keeps their subject). BUILD_PROMPT 9.1 item 4 complete. PR #23 merged.
- Migration 9 (9.1 item 5): `grade_bands` and `remark_bands` (cover 0 to 100, checked at commit), `assessment_structures` per level and term with the mode and the lock (AC08.3, AC08.6), `assessment_components` (1 to 8, adding up to 100; none for Skill ratings; no structure for a level that is off, AT-04.2), `rating_traits` with the 1 to 5 key, `school_settings` with the pass mark (1 to 99). Spec defaults in `grading/defaults.py`. D-141 records how F08 was read. PR #24 merged.
- Chidimma decided D-142 (approve without review only when no reviewer covers the sheet), D-143 (reasons once a sheet has been submitted) and D-144 (staff who also teach get assignments; approved CHANGE). SPEC v0.5.4.
- Migration 10: `check_member_role()` accepts several roles; assignments and assistant places accept teachers, school admins and reviewers.
- Migration 11 (9.1 item 6, score sheets): `result_sheets`, `scores`, `result_revisions`, `approval_actions`. The SPEC section 8 workflow, separation of duties, completeness on submit, reasons, the structure lock on the first score and published immutability are all enforced in the database; the history tables are written only by triggers and never change.
- PR #25 merged. Chidimma approved the CHANGE "Rating sheets join the sheet workflow".
- Migration 12 (9.1 item 6a, skill ratings): `learning_areas`, `class_learning_areas`, `skills`, `rating_scales`, `rating_scale_points`, `skill_ratings`, `area_comments`. Rating sheets reuse `result_sheets` and the same workflow; a learning area row joins `teacher_assignments` (one kind per row); "Teaches all subjects" covers the class's learning areas except a specialist's; submitting needs every active skill rated (AC26.2); ratings follow the score rules (locks, reasons, authors); a scale has exactly one attention point, checked at commit. D-145 records how F26 was read.
- PR #26 merged. A probe confirmed two problems found while building 6a: a second score change was accepted under the previous change's reason, a reason could be rewritten on its own, and JSS 1 moved to Senior Secondary while it had 3 JSS sheets. Chidimma approved both CHANGEs. Migration 13: each score or rating change brings its own reason (never edited on its own), and a class keeps its level once it has sheets or learning areas.
- 2026-10-14: PR #27 merged. Chidimma decided D-146 (class sections after publication work like score sheets: Published, then reopened with a reason as a new revision; SPEC v0.5.5) and D-147 (`attention_entries` move to item 7, with publication), and approved the CHANGE giving `rating_traits` a same-school key.
- Migration 14 (9.1 item 6b): `class_report_sections` (status, revision, times school opened), `class_section_actions` (written only by the database), `student_term_entries` (form teacher's and head's comments, times present) and `student_trait_ratings`. Only the form teacher submits; returns need a comment; teacher entries lock while submitted; the head's comment can be written until publication; times present never exceeds times opened. D-148 records how F22 is stored.
- PR #28 merged. Chidimma decided D-149: the plain verification code is kept on the report document (school-only), so PDFs regenerated from the snapshot print the same QR; the verification table keeps only hashes.
- Migration 15 (9.1 item 7, with `attention_entries` from D-147): `report_templates` (versions numbered by the database, never changed), `report_documents` (snapshot, hash and masked name worked out by the database; only when every sheet of the class is published; a new revision supersedes the last; revoke needs a reason; never changed or deleted), `verification_tokens` (hashes only, written by the database) with `verify_report()`, the only thing the verification role can use, and `attention_entries` (only for a Valid report, never changed). D-150 records how these are stored.
- PR #29 merged. Chidimma decided D-151 (a correction ticket links the pupil's newer report revision when it is resolved) and approved the CHANGE linking `schools.logo_file_id` to the new `files` table.
- Migration 16 (9.1 item 8): `files` (D-057: allowed types and sizes per purpose, storage paths inside the school's folder, never changed; the platform role handles logos only), `correction_requests` (numbered per school; only while the Correction queue is on; requester a school admin, reviewer, teacher or parent, a parent only for their own ward; section 8 moves with messages; only the requester replies), `correction_events` (the timeline, written only by the database) and `correction_attachments` (one per request, by the requester while open). D-152 records how these are stored.
- PR #30 merged (a `use_alter` fix on the logo link cleared a SQLAlchemy warning about the schools, files and users loop). Chidimma decided D-153: a fourth database role, `app_sender`, sends the emails.
- Migration 17 (9.1 item 9): `notices` (only school admins post or edit; system notices may have no author and keep their text; archiving is final), `notice_audiences`, `notice_recipients` (members of the school only), `notice_reads` (people mark only their own), all never changed, and `email_outbox` (one email per recipient per event; no password, token or score keys; Queued to Sent, Failed or another attempt, at most 5; content never changes). D-154 records how these are stored.
- 2026-10-15: PR #31 merged. Chidimma asked to go faster: the last three database items in one branch and PR, with defaults recorded as decisions (D-155 to D-157) instead of questions.
- Migration 18 (9.1 items 10 and 11): `pricing_versions` and `pricing_tiers` (super admin only, numbered by the database, plans cover every count once, never changed), `school_subscriptions`, `invoices` (super admin only; arithmetic and cliff cap checked; rate from the version; Unpaid to Paid only with a succeeded payment of the exact amount, or Void with a reason; snapshot never changes), `payments` (school admin starts one for an unpaid invoice; amount copied from the invoice in NGN; one success per invoice with a numbered receipt that marks the invoice paid), `payment_events` (one row per gateway event) and `audit_events` (never changed, deleted or emptied, even by the owner; no secret keys).
- Item 12: `tests/test_audit_and_security.py` audits the whole database (RLS on every table except a short platform-level list, no app role owns anything, owner-run functions locked down, no app role can delete or empty history tables). It found one table without RLS, `platform_settings`, which is platform-level by design (migration 2) and is now on the list (D-157).
- PR #32 merged: BUILD_PROMPT 9.1 (the database) is complete.
- 9.2a, the API core (D-158): RFC 9457 errors that never echo input or quote the database, a fresh request ID per request, security headers, no CORS, docs only locally, JSON logs with redaction and route templates, a per-request database session committed before the response, `/health/ready`, and rate limits in PostgreSQL (migration 19: `rate_limit_buckets`, `rate_limit_hit()` on an HMAC of the key; client IP only from Vercel's own header). Deliberate breaks: 11, all caught after one test was strengthened (a validation error on the password itself).

### What changed (files)
- New: `compose.yaml`, `backend/docker/initdb/`, `backend/alembic.ini`, `backend/migrations/` (3 migrations), `backend/src/schoolflow_api/{settings,db,models}.py`, `schools/`, `platform/`, `accounts/` models, `backend/tests/{conftest,db_support,factories}.py` and tests for settings, database, migrations, schools, tenant isolation and accounts.
- Updated: `backend/pyproject.toml`, `uv.lock`, `backend/.env.example`, `.github/workflows/ci.yml` (Postgres service), `docs/SPEC.md` and its design copy (v0.5.2), `docs/ACCEPTANCE_TESTS.md`, `DECISIONS.md` (D-136 to D-138, D-044 amended), `CHANGES.md` (three blocks), `MEMORY.md`.

### Issues and fixes
- PostgreSQL error text can quote values; `hide_parameters` only hides SQLAlchemy's part. The 9.2a error handler must never log raw database errors (MEMORY).
- A reused connection returns `''` (not NULL) for the school setting after a transaction; `''::uuid` would crash. The helpers use `nullif`, proven by a test that fails without it.
- Consent rule first fired for staff too; the migration round-trip test caught a wrong drop order; `Result.tuples()` deprecation. All fixed before commit.
- Long inline scripts in the shell failed to parse; scripts now go in a file first.
- 2026-10-13: the test run hung because Docker Desktop's engine had stopped overnight. `docker desktop restart` brought it back; the database volume was intact (still on migration 6).

### Tests
- Backend: 1026 passed on Postgres 17.11 (about 11 minutes locally); Ruff, format and strict Pyright clean; `alembic check` finds no drift; deliberate breaks of each rule (169 in total) each made tests fail. CI green on PRs #18 to #32.

### Next step
- 9.2a is on `feat/phase7-api-skeleton`; PR open, waiting for `merge`.
- After `merge`: 9.2b (auth) and 9.2c (authorization chain) in one batch, test-first.

### Blockers
- None.

### Roughly left
- Phase 7: the 9.2 modules (auth, platform, school admin, results, reports, verification, portal, notices, billing). Then Phases 8 to 11.

---

## 2026-10-12 (Session 4)

### What we did
- `backend/.env.example` and `frontend/.env.example` with setting names only (PR #11).
- Staging marked as staging (D-121), test-first: `StagingBanner` component ("Staging site: test data only", wording chosen by Chidimma), shown only when `APP_ENV` is exactly `staging`; `X-Robots-Tag: noindex, nofollow` header for the staging host only in `vercel.json`; Vercel env `APP_ENV` (Preview `staging`, Production `production`); CI checks both on live staging (PR #12).
- `README.md` with the "All rights reserved" notice (D-111), the "Stack and commands" section in `AGENT.md`, and `CHANGES.md` (PR #13).
- **Phase 4 complete.** Re-reading BUILD_PROMPT: Phase 4 ends at step 7 (CLAUDE.md/AGENT.md). The production deploy job belongs to Phase 11, after the Phase 10 security gate ("We do not deploy to production until every item passes"). Earlier notes listing it as a Phase 4 item were wrong.
- **Phase 5** (faster pace, 2 or 3 steps per turn): `docs/UI_REVIEW.md` with the route-to-board coverage table (13 demo pages without a board, 6 on one-theme v0.3 boards), decisions D-132 to D-134, all five NAVIGATION section 5 label groups approved with fixes (teacher menu "Result sheets"), role journeys, the Phase 5 checklist and content for the pages without a board. Item 8: no real cards had been given to the designer; online research (`docs/REPORT_CARD_RESEARCH.md`) found the Ogun State and FCT UBEB formats but no six complete real cards; approved CHANGE adds the missing switches and defaults (SPEC v0.5.1, D-135).
- **Phase 6 complete:** `docs/ACCEPTANCE_TESTS.md`, the 38 demo steps as 128 given/when/then cases (54 denied cases), fixtures, and a table covering all 44 BUILD_PROMPT Phase 6 items. Pass mark label changed to 1 to 99. AGENT.md rule 1 now allows two or three steps per turn.

### What changed (files)
- New: `backend/.env.example`, `frontend/.env.example`, `frontend/src/components/staging-banner.tsx` and its test, `README.md`, `CHANGES.md`, `docs/UI_REVIEW.md`, `docs/REPORT_CARD_RESEARCH.md`, `docs/ACCEPTANCE_TESTS.md`.
- Spec v0.5.1 (`docs/SPEC.md`, `design/docs/SPEC.md`), `design/docs/DESIGN_BRIEF.md`, `design/NAVIGATION_AND_SETTINGS.md`, `DECISIONS.md` D-132 to D-135. PRs #11 to #16 merged; Phase 6 is PR #17.
- Updated: `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css` (two warning tokens from `tokens.css`), `frontend/.gitignore`, `vercel.json`, `.github/workflows/ci.yml`, `AGENT.md` (production deploy moved from "later in Phase 4" to Phase 11), `MEMORY.md`, `LOG.md`.

### Issues and fixes
- **Change protocol skipped seven times in Phase 4** (CI, branch protection and staging changes were approved step by step in the session, but no CHANGE block was written first). Fix: recorded retroactively in `CHANGES.md`; every change to something already built now gets its block and Chidimma's `ok` first.
- **`vercel env add` asks Secret or Config:** `APP_ENV` is not secret, so Config.

### Tests
- Backend: 2 passed. Frontend: 6 passed (page 2, banner 4). Lint, format, types and audits clean.
- CI: 5 checks green on `main`; staging deploy green, including health, noindex header and banner checks. Production (`*.vercel.app`) shows neither banner nor noindex.

### Next step
- New session. Phase 7, step 1: Postgres 17 in Docker, settings, SQLAlchemy and Alembic wiring, database test fixture, then migration 1 (schools, school_features, school_levels, platform_settings), test-first. Optional: real report cards from schools Chidimma knows.

### Blockers
- None.

### Roughly left
- Phases 1 to 6 done. Left: 7 (backend), 8 (frontend), 9 (end to end), 10 (security gate), 11 (production deploy and demo), then build-after-the-core items. Phases 7 and 8 are the bulk.
- Reminders: renew the Vercel token before 2026-11-10; remove the D-130 ignore once `braces` is patched; watch CI after 2026-10-19 (Ubuntu 26 runners); re-check Vercel image storage after several deploys.

---

## 2026-10-09 to 2026-10-11 (Session 3)

### What we did
- Phase 4 tools: pre-commit 4.6.2 (uv tool), Vercel CLI 63.1.0 (Bun); GitHub CLI 2.102.0 was already installed.
- Git: `git init -b main`, local identity with the noreply email, `.gitignore`, `.gitattributes` (LF), pre-commit with gitleaks v8.30.1 and pre-commit-hooks v6.0.0 (red test with a fake token, green on real files). First commit `c1353b1`.
- GitHub: public repo `chidimmamogbo/schoolflow-result-portal`; secret scanning and push protection on; Dependabot alerts and security fixes on; `main` protected (PR, 0 approvals, admins included, linear, squash only, delete branch on merge, then 5 required checks pinned to GitHub Actions).
- Backend scaffold (uv, Python 3.14, FastAPI 0.143): `GET /api/v1/health` test-first (red, then green), pytest warnings as errors, httpx2, Ruff, strict Pyright.
- Frontend scaffold (Next.js 16.4.0, React 19.3, Bun): home page h1 and tab title test-first, Vitest 5 + Testing Library, Prettier + Tailwind plugin, eslint-config-prettier, `typecheck` = `next typegen && tsc --noEmit`, Node 24 pinned (`.nvmrc`, engines).
- CI (`.github/workflows/ci.yml`): gitleaks full history, pre-commit repo checks, backend (Ruff, Pyright, pytest, uv audit), backend image (Docker build, health smoke test, non-root), frontend (Prettier, ESLint, tsc, Vitest, build, bun audit). All actions pinned to commit SHAs.
- Vercel: project `schoolflow-result-portal` (Services: Next.js + FastAPI container in `lhr1`), GitHub connected, `.vercelignore` allowlist, domain `staging.schoolflow.meritiaa.com` (CNAME in cPanel), staging deploy job in CI. Staging is live and deployed automatically on pushes to `staging`.
- Decisions D-130 (audit ignore for one dev-only advisory) and D-131 (staging deploy design).

### What changed (files)
- New: `.gitignore`, `.gitattributes`, `.pre-commit-config.yaml`, `.nvmrc`, `.vercelignore`, `vercel.json`, `.github/workflows/ci.yml`, `backend/` (pyproject, uv.lock, src, tests, Dockerfile.vercel, .dockerignore), `frontend/` (Next.js app, tests, configs).
- Updated: `DECISIONS.md` (D-130, D-131), `docs/SERVICES.md` (repo, Vercel project, staging DNS, token expiry), `MEMORY.md`, `LOG.md`.
- Pull requests #1 to #9 merged into `main`; `staging` branch created and fast-forwarded.

### Issues and fixes
- **Starlette deprecation warning** (httpx with TestClient): Starlette 1.7.0's own code prefers `httpx2`. Fix: added httpx2 as a dev dependency; made pytest treat warnings as errors.
- **Vitest worker timeout on the first run** (60 s): cold start. Each piece loaded fine in isolation; later runs start in about 10 s.
- **`vite-tsconfig-paths` notice:** Vite 8 resolves tsconfig paths natively; switched to `resolve.tsconfigPaths` and removed the plugin.
- **`frontend/.gitignore` `.env*` ignored `.env.example`:** added `!.env.example`.
- **CI type check failed (`LayoutProps` not found):** types are generated by Next.js; CI had no `.next`. Fix: `next typegen && tsc --noEmit` (Next.js 16.4 CLI docs).
- **Frontend audit: GHSA-vfj7-8cjw-p6xm** in `braces` (dev-only, no patch). Fix: ignore that one ID with a recorded reason (D-130).
- **`vercel link` appended `.env*` to the root `.gitignore`,** which hid every `.env.example`. Fix: restored the committed `.gitignore`.
- **Vercel's default upload list skips `.env.local` but not `.env`, and skips `.dockerignore`.** Fix: `.vercelignore` allowlist (simulated: 22 files, no env files).
- **First deployment was labelled Production** although it came from a feature branch. Later CLI deploys are Preview. Cause not confirmed.
- **`VERCEL_TOKEN` saved empty twice:** Windows programs (`gh`) receive nothing from `< /dev/clipboard` in Git Bash. Fix: `cat /dev/clipboard | gh secret set ...`, length check first, plus a CI step that fails clearly on an empty secret. Two tokens deleted and replaced; one was briefly pasted into the terminal and was deleted in Vercel.
- **Alias failed with "User not found":** a project-scoped token cannot use `vercel alias set` or `--scope`. Fix: assign the alias with the REST API (D-131).
- **HTTPS certificate for staging** was only issued after the first alias attached a deployment to the name.
- **uv cache path doubled** (`backend/backend/uv.lock`): `cache-dependency-glob` is relative to `working-directory`. Fix: `uv.lock`.

### Tests
- Backend: 2 passed (health OK, POST denied). Ruff clean, Pyright strict 0 errors, uv audit clean.
- Frontend: 2 passed (single h1, tab title). Prettier, ESLint, tsc clean; bun audit clean with one documented ignore.
- CI: all 5 checks green on `main`; staging deploy green; `https://staging.schoolflow.meritiaa.com/api/v1/health` returns `{"status":"ok"}`.

### Next step
- Phase 4 remaining: `.env.example` files with names only, staging `X-Robots-Tag: noindex` and "Staging" banner (D-121), root `README.md` (with the "All rights reserved" notice, D-111), the "Stack and commands" section in `AGENT.md`, `CHANGES.md`. Then a `production` GitHub environment locked to `main` and the production deploy job.

### Blockers
- None. Renew the Vercel deploy token before 2026-11-10.

### Roughly left
- Phase 4: the docs and env items above, plus the production pipeline. Then Phases 5 to 11 and the build-after-the-core items; Phases 7 and 8 are the bulk.

---

## 2026-10-09 (Session 2)

### What we did
- Phase 2 Round 1 (Frontend): presented ten decisions; Chidimma approved all (D-001 to D-011).
- Chidimma added: React Icons may be used where lucide-react lacks an icon (recorded in D-004).
- Chidimma asked whether to use Redis to cache repeat requests such as "get result". Answered: not in the MVP; browser cache + private ETags + indexed Postgres snapshots instead. Approved as D-012.
- Round 2 (Backend) presented and approved (D-013 to D-021).
- Chidimma set a budget rule: **free resources only** (Vercel Hobby, Hobby cron, Neon Free and so on) until real schools onboard. Recorded as D-00A.
- Checked Neon regions (no Africa region; nearest are London `aws-eu-west-2` and Frankfurt `aws-eu-central-1`), Neon Postgres versions (14 to 18) and Vercel function regions (Hobby: one region, selectable). Presented Round 3 (Database).
- Created this LOG.md.

- Chidimma asked "Why Neon, and what happens when I start having users?" Checked Neon's plan page: Free gives 100 CU-hours a month (about 400 hours awake at 0.25 CU); over the limit the compute is suspended until next month; over 1 GB storage, writes fail (no data deleted); 6-hour restore. Conclusion: Free is fine for build and demo, not for real schools (results week could hit the compute limit). Growth path: Neon Launch (no minimum; $0.106/CU-hour, $0.35/GB-month; 7-day restore), roughly $5 to $25 a month for first pilots, or move to any Postgres host with `pg_dump`, since we use no Neon-only features. To verify in Phase 3: whether upgrading keeps data in place.
- Chidimma asked "Neon vs Render, same thing?" Explained: Render is a hosting platform that also offers Postgres; Neon is only Postgres. Render Free Postgres (checked) expires after 30 days and is deleted after 14 more, has no backups and no pooling, so Neon wins for free use.
- Round 3 (Database) approved and recorded (D-022 to D-031), including the Neon growth path.
- Checked OWASP Authentication and Password Storage cheat sheets and the FastAPI security tutorial for Round 4. Presented Round 4 (Authentication).
- Round 4 approved with Chidimma's choices: password option C (15 staff and parents, 10 students; recorded as an accepted risk against OWASP's 15-without-MFA guidance) and accounts option A (one school per account). Recorded D-032 to D-044. Presented Round 5 (Authorization).
- Round 5 approved and recorded (D-045 to D-053). Checked Vercel Blob private storage docs (Python SDK `vercel` >= 0.5.0 supports private stores; OIDC auth on Vercel; blobs served through our own authorised route). Presented Round 6 (File storage).
- Round 6 approved and recorded (D-054 to D-059); closes the spec's open question "store PDFs or regenerate" (regenerate). Presented Round 7 (PDF).
- Found that the approved report card designs (`design/screens/Report*.dc.html`, 7 files) are HTML, which supports the HTML-to-PDF choice. Round 7 approved and recorded (D-060 to D-070). Presented Round 8 (QR verification).
- Read the `Verify` and `VerifyAfter` designs: they show 8-character codes (about 40 bits). Recommended 12 characters (about 60 bits); Chidimma chose option B. Recorded D-071 to D-077 and added an "approved differences from the design" list to MEMORY.md. Presented Round 9 (Email and notice board).
- Chidimma asked whether every school can have its own email like admin@greenfield.com. Answered: now, school name as sender name plus the School email as Reply-To (free, works with Gmail addresses); later, a paid "custom sending domain" add-on (school-owned domain with DNS records; Resend Free allows only 3 domains). Never spoof a school's address; never store school mailbox passwords. Round 9 approved and recorded (D-078 to D-086). Presented Round 10 (Payments and billing) with the cliff-protection numbers worked out.
- Verified the pricing numbers with a small Python script (scratchpad, not in the repo): all AC19.2, AC19.3 and AC19.4 values match. Round 10 approved and recorded (D-087 to D-097). Presented Round 11 (Testing).
- Round 11 approved and recorded (D-098 to D-106).
- Checked installed tools (Node 24.21.0, npm 11.19.0, Python 3.14.7, uv 0.12.16, Git 2.55.0, Docker 29.8.0, WSL Ubuntu, VS Code 1.139.1; no pnpm, no `gh`), Vercel Node versions (24.x default, 22.x, 20.x) and GitHub Free limits (2,000 Actions minutes a month for private repos; no protected branches on private Free repos; secret scanning free for public repos). Presented Round 12 (Development tools) with a public-or-private repo question.
- Chidimma chose **Bun** instead of npm (Bun 1.4.2 installed) and asked for any reason not to. No blocking reason: Vercel detects `bun.lock` (checked); Node stays the runtime; Vitest stays the test runner (`bun run test`, not `bun test`). Chidimma chose a **public repo**. Round 12 recorded (D-107 to D-118).
- Checked Sentry's free plan (5,000 errors, 1 user, 30-day lookback, 5M spans) and Vercel's `git.deploymentEnabled`. Round 13 (Deployment, logging, monitoring) presented, approved and recorded (D-119 to D-129).
- Wrote the one-page **Stack Summary** at the end of `DECISIONS.md`. **Chidimma gave final approval. Phase 2 complete.**
- Phase 3 started: created `docs/SERVICES.md` (7 required services in order, credentials map, onboarding-day upgrades, do-not-register list). Presented service 1: GitHub.
- **Service 1 GitHub done:** account `chidimmamogbo`, 2FA on, recovery codes saved, private commit email `288715556+chidimmamogbo@users.noreply.github.com` (to set in git config in Phase 4). Presented service 2: Vercel.
- **Service 2 Vercel done:** Chidimma already had a Vercel account with 2 deployed projects and asked if a new account is needed. Answer: no, reuse it. Caveats: Hobby usage limits are shared across all projects in the account (check the Usage page); a Vercel token can reach all projects, so the Phase 4 deploy token gets a short expiry and lives only in GitHub Actions secrets; the project can be moved to a Pro team later. Presented service 3: Neon (direct Neon account, not the Vercel Marketplace integration, so Vercel never receives the database owner credentials).
- Ran the region latency test from Chidimma's laptop (`curl` connect time to AWS endpoints, 5 tries each): London about 0.165 s and steady; Frankfurt 0.148 to 0.384 s and unsteady. London confirmed (D-025 updated).
- **Service 3 Neon done:** project `schoolflow`, Postgres 17, AWS Europe West 2 (London), default branch `production`. Vercel account name `Chidimma`, usage low.
- Looked up `meritiaa.com` public DNS: managed in Namecheap shared hosting cPanel; existing website (A `66.29.146.24`) and Namecheap email (MX jellyfish.systems) in use; root SPF present; no DMARC. Set the rule: only add subdomain records. Presented service 4 (DNS) with recommended names `schoolflow.`, `staging.schoolflow.`, `mail.`.
- Chidimma confirmed Namecheap 2FA and Zone Editor access, and noticed `mail.meritiaa.com` already exists. Checked: it points to the hosting server `66.29.146.24` (cPanel's automatic mail hostname for her mailbox). **Issue:** using it for SchoolFlow sending would mix two jobs (replies bouncing to the shared host, risk of cPanel cleanup removing our records). **Fix:** recommended `notify.meritiaa.com` for Resend instead (unused); `schoolflow.` and `staging.schoolflow.` also unused.
- Chidimma asked whether to create records for the app subdomains now. Answered: no; names only for now. App CNAMEs are added in Phase 4 with Vercel's exact values (avoids dangling records); Resend records come in service 5.
- **Service 4 DNS done:** names confirmed `schoolflow.meritiaa.com`, `staging.schoolflow.meritiaa.com`, `notify.meritiaa.com`. Updated D-079 (sending subdomain `notify.`, Resend region Ireland) and D-121 (domain names). Checked Resend docs (subdomain recommended; regions us-east-1, eu-west-1, sa-east-1, ap-northeast-1; records shown on the domain's Records tab; API keys shown once and can be domain-restricted). Presented service 5: Resend.
- Resend account created; domain `notify.meritiaa.com` added (Ireland). Resend's records: DKIM TXT `resend._domainkey.notify`, SPF via CNAMEs `rsend.notify` → `rsend-euw1.forge.rmta.net` and `send.notify` → `send.forge.rmta.net`, DMARC TXT named `_dmarc`. **Issue:** Resend's DMARC name `_dmarc` would land on the root domain (`_dmarc.meritiaa.com`), breaking the "never touch root" rule. **Fix:** add DMARC as `_dmarc.notify` instead (receivers check the subdomain first; root email unchanged). Gave exact cPanel Zone Editor entries with checks for the double-domain name trap and TXT quoting.
- Chidimma added the 4 records. Checked with `nslookup` via Google DNS (8.8.8.8) and `dns1.namecheaphosting.com`: DKIM value matches exactly, both CNAMEs correct, DMARC on `_dmarc.notify` correct; root SPF and Google verification record unchanged; no root DMARC. Asked Chidimma to click Verify in Resend.
- **Service 5 Resend done:** `notify.meritiaa.com` shows Verified. Presented service 6: Paystack (test mode only; no compliance documents; keys copied in Phase 4).
- **Issue:** Chidimma's Paystack login is an existing registered business account (meritiaa) whose webhook is already in use. Sharing it would mean overwriting or competing for its single test/live webhook URLs, sharing secret keys, and mixing transactions. **Fix:** add a separate **SchoolFlow** business under the same login (Paystack supports several businesses per user; each has its own keys and webhooks; new businesses start in test mode). meritiaa stays untouched. Fallback: separate account with a different email.
- **Service 6 Paystack done:** SchoolFlow business added under the same login, test mode, test webhook empty. Presented service 7: Sentry (EU data storage, server-side scrubbing on, projects created in Phase 4).
- **Service 7 Sentry done:** organisation `Meritia`, EU data storage, Data Scrubber, Default Scrubbers and Prevent Storing of IP Addresses on.
- Chidimma asked whether a new session will remember everything. Answered: no built-in conversation memory; continuity comes from `CLAUDE.md` (auto-loaded, imports `AGENT.md` and `MEMORY.md`), my project memory notes, and reading `LOG.md` at session start. Start Claude Code in the project root; `claude --continue` reopens the same conversation.
- **Phase 4 started.** Step 1: install GitHub CLI. Checked: winget 1.29.380 available; GitHub CLI not installed.
- Installed GitHub CLI with `winget install --id GitHub.cli -e --source winget`. **Issue:** `gh --version` said "command not found". **Cause:** the install succeeded (gh 2.102.0 at `C:\Program Files\GitHub CLI\`, already on the machine PATH), but open terminals keep the PATH they started with; a VS Code terminal inherits VS Code's old PATH. **Fix:** fully close and reopen VS Code / Git Bash (or `export PATH="$PATH:/c/Program Files/GitHub CLI"` for the current shell). Confirmed by running the full path: `gh version 2.102.0 (2026-09-30)`.
- **Phase 3 complete.** Filled the credentials map in `docs/SERVICES.md` with planned variable names (no values). No secrets have been copied anywhere yet; keys are created or copied in Phase 4 straight into `.env` files, Vercel and GitHub secrets.

### What changed (files)
- `DECISIONS.md` created: D-000 (Vercel preference), D-001 to D-011 (Round 1), D-012 (caching, no Redis).
- `LOG.md` created.
- `MEMORY.md` updated with Round 1 status.

### Issues and fixes
- **Two file edits were briefly blocked** by a temporary failure of the tool's automatic safety check (no verdict returned). Fix: retried once and both succeeded; nothing was lost.
- **A shell command hung for 2 minutes** while writing the pricing check script: `cat > file || cat > other <<EOF` left the first `cat` waiting for keyboard input, because the heredoc only belonged to the second `cat`. Fix: stopped the background task, wrote the script with the editor instead, and ran it with a timeout. Lesson for later commands: one heredoc per `cat`, and add `timeout` to quick checks.

### Tests
- No code yet. (Pricing numbers checked by a throwaway script.)

### Next step
- Phase 4, step 1: install the missing tools one at a time with version checks (GitHub CLI, pre-commit via `uv tool`, Vercel CLI via Bun), then `git init`, git identity with the noreply email, create the public repo, scaffold.

### Blockers
- None.

### Roughly left
- Phases 1 to 3 done. Left: Phase 4 (install, scaffold, CI, staging skeleton), 5 (UI review), 6 (acceptance tests), 7 (backend), 8 (frontend), 9 (end to end), 10 (security gate), 11 (deploy and demo), then build-after-the-core items. The building phases (7 and 8) are the bulk of the work.

---

## 2026-10-08 (Session 1)

### What we did
- Read `docs/BUILD_PROMPT.md`, `docs/SPEC.md` (v0.5), the MVP document, the capstone proposal, `design/README.md` and `design/CLAUDE_CODE_PROMPT.md`.
- Section 15 step 1: OS confirmed as Windows 11 Pro; Chidimma chose **Git Bash** for commands.
- Section 15 step 2: summarised the MVP scope in 20 bullets plus the out-of-scope list; accepted.
- Created `AGENT.md` (rules for any agent), `MEMORY.md` (project state) and `CLAUDE.md` (imports both).
- Phase 1: wrote `docs/RESEARCH_TECH.md` (22 topics plus a Vercel section) with dated sources.
- Chidimma stated a preference for **Vercel** over Render; research rebuilt around Vercel.

### What changed (files)
- `AGENT.md`, `MEMORY.md`, `CLAUDE.md`, `docs/RESEARCH_TECH.md` created.

### Issues and fixes
- **Paystack pricing and webhook pages returned 403 to automated reading.** Fix: used Paystack's support article (cap of ₦2,000, ₦100 waived under ₦2,500) and marked the 1.5% rate "to verify" by hand.
- **Brevo pricing page loaded without plan details.** Fix: used third-party 2026 summaries and marked them "to verify".
- **Vercel Hobby is non-commercial only.** Fix: noted that we move to Pro before a school pays; final call in Round 13.
- **Vercel Hobby cron runs only once a day,** too slow to drive an email outbox. Fix: proposed a Postgres outbox triggered through Vercel Queues, with a daily cron sweep as a safety net.
- **WeasyPrint needs the Pango system library,** which Vercel's plain Python runtime cannot install. Fix: proposed running FastAPI as a Vercel container service (Dockerfile with `apt-get`).
- `design/docs/SPEC.md` and `docs/SPEC.md` looked like duplicates. Fix: hash check confirmed they are identical.

### Tests
- No code yet.

### Next step
- Phase 2 Round 1 (Frontend). (Done in Session 2.)

### Blockers
- None.
