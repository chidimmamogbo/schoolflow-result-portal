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

## 2026-10-23 and 2026-10-24 (Session 5, continued): Next.js advisories, 9.2i part 2b, 9.2j, 9.2j2

### What we did
- Chidimma accepted D-170 and asked that no two pupils ever share a report ID; done in PR #44 (numbered IDs, IDs kept across revisions).
- CI's audit failed on three new Next.js advisories (two critical, one high, published 2026-10-22). CHANGE approved; PR #45 moved Next.js to 16.4.2. Both PRs merged on `merge`; staging not touched.
- **Reopen and republish**, test-first: a school admin reopens chosen sheets or the class sections with a reason (optionally naming an open correction request); republishing issues new revisions only for pupils whose report changed, keeps report IDs, tells only those pupils, their parents and the staff.
- **Students needing attention** (`/attention`, CSV export) by subject, student and learning area, scoped by role; parents and students refused.
- **Audit timeline** (`/school/audit`) for school admins with filters and pages.
- Found while reading the labels file: five template defaults from PR #44 differ from `design/NAVIGATION_AND_SETTINGS.md` section 3 (CHANGE proposed, waiting for `ok`). Defaults recorded as D-171. No migration.

### What changed (files)
- New: `reports/attention.py`, `audit/routes.py`, `tests/test_republishing.py`, `tests/test_attention.py`, `tests/test_audit_timeline.py`.
- Updated: `reports/publication.py` (readiness for republish, changed-only reports, reopen), `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- Long heredocs failed again in the Bash tool; edit scripts went to the scratchpad through the Write tool.
- A correction request test used the wrong pupil (the database refused it: parents report only on their own children).
- Audit events in one test transaction share a time, so the timeline test picks events by action.
- **Deliberate breaks:** 39; 35 caught at first. Fixed: a closed correction request case, a learning area specialist in the skills test, and one break that could not happen (removed by simplifying readiness). One survives by design: row-level security already hides other schools' audit events, and the query's own school filter is a second guard.

### Tests
- Full backend suite: 1226 passed (about 15 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge` and the CHANGE answer: report PDFs, public verification and the parent and student portal, test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2i part 2a

### What we did
- PR #43 (9.2h2) merged on Chidimma's `merge`; staging not touched.
- Publication split in two: 2a now (templates, readiness, principal's comments, publish, revoke, list of reports); 2b next (reopen and republish, attention views, audit timeline).
- **Report templates**, test-first: versioned per level, settings checked against a fixed shape (footer always shown and last, no way to hide the report ID or QR code, unknown settings refused), Score or Skills card by the level's mode, core styles only, defaults until a school saves one.
- **Publishing**, test-first: readiness as plain sentences, the principal's comments, then one transaction that publishes sheets and sections, freezes a snapshot per pupil with a report ID (`GMC-2627-T1-JSS1A-014`) and a 12-character verification code, records Students needing attention, posts one notice to the class's audience only and queues score-free emails. Revoke needs a reason.
- Defaults recorded as D-170. No migration.
- Chidimma accepted D-170 (2026-10-23) and asked that no two people in a class ever share a report ID: IDs now get `-2`, `-3` when still in use, skip IDs other pupils of the school hold this term, and are kept across revisions. New test with 5 clash cases; 6 of 6 breaks caught after one more case (an ID cut right after a dash).

### What changed (files)
- New: `reports/templates.py`, `reports/publication.py`, `tests/test_publication.py`.
- Updated: `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- Ruff wanted shorter lines and Pyright a typed list of averages; fixed before the breaks.
- **Deliberate breaks:** 21; 20 caught at first. Revoking twice was still refused by the database, so the test now asks for the app's own `wrong_status` code; then 21 of 21.

### Tests
- Full backend suite: 1214 passed (about 13 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2i part 2b (reopen and republish, attention views, audit timeline), test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2h2

### What we did
- PR #42 (9.2h1 and 9.2i part 1) merged on Chidimma's `merge`; staging not touched.
- **9.2h2, My class**, test-first: my classes (form teachers and assistants; others 403), the class view (times opened, each pupil's comment, times present and absent, trait ratings, average and suggested comments from the remark bands, counts), the broadsheet (subjects with sheet status and engine totals, or learning areas for Skill ratings), attendance days, pupil entries (checked: present within opened, ratings 1 to 5 on active traits, 300-character comments), preview ("Preview, not published"), submit (form teacher only) and the admin's return with a comment.
- Defaults recorded as D-169 (submit does not check completeness; publication does, by template). No migration.

### What changed (files)
- New: `form_class/routes.py`, `tests/test_form_class.py`.
- Updated: `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- A leftover `if False else` around two copies of a query was removed before the first run.
- Before the breaks a test was added for admins (read only, cannot submit, return only submitted sections) and a Skill ratings broadsheet; after the breaks a check that an assistant can open the arm.
- **Deliberate breaks:** 15; 14 caught at first, one test strengthened, then 15 of 15.

### Tests
- Full backend suite: 1206 passed (about 14 minutes locally, the machine was busy). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2i part 2, publication, test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2h1 and 9.2i part 1

### What we did
- PR #41 (9.2h) merged on Chidimma's `merge`; staging not touched.
- 9.2i split: publishing needs the form teacher's sections (9.2h2), so this batch is rating sheets plus the sheet moves; publication, reopen and revoke come after 9.2h2.
- **Rating sheets** (`/rating-sheets`): my rating sheets by assignment (class teachers who teach all subjects, area teachers, assistants), open, grid of pupils by the area's active skills with the school's scale, save ratings and comments all or nothing.
- **Moves** (`/sheets/{id}/submit|return|review|approve`) for both kinds, the reviewer's queue (`/reviews`) and a read-only view of a sheet in scope, and the school admins' overview (`/school/sheets`). The database's section 8 rules (transitions, completeness, comments, D-052 separation, D-142 review first) stay the final word.
- Defaults recorded as D-168. No migration.

### What changed (files)
- New: `results/rating_sheets.py`, `results/workflow.py`, `tests/test_ratings_and_workflow.py`.
- Updated: `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- A test re-sent an unchanged rating after submission (nothing to refuse); it now sends a different point.
- Pyright needs `Field(default_factory=list[RatingCell])`, not a bare `list`, for typed defaults.
- Before and after the breaks, tests were added for: approving a draft, a class-scoped reviewer covering rating sheets, opening a rating sheet at a Scores level, and a teacher reading another class's rating sheet.
- **Deliberate breaks:** 16; 14 caught at first, two missing tests added, then 16 of 16.

### Tests
- Full backend suite: 1199 passed (about 12 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2h2 form teacher tools, then publication (9.2i part 2), test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2h

### What we did
- On `merge`: PR #39 (9.2f) merged, PR #40 (9.2g) updated from `main` (the notes files conflicted; both sides kept), CI green again, merged. Staging not touched.
- **9.2h, score entry and import**, test-first: my sheets by assignment (subject teachers, form teachers who teach all subjects, assistants on their arm), opening a draft (saving the term's structure if missing), the grid (structure's columns, only pupils taking the subject, totals, grades and flags from the engine, counts), saving scores all or nothing with reasons after a submission, CSV template, import preview and commit, error file, export. School admins read every sheet but enter only where they teach.
- Defaults recorded as D-167. No migration.

### What changed (files)
- New: `results/sheets.py`, `tests/test_score_entry.py`.
- Updated: `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- Submitting in a test needs every score (the database checks completeness); the test fills the sheet first.
- Before and during the breaks, tests were added for: blank CSV cells and repeated cells, pupils who moved arms, a level switched off, a Skill ratings level, and a school admin opening a sheet for a subject she does not teach.
- **Deliberate breaks:** 17. 15 caught at first; one break's search text no longer matched after formatting (checked by hand: caught), and "open any subject" survived for teachers because the request rolls back, but would have let a school admin create sheets; the new test catches it. 17 of 17.

### Tests
- Full backend suite: 1190 passed (about 12 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2h1 rating sheets and 9.2i approval workflow, test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2g

### What we did
- PR #39 (9.2f, grading set-up) opened, CI green. Chidimma said `continue` (not `merge`), so #39 stays open and 9.2g was built on its own branch from `main` (the engine does not depend on #39). MEMORY.md and LOG.md on `main` will catch up when #39 merges (its docs entry for 9.2f is in that PR).
- **9.2g, the results engine**, test-first: pure functions for totals, grades, positions with ties, averages (half up, ties on exact values), missing and out-of-range flags, duplicates, a whole class's subject and overall results, and the calculation version. Added Hypothesis (D-098) for property tests.
- Defaults recorded as D-166.

### What changed (files)
- New: `results/engine.py`, `tests/test_results_engine.py`.
- Updated: `pyproject.toml` and `uv.lock` (Hypothesis 6.170.5, dev only), `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- **Deliberate breaks:** 12. 9 caught at once; three tests were missing and are now added: an average exactly on a half (0.125 rounds to 0.13), two pupils whose averages both show 60.38 but differ (60.385 places above 60.375), and the pass mark itself passing (40 passes, 39 does not). Then 12 of 12.
- A test helper made an exam score of -1 for a total of 39; it now fills the columns in order.
- Engine tests use no database, so they ran alongside the full suite.

### Tests
- Full backend suite: 1162 passed before the three new tests (17 minutes this time, the machine was busy); engine tests 19 passed, 100% line and branch coverage.

### Next step
- After `merge` of #39 and this PR: 9.2h, score entry and import, test-first.
## 2026-10-22 (Session 5, continued): 9.2f

### What we did
- PR #38 (9.2e part 2b and the logo CHANGE) merged on Chidimma's `merge`; staging not touched. 9.2e is complete.
- **9.2f, grading set-up**, test-first: defaults copied once on first use (bands for all four levels, pass mark 40, 13 traits and the 1 to 5 key, the five-point rating scale, Nursery's ten learning areas when Nursery is on); grading bands and remark bands per level covering 0 to 100; pass mark 1 to 99; traits and key; assessment structures per level and term (1 to 8 components adding up to 100 with the difference shown, none for Skill ratings, next term once locked, the latest earlier structure suggested); learning areas, skills, classes' areas; the rating scale with exactly one attention point, keeping points' ids.
- Defaults recorded as D-165. No migration: the existing tables, grants and rules were enough.

### What changed (files)
- New: `grading/setup.py`, `school/grading.py`, `tests/test_grading_setup_api.py`.
- Updated: `main.py`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- A test sent an empty band list to check the level rule, which validation refused first; it now sends a valid set.
- Before the breaks, three tests were added or strengthened: the earlier structure offered for a new term, a school without Nursery gets no learning areas, and scale points keep their ids.
- The break script now restores each file's exact bytes (no line-ending noise).
- **Deliberate breaks:** 15. 14 caught at once; "defaults copied again" survived because the test did not check the second request's status (the failed request rolled back, so the counts matched); now it does, and catches it.

### Tests
- Full backend suite: 1158 passed (about 11 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2g, the results engine (pure functions), test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2e part 2b and the logo CHANGE

### What we did
- PR #37 (9.2e part 2a) merged on Chidimma's `merge`; staging not touched.
- Chidimma approved the CHANGE for a public school logo on the login page; recorded in `CHANGES.md` and built first: migration 23 (`auth_school_logo`, logos only), `GET /auth/schools/{code}/logo` (rate limited, public caching, ETag), `logo_url` filled on the school page, an eighth public route.
- **9.2e part 2b, pupils and parents**, test-first: pupils (register, search, edit, status, enrol in the active session with the arm's subjects, change subjects, move arms with history, login slips) and CSV import (preview with row problems, commit all or nothing, template). Parents: guardians with wards, link requests that look the same for every email (D-140, option 2A), slips only without an email, pause, resume and remove the school's own link, resend and cancel requests. Migration 24: the signed-in parent lists, accepts and declines requests sent to their own verified email; staff and pupils never can.
- Defaults recorded as D-164.

### What changed (files)
- New: migrations 23 and 24, `school/{pupils,guardians}.py`, `parents/{__init__,routes}.py`, `tests/test_pupils_and_parents_api.py`.
- Updated: `auth/routes.py` and `authz/deps.py` (the logo CHANGE), `main.py`, `tests/test_auth.py` and `tests/test_authz.py` (logo tests, eighth public route), `CHANGES.md`, `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- The files trigger names the uploader from the signed-in user; the logo test sets the context before inserting files.
- An expiry before creation breaks a database rule; the expiry test moves both dates.
- Before the breaks, a test was added for AT-31.7 (a teacher cannot answer a request sent to their email).
- The break script rewrote migration 23 with Windows line endings (same content); restored from git.
- **Deliberate breaks:** 17, all caught.

### Tests
- Full backend suite: 1147 passed (about 9.5 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2f, grading set-up (with learning areas, skills and the rating scale), test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2e part 2a

### What we did
- PR #36 (9.2e part 1) merged on Chidimma's `merge`; staging not touched.
- 9.2e part 2 split again: **2a staff and uploads** (this), 2b pupils and parents; learning areas, skills and the rating scale move to 9.2f.
- Staff: create teachers and reviewers (activation email or slip), edit names and emails, list. Assignments: subject, learning area or form teacher (optionally teaching all subjects), assistants (two per arm at most), reviewer scopes. Ids from other schools are not found; arms at levels that are off are refused; the database's rules come back as 409 with their names.
- Uploads: logo, signature, stamp; type from the first bytes, 1 MB, Pillow re-save from pixels only (no EXIF or GPS), 1200 px; school folder; logo set at once; downloads for the school's own people with private caching and an ETag. `FileStorage` with a local folder (now git-ignored); Blob comes with the first staging deploy of uploads.
- Defaults recorded as D-163. Added `pillow` 13.0.0.

### What changed (files)
- New: `school/staff.py`, `files/{storage,images,routes}.py`, `tests/test_staff_and_uploads.py`.
- Updated: `main.py` (two routers), `pyproject.toml` and `uv.lock` (Pillow), `.gitignore` (`backend/.local-storage/`), `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- psycopg cannot run two statements with parameters in one call; a test now uses one update.
- Every API test passed first time, so two gaps were closed before the breaks: a test that correction attachments are not served by the school files route, and a test that local storage never leaves its folder.
- **Deliberate breaks:** 14, all caught.

### Tests
- Full backend suite: 1129 passed (about 10 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2e part 2b, pupils and parents, test-first.

### Blockers
- None.

---

## 2026-10-22 (Session 5, continued): 9.2e part 1

### What we did
- PR #35 (9.2d, the platform module) merged on Chidimma's `merge`; staging not touched.
- 9.2e split in two PRs to keep each reviewable. **Part 1, a school sets itself up**, test-first: school settings (contacts and colour only), assessment mode and head's title per level (a mode change waits for next term once entries started), sessions and terms (no overlaps, terms inside their session, one active term), classes and arms at levels that are on, departments, subjects and the subjects each arm takes, additional admins (principal only, platform limit, activation email or slip), and login support for the school's own people (never the principal, never yourself, never a shared account).
- Migration 22: column grants and a school-admin trigger so `app_user` can edit exactly these school and level columns. Shared helpers `audit/log.py` and `emails/queue.py`. Defaults recorded as D-162.

### What changed (files)
- New: migration 22, `school/{__init__,schemas,routes,people}.py`, `audit/log.py`, `emails/queue.py`, `tests/test_school_setup.py`.
- Updated: `main.py` (two routers), `DECISIONS.md`, `MEMORY.md`, `LOG.md`.

### Issues and fixes
- A PL/pgSQL `case` that reads `new.id` or `new.school_id` fails on a table without one of them; replaced with `if`.
- Pyright now flags `@contextmanager` on a function typed `Iterator`; typed `Generator` instead.
- Every API test passed first time, so two gaps were closed before the breaks: a database-level test for migration 22's trigger (the API's permission check stops teachers first), and the deactivate test now checks that the session rows are gone.
- **Deliberate breaks:** 16, all caught.

### Tests
- Full backend suite: 1116 passed (about 10.5 minutes locally). Ruff, format and strict Pyright clean.

### Next step
- After `merge`: 9.2e part 2, people, test-first.

### Blockers
- None.

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
