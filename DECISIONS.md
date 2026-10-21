# DECISIONS.md

Every significant decision, with the reason and the alternatives we rejected. Decisions are made in Phase 2 rounds (BUILD_PROMPT section 6) and approved by Chidimma. To change one later, use the change protocol (BUILD_PROMPT section 10) and add a new entry that supersedes the old one; never rewrite history here.

Research behind these choices: `docs/RESEARCH_TECH.md`.

---

## D-000. Hosting preference: Vercel

| | |
|---|---|
| Date | 2026-10-08 |
| Status | Preference stated; final hosting decision in Round 13 |
| Decision | Deploy on Vercel rather than Render |
| Reason | Chidimma's preference; native home for Next.js; Services can serve Next.js and FastAPI on one domain |
| Alternatives rejected | Render (Chidimma prefers Vercel) |
| Consequences | Hobby plan is non-commercial only, so move to Pro ($20 per developer seat per month, checked 2026-10-08) before a school pays; Hobby cron runs only once a day; PDF system libraries need a container service |

## D-00A. Free resources only until real schools onboard

| | |
|---|---|
| Date | 2026-10-09 |
| Status | Approved (Chidimma) |
| Decision | Build, stage and demo entirely on free tiers: Vercel Hobby (including Hobby cron, Queues, Blob), Neon Free, Resend Free, Paystack test mode, and free tooling. Upgrade a resource only when we start onboarding real schools |
| Reason | MVP and capstone stage; no revenue yet |
| Consequences | Every design must work within free limits: daily-only cron (outbox drained by Queues, cron is just a daily safety sweep); Resend 100 emails per day (outbox stays queued and sends the rest next day); Neon 1 GB storage and 6-hour restore window (add our own `pg_dump` backups); Blob 1 GB; Hobby keeps 1 hour of runtime logs; one function region. Upgrade list kept in `docs/SERVICES.md` for onboarding day (Vercel Pro is required then anyway, since Hobby is non-commercial) |

---

## Round 1: Frontend (approved 2026-10-09)

### D-001. Framework: Next.js App Router
- **Reason:** current direction of Next.js; server components send less JavaScript to low-cost phones; nested layouts fit the dashboard shell; native on Vercel.
- **Rejected:** Pages Router (familiar, but new features and docs centre on the App Router); Vite + React SPA (everything in the browser, heavier on cheap phones).

### D-002. Language: TypeScript, strict mode
- **Reason:** catches type mistakes before runtime; on Chidimma's training path.
- **Rejected:** JavaScript.

### D-003. Styling: Tailwind CSS mapped to the design tokens
- **Reason:** Tailwind colour names point at the CSS variables in `design/design-system/tokens.css` (for example `bg-surface` is `var(--surface)`), so there are no hard-coded hex values and dark mode switches with `data-theme`. `tokens.css` stays the single source of design values.
- **Rejected:** plain CSS modules porting `sf.css` (all responsive and accessible patterns by hand); CSS-in-JS (awkward with server components).

### D-004. Components: shadcn/ui (Radix primitives), restyled to the design
- **Reason:** accessible sidebar, sheet (drawer), dialog, tabs, tooltip and menus; the code lives in our repo so it matches the screens exactly.
- **Icons:** lucide-react (shadcn's default set) first; **React Icons allowed where lucide lacks an icon the design needs** (Chidimma, 2026-10-09).
- **Rejected:** MUI (Material look to undo); Mantine (separate theming system beside our tokens).

### D-005. Theme: next-themes
- **Reason:** sets `data-theme` on `<html>` before first paint (no flash of the wrong theme), matching `tokens.css`; Light, Dark and System; only the non-sensitive theme choice is stored on the device. Print and PDFs always use light values.
- **Rejected:** a hand-written theme script; storing the theme on the server (not needed for the MVP).

### D-006. Fonts: next/font
- **Reason:** serves Inter from our own domain, so the Content Security Policy needs no Google Fonts exception and visitors avoid an extra request. Report card fonts (Inter, Merriweather, Nunito) are bundled with the PDF backend.
- **Rejected:** the Google Fonts `@import` in `tokens.css` (kept in the design file, not used by the app).

### D-007. Responsive strategy: mobile first
- Base styles for 320px phones, then Tailwind breakpoints `sm` 640, `md` 768, `lg` 1024, `xl` 1280.
- Wide tables become cards on phones (the `sf.css` `.rt` pattern); the score grid is one card per student on phones.
- Sidebar becomes a drawer and dialogs become bottom sheets on phones; touch targets at least 44px.
- Playwright checks 360, 768 and 1440px with no sideways page scroll.
- The prototype's `data-device` switch is a design-canvas device only; the app uses CSS breakpoints.

### D-008. Forms: React Hook Form + Zod, with FastAPI Pydantic as the authority
- **Reason:** fast with large forms (score grid, Create school); inline errors for user experience. The server's Pydantic validation is the real gate; the browser is never trusted. Zod schemas may later be generated from the OpenAPI schema to prevent drift.
- **Rejected:** plain React state (messy at grid scale); Server Actions only (would add a second backend layer beside FastAPI).

### D-009. State management: no global library
- Server data lives in the data-fetching cache; UI state in React state; the signed-in user from `/auth/me` in one React context.
- **Rejected:** Redux, Zustand (solve a problem we do not have yet).

### D-010. Data fetching and API client
- Server components for first load; **TanStack Query** in client components (caching, refetch, retries).
- One typed `apiClient`: sends the session cookie, adds the CSRF token on state-changing requests, maps FastAPI's error format to readable messages, redirects to `/login` on an expired session.
- Request and response types generated from FastAPI's OpenAPI schema with `openapi-typescript`.
- Same domain through Vercel Services (`/api/*`), so cookies are first-party and no CORS setup is needed.
- **Rejected:** `fetch` alone (no caching or retries on interactive screens); SWR (fewer mutation features).

### D-011. Route guards
- One `layout.tsx` per role area (`/platform`, `/school`, `/teacher`, `/review`, `/parent`, `/student`) checks `/auth/me` and redirects when the user does not belong there or must change their password first. This is for user experience only; the server is the real gate.

---

### D-012. Caching repeat requests: no Redis in the MVP (approved 2026-10-09, was P-001)
- **Raised by Chidimma:** "Can we use Redis to cache requests like get result that a user asks multiple times in one session?"
- **Decision:** three layers instead of Redis:
  1. TanStack Query cache in the browser (repeat views in one session never reach the server);
  2. `Cache-Control: private` plus an ETag (content hash) on immutable published reports, so repeat requests get a `304 Not Modified`;
  3. indexed Postgres lookups of precomputed published snapshots.
- **Why not Redis yet:** a cache outside Postgres sits outside row-level security, and one wrong cache key could leak a school's results to another school; cache invalidation is error-prone while sheets move through the workflow; an extra service and account (Upstash on the Vercel Marketplace; free tier not verified).
- **Revisit when:** a measured slow endpoint cannot be fixed with an index, or traffic grows; the first likely use is rate limiting rather than result caching. Review in Round 13.

---

## Round 2: Backend (approved 2026-10-09)

### D-013. Framework: FastAPI
- **Reason:** on Chidimma's training path; Pydantic validation built in; automatic OpenAPI; runs on Vercel.
- **Rejected:** Django + DRF (built-in auth does not fit school-code login; heavy); NestJS (new language for the backend; weaker PDF and data tooling).

### D-014. Language: Python 3.12 or newer
- Exact version pinned in Round 12 after checking library support (WeasyPrint needs 3.10+; Vercel offers 3.12 default, 3.13, 3.14).

### D-015. API architecture
- REST under `/api/v1`; same domain as the frontend through Vercel Services (no proxy through Next.js, no CORS, first-party cookies).
- One error format based on RFC 9457 Problem Details, with a stable `code` and field `errors`; no internal details or stack traces to clients.
- Lists use `page` and `page_size` with a fixed maximum; filter names follow the spec.
- Another school's records return 404, never 403 (AC01.2).
- Code organised by feature module (`router.py`, `service.py`, `schemas.py`, `models.py`); results and pricing engines are pure functions with no database or HTTP code.

### D-016. Validation: Pydantic everywhere, unknown fields rejected
- Every request model uses `extra="forbid"`; business rules live in the service layer with tests.

### D-017. Database access: SQLAlchemy 2.x, sync, psycopg 3, separate Pydantic schemas
- **Reason:** full SQL for row-level security, triggers and locking; database models and API shapes are separate classes so sensitive fields cannot leak; sync code is simpler to learn and keeps per-transaction `set_config` straightforward.
- **Rejected:** SQLModel (one class as table and schema makes leaks easier); async SQLAlchemy (more complexity than our scale needs).

### D-018. Authentication wiring: FastAPI dependency chain
- `current_session → current_user → school_membership → feature_enabled → level_enabled → permission → ownership/scope` on every protected route.
- A test fails if any non-public route lacks the authentication dependency. Public routes are an explicit list (login, school public info, activate, forgot and reset password, verify, payment webhook, health).
- The authentication method itself is decided in Round 4.

### D-019. Background work: Postgres outbox + Vercel Queues + daily cron sweep
- The outbox table is the source of truth, written in the same transaction as the triggering action; Vercel Queues (Python SDK `vercel-queue`) delivers; the Hobby daily cron sweeps anything left queued. Also used for bulk class PDFs.
- **Rejected:** FastAPI `BackgroundTasks` for email (serverless functions may be frozen after the response, losing work); Celery + Redis (adds Redis, see D-012).

### D-020. Configuration: pydantic-settings, fail fast
- The app refuses to start with missing or invalid settings; debug mode and `/docs` only in development.

### D-021. Logging and request basics
- Structured JSON logs with a redaction filter (passwords, tokens, scores, personal data); a request ID on every log line and error; security headers on every response; rate limits stored in Postgres (in-memory limits fail across serverless instances).

---

## Round 3: Database (approved 2026-10-09)

### D-022. Engine: PostgreSQL 17
- **Reason:** row-level security, triggers, transactions, rich constraints; same major version locally, in CI and on Neon. Version 18 considered later once library support is checked (Round 12).
- **Rejected:** MySQL (no row-level security); MongoDB (relational, transaction-heavy model).

### D-023. Migrations: Alembic
- Autogenerated table changes are reviewed by hand; RLS policies, roles and immutability triggers are hand-written SQL in migrations. A migration that has run is never edited; fixes are new migrations.
- **Rejected:** raw SQL files only (no diffing); Prisma Migrate (TypeScript backend).

### D-024. Hosting: Neon Free, then Neon Launch on onboarding day
- One Neon project with `production` and `staging` branches.
- **Reason:** plain Postgres (no lock-in), no expiry, scale to zero, branches, Vercel Marketplace integration.
- **Free limits (checked 2026-10-09):** 100 CU-hours a month (about 400 hours awake at 0.25 CU), then compute suspends until next month; 1 GB storage, then writes fail; 6-hour restore window.
- **Growth path:** Free is for build, staging and demo only. Before the first real school: Neon Launch (no minimum; $0.106 per CU-hour, $0.35 per GB-month, up to 7-day restore; roughly $5 to $25 a month for the first pilots), or move to any Postgres host with `pg_dump` and restore. Use no Neon-only features (no Neon serverless driver, no Neon Auth). To verify in Phase 3: whether upgrading keeps data in place.
- **Rejected:** Supabase Free (500 MB, paused after a week of inactivity, no automatic backups); Render Free Postgres (expires after 30 days and is deleted 14 days later, no backups, one per account, no pooling).

### D-025. Region: London
- Neon `aws-eu-west-2` with Vercel functions in `lhr1` (Hobby allows one region); Frankfurt (`aws-eu-central-1` + `fra1`) as the alternative. Neon offers no African region. Confirm with a latency test from Chidimma's connection in Phase 3, because a Neon project's region cannot be changed later.
- **Confirmed 2026-10-09:** TCP connect times from Chidimma's connection, 5 tries each: London 0.156 to 0.180 s (steady, about 0.165 s); Frankfurt 0.148 to 0.384 s (unsteady, median about 0.25 s). London chosen.

### D-026. Connections and roles
- Pooled connection string for the app; direct connection string for migrations.
- Roles: `owner` (migrations only), `app_user` (runtime; not table owner; no `BYPASSRLS`), optional `app_verifier` (public verification lookups only).

### D-027. Tenant context per transaction
- `set_config('app.school_id', :id, true)` inside every transaction; a test proves the setting never leaks between pooled connections.

### D-028. Primary keys: random UUIDs
- `gen_random_uuid()`; human-readable numbers (admission number, report ID) are separate columns.

### D-029. Immutability in the database
- Triggers reject `UPDATE` and `DELETE` on published snapshots and audit events, and `app_user` has no `UPDATE` or `DELETE` grant on them (AC11.1).

### D-030. Local and test database: PostgreSQL 17 in Docker
- Docker Desktop on Windows (WSL 2); a fresh database per test run; CI uses the same version; never SQLite.
- **Rejected:** native Windows installer (version drift, harder resets); a Neon branch for tests (needs internet, slower, uses free compute hours).

### D-031. Backups
- A `pg_dump` script and a restore test into a scratch database before the demo; automation decided in Round 13.

---

## Round 4: Authentication (approved 2026-10-09)

Sources checked 2026-10-09: OWASP Authentication, Password Storage, Session Management and CSRF cheat sheets; FastAPI security tutorial.

### D-032. Custom authentication in FastAPI
- **Reason:** per-school student usernames found by school code, no sign-up, role-dependent resets and "super admin resets school admins only" do not fit managed providers; keeps users inside our database and row-level security; free.
- **Rejected:** Clerk, Auth0, Supabase Auth.

### D-033. Usernames and identifier lookup
- Format: 3 to 30 characters, lowercase letters, numbers, dot, underscore, hyphen; no `@`; suggested from the name, editable.
- Unique: staff, parent and super admin usernames platform-wide; student usernames and admission numbers per school; emails platform-wide, case-insensitive.
- Staff and parents tab: identifier with `@` is looked up as email, otherwise username. Student tab: school code, then username or admission number inside that school only.

### D-034. Generic login errors with equal timing
- One message for wrong school code, username, password, deactivated or throttled account (wording from `design/NAVIGATION_AND_SETTINGS.md`). A dummy hash check runs when the account does not exist. The "school paused" message appears only after a correct password.

### D-035. Password hashing: Argon2id via pwdlib
- At least the OWASP minimum (19 MiB memory, 2 iterations, 1 degree of parallelism); pwdlib's recommended defaults are stronger and are kept if they run fast enough on Vercel (measured in Phase 7).
- **Rejected:** bcrypt (Argon2id is OWASP's first choice); passlib (pwdlib is FastAPI's current recommendation).

### D-036. Password rules: option C (Chidimma, 2026-10-09)
- Minimum **15 characters for staff and parents**, **10 for students**; maximum at least 64; no composition rules; a bundled list of common passwords is blocked (offline, free); passphrase hint on forms.
- **Accepted risk:** OWASP treats passwords under 15 characters as weak when there is no MFA. Students get 10 because younger pupils struggle with long passwords and student accounts hold only their own published results. Mitigations: common-password block, per-account throttling, generic errors, admin-issued temporary passwords as 4 words. Listed in `docs/SECURITY_AUDIT.md` as an accepted risk.
- **Rejected:** option A (15 for everyone); option B (12 for everyone).

### D-037. Sessions: server-side, opaque cookie
- 256-bit random token in `__Host-sf_session` (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`); only its hash is stored in `user_sessions` with device label, IP, `last_seen_at`, `expires_at`, `revoked_at`.
- Lifetimes (editable later in Platform settings, Security): 12 hours idle and 7 days absolute; super admins 1 hour idle and 12 hours absolute.
- Sliding expiry; `POST /auth/refresh` rotates the token; rotation also on login and password change. Logout, sign out of all devices and deactivation delete session rows immediately.
- **Rejected:** JWTs in browser storage (cannot be revoked instantly; storage readable by scripts).

### D-038. CSRF
- Same origin + `SameSite=Lax` + double-submit CSRF token (`__Host-sf_csrf` cookie copied into `X-CSRF-Token`) on state-changing requests + `Origin` check. The payment webhook is exempt and protected by its signature instead.

### D-039. Activation links
- Random token, hash stored in `account_tokens`, single use, 72-hour expiry; resending cancels the previous link; setting the password verifies the email; `/activate` sends `Referrer-Policy: no-referrer`.

### D-040. Temporary passwords
- Server-generated 4-word passphrase, shown once and on the printable slip, hash stored, `must_change_password` set, unused temporary passwords expire after 7 days. Until changed, the session can reach only change-password, me and logout (enforced on the server).

### D-041. Password resets
- Forgot password: same confirmation for every input; a 1-hour single-use link sent only to existing, non-student accounts with a verified email.
- Students: no self-service; "Ask your school admin".
- School admins reset their reviewers, teachers, parents and students; the super admin resets school admins only and the server refuses any other role.
- Every reset ends other sessions, sends a "password changed" email when there is an address, and is audited. Passwords never appear in emails or logs.

### D-042. Throttling and lockout
- Per account: growing delays after 5 failures (30 s, 1 min, 5 min, up to 15 min), no permanent lockout (avoids attackers locking out real users). Per IP: a wider limit. Counters in Postgres. Same approach for forgot password, activation, reset and verification. Responses stay generic.

### D-043. Two-factor login for super admins (after the core)
- TOTP via `pyotp` with hashed one-time recovery codes; no external service. Session flow designed now so it slots in later.

### D-044. Accounts and schools: option A (Chidimma, 2026-10-09)
- **One school per account** in the MVP. A parent with wards in two SchoolFlow schools gets a separate account from each school (with different usernames, since usernames are platform-wide). The super admin has a platform role with no school.
- **Rejected for now:** one account across several schools with a school switcher (later, if needed).
- **Amended by D-138 (2026-10-12):** parent accounts can be linked to several schools, with the parent's consent.

---

## Round 5: Authorization (approved 2026-10-09)

### D-045. Fixed roles
- `super_admin` (platform), and per school membership: `school_admin`, `reviewer`, `teacher`, `parent`, `student`. The principal is a `school_admin` with `is_primary = true`. Form teacher, "teaches all subjects" and class teacher assistant are assignments, not roles. No custom roles in the MVP (roadmap).

### D-046. Permission names and seeding
- `area.action` names from spec section 5 (for example `scores.enter`, `sheets.approve`, `results.publish`, `attention.view`, `report_card_levels.toggle`, `school_admins.manage`). Seeded by migration from one Python file mirroring the spec matrix; a test compares the file with the spec. Admin management needs `school_admin` plus `is_primary`.
- **Built (2026-10-12):** names follow the SPEC section 5 rows exactly, so admin management is four names (`school_admins.create`, `.remove`, `.reset_login`, `.sign_out_all`) rather than the example `school_admins.manage`; a part without a dot takes the area before it (`sheets.review / return` gives `sheets.return`). 45 permissions in `backend/src/schoolflow_api/authz/permissions.py`. Migration 5 seeds a written-out copy (a migration must never change after it has run), and `tests/test_permissions.py` checks the file against the SPEC table and against the database, so a change needs SPEC, file and a new migration together.

### D-047. Nine-step check chain on every request
- Signed in; password change pending; school active; feature on; level on; permission; ownership or scope; workflow state; separation of duties. Other schools' and out-of-scope records return 404; a missing permission returns 403; a disabled feature returns 404 with a clear code.

### D-048. Provisioning rule
- Nobody creates or resets a role equal to or above their own, always inside their own school. CLI creates the super admin; the super admin creates schools and principals and resets school admins only; the principal manages additional admins up to the limit; school admins manage reviewers, teachers, parents and students.

### D-049. Ownership and scope
- Teachers: `teacher_assignments` per subject and arm; "teaches all subjects" is one row with a flag worked out at query time (covers subjects added later). Form teachers: own form arm only. Assistants: enter and save on their arm, never submit; every entry records its author. Reviewers: `reviewer_scopes`. Parents: `guardian_students` links, effective on the next request. Students: self, published only. Students needing attention: one scope function per role; parents and students refused.
- **Built (2026-10-13, migration 8):** the `teacher_subjects` view (security_invoker, so the caller's row-level security applies) lists every (teacher, arm, subject): subject rows plus, for a form teacher with "Teaches all subjects", every subject of the arm except one given to a specialist teacher (a specialist's assignment wins; one teacher per subject per arm). Assignments describe who teaches now, not per session; result sheets will record their own teacher, and changes go to the audit trail.

### D-050. Report card levels
- Only the super admin toggles levels; no school-side endpoint changes them; every level-bound endpoint (classes, templates, structures, sheets) refuses a level that is off; published reports of a level that is off stay readable and verifiable.

### D-051. School separation: two walls and least-privilege database roles
- Application filter by the signed-in membership plus row-level security with `app.school_id` set per transaction from the membership (never from the URL or body).
- `app_platform` role for `/platform/*` only: schools, admin accounts, billing, audit and email logs, and counts; it cannot read pupils' scores or report contents. `app_verifier` for public verification only.

### D-052. Separation of duties
- Anyone who submitted any revision of a sheet cannot review or approve it; reviewers have no score-editing permission.

### D-053. Proof
- Role × endpoint × status matrix test generated from the permission file; ID-swap tests across schools, wards, sheets and form classes; direct-SQL RLS tests; route coverage test for the auth chain.

---

## Round 6: File storage (approved 2026-10-09)

### D-054. External storage is required
- Vercel Functions have no lasting disk; uploads must live outside the function.

### D-055. One private Vercel Blob store
- Private stores require authentication for every read and write; files are delivered only through our routes. Python SDK `vercel` >= 0.5.0 with OIDC on Vercel (no long-lived key). Free on Hobby: 1 GB storage, 10 GB transfer (checked 2026-10-09).
- **Rejected:** Cloudflare R2 and Amazon S3 (extra accounts and keys); Supabase Storage (extra platform); Postgres `bytea` (uses Neon's 1 GB needed for results).

### D-056. Delivery
- `GET /api/v1/files/{id}` runs the full permission chain, then streams with `Cache-Control: private, no-cache`, `X-Content-Type-Options: nosniff` and an ETag. School logos only through the public school endpoint. Private files are never cached in Vercel's shared CDN.

### D-057. Upload rules
- PNG, JPEG, WebP for logos, signatures and stamps; PDF also allowed for correction attachments; SVG rejected. Type checked by content (magic bytes). Images re-saved with Pillow to strip metadata (including GPS) and resize. Limits: 1 MB images, 4 MB attachments (Vercel request limit 4.5 MB). Random storage paths under `schools/{school_id}/...`; the original name is a label only. A `files` table (school_id, owner, type, size, SHA-256) with row-level security. Tests for disguised, oversized, SVG and cross-school files.

### D-058. PDFs are regenerated, not stored (closes the spec's open question)
- The permanent record is the immutable published snapshot plus template version and the snapshot's SHA-256 hash. PDFs render on demand from those inputs. Bulk class prints are queued jobs that write a temporary merged PDF to Blob, deleted by the daily cron after 24 hours.
- **Reason:** storing every PDF (estimate about 225 MB per 500-student school per year) would fill the free 1 GB quickly; the snapshot is the real record.
- **Revisit when:** on-demand rendering measures too slow in Phase 7; then cache single PDFs in Blob on first download.

### D-059. FileStorage interface
- Local folder (`backend/.local-storage/`, git-ignored) for development and tests; Vercel Blob for staging and production; switched by configuration. Fonts, templates and default images ship inside the backend container.

---

## Round 7: PDF (approved 2026-10-09)

### D-060. Renderer: WeasyPrint in the FastAPI container
- **Reason:** HTML and CSS input matches the approved report card designs (already HTML in `design/screens/Report*.dc.html`); strong paged-media support; runs no scripts; light enough for the container (Python 3.10+, Pango 1.44+ via `apt-get`).
- **Fallback:** headless Chromium in the same container for any layout WeasyPrint cannot handle.
- **Rejected:** ReportLab (layout by coordinates); react-pdf (limited CSS, renders away from the snapshot data).

### D-061. Pipeline and template validation
- Published snapshot + template version JSON (validated by Pydantic; attempts to hide report ID, revision, date or QR are rejected, AC12.3) → one Jinja2 file per block, included in the template's block order (footer always last) → WeasyPrint.

### D-062. Two card types on one block engine
- Score report card and Skills report card share the engine; Skills cards never render totals, averages, grades or positions (AC26.3).

### D-063. Styles as CSS presets
- Modern, Classic, Compact, Early Years in the core; Bold Banner, Ink Saver, Cumulative after the core. Template settings map to CSS (`@page` paper size and margins, font, text size, accent colour, borders, watermark, grading key position). Variable assessment columns loop over the snapshot's components (1 to 8); Compact fits 15+ subjects with 5 components on A4.

### D-064. Safety and print rules
- Jinja2 autoescape on; cards always use light token values; fonts Inter, Merriweather, Nunito bundled in the container (SIL Open Font License); no network fetches during rendering.

### D-065. QR and footer
- QR generated with segno as inline SVG, holding only the verification URL; report ID, revision, publication date and QR always shown.

### D-066. One HTML for preview and print
- Template editor and form teacher previews render the same block HTML in an iframe, watermarked "Preview, not published". The parent's online view is a separate light HTML page built from the same snapshot.

### D-067. Repeatable output
- PDF metadata creation date set to the publication date, so the same snapshot and template version always give the same PDF.

### D-068. Bulk class printing
- Queued job renders the class into one merged PDF, stored temporarily in Blob (24 hours, D-058), with a notice when ready.

### D-069. PDF testing
- Text extraction with `pypdf` (names, scores, report ID; no totals or grades on Skills cards); visual snapshots of page 1 with `pypdfium2`; golden cases (two real-format templates AC12.1, Highest in class AC12.2, Compact 15 subjects × 5 components, Nursery Skills card, Primary A to F with Head teacher's comment); speed measured in Phase 7 for one card and a 30-student class.

### D-070. Windows development for PDFs
- Run the backend in Docker locally to match production (final call in Round 12); MSYS2 Pango is the alternative.

---

## Round 8: QR verification (approved 2026-10-09)

### D-071. Opaque random code with server lookup
- The QR holds only `https://<domain>/verify/<code>`; status is read live from the database. A QR proves the report exists in our records, not that every score is correct.
- **Rejected:** signed tokens (data inside the QR; revocation still needs a lookup; too long to type).

### D-072. Code format: option B, 12 characters (Chidimma, 2026-10-09)
- 12 characters of Crockford Base32 in three groups, for example `7KQ4-M2XD-P9QA` (about 60 bits), generated with Python `secrets`. Input is forgiving (lowercase, missing dashes and spaces accepted).
- **Design deviation:** the `Verify` and `VerifyAfter` screens show 8-character codes (`7KQ4-M2XD`). The layout and labels stay as designed; only the code is one group longer. Report this difference when the Verify screen is built.
- **Rejected:** option A, 8 characters (about 40 bits; relies on rate limiting alone).

### D-073. Code storage
- Only the SHA-256 hash of each code is stored in `verification_tokens`; each published revision gets its own code; publishing a new revision marks the previous one SUPERSEDED.
- **Note (2026-10-14, D-149):** the plain code is also kept on the report document itself, readable only by the school, so regenerated PDFs (D-058) can print the same QR code.

### D-074. Public page content (as designed)
- Status word and line, school, masked student name (first 4 letters of the first name + `***` + surname initial, for example `Chuk*** O.`), term, report ID (for example `GMC-2627-T1-JSS1A-014`), revision and date. Never scores or the full name.
- SUPERSEDED offers "Check the current version"; REVOKED shows "The school withdrew this report. Contact the school." and never the reason; NOT FOUND takes the same time as a real lookup. Status always shown with a word, not colour alone.

### D-075. Verification survives level and school changes
- Reports still verify when their level is turned off (AC25.4) or the school is suspended (a report already issued remains a real record).

### D-076. Abuse protection
- Postgres-backed rate limits (about 30 lookups per minute per IP, tighter for repeated NOT FOUND) plus one Vercel firewall rule; `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `noindex`; logs keep only the first 4 characters of a code; lookups run as `app_verifier`.

### D-077. Verification tests
- VALID, SUPERSEDED after correction (AC13.1), REVOKED, NOT FOUND; forgiving input; response contains no scores or full name; rate limit triggers; level-off reports still verify.

---

## Round 9: Email and notice board (approved 2026-10-09)

### D-078. Email provider: Resend Free behind an EmailProvider interface
- Free: 100 emails per day, 3,000 per month, 3 domains (checked 2026-10-08). Resend Pro ($20/month, no daily limit) on the onboarding-day upgrade list.
- **Rejected:** Brevo Free (adds Brevo branding; limits unverified); Amazon SES (paid, sandbox approval).

### D-079. Sending domain and sender identity
- Send from a subdomain, for example `SchoolFlow <no-reply@mail.meritiaa.com>`, so the main domain's reputation is protected. **Updated 2026-10-09 (Phase 3): the sending subdomain is `notify.meritiaa.com`**, because `mail.meritiaa.com` already exists as cPanel's mail server hostname for Chidimma's mailbox and must stay untouched. Resend sending region: Ireland (`eu-west-1`), the closest of Resend's four regions. SPF, DKIM and DMARC records set up in Phase 3 (ask where `meritiaa.com` DNS is managed).
- **Per-school identity (Chidimma asked 2026-10-09 "Can every school have its own email like admin@greenfield.com?"):** school emails use the school's name as the sender name and the School email as Reply-To, for example `Greenfield Model College <no-reply@mail.meritiaa.com>` with `Reply-To: admin@greenfield.com`. Free, no DNS work for schools, works with Gmail addresses. Platform emails use "SchoolFlow" and the support address from Platform settings.
- Never put a school's address in the From line without that domain verifying us (spoofing fails SPF, DKIM, DMARC checks); never store schools' mailbox passwords.
- **Roadmap (paid add-on):** custom sending domain per school (school owns the domain and adds DNS records; needs a higher Resend plan, since Free allows 3 domains and Pro 10). The From address is chosen in one place in `EmailProvider` so this slots in later.
- Mailbox hosting for schools (receiving mail) is out of scope; schools enter whatever address they already have.

### D-080. Outbox table
- `email_outbox` is the source of truth: `school_id` (null for platform), `type`, `to_address`, `template`, `template_data`, `priority`, `status` (QUEUED, SENT, FAILED), `attempts`, `next_attempt_at`, `last_error` (cleaned of personal data), unique `idempotency_key` (exactly one email per recipient per event, AC18.1), `provider_message_id`.

### D-081. Secret links created at send time
- Activation and reset tokens are created by the sender at the moment of sending; only the hash is stored; the raw token never sits in the outbox or anywhere else.

### D-082. Daily limit, priority and retries
- Stop at 95 sends a day; the rest stay QUEUED for the next day (Queues delay plus daily cron). Order: priority first (account emails before bulk result emails), then oldest. Temporary failures retry at growing gaps (1 min, 5 min, 30 min, 2 h, 12 h); after 5 attempts FAILED; super admin Retry button in the Email log.

### D-083. Email content and logs
- Plain, friendly text with a login link; never scores, report contents or passwords; activation emails include the username (and the school code for school admins). Jinja2 with autoescape, HTML and plain-text parts.
- Email logs show status only, never bodies: `/platform/emails` (all) and `/school/emails` (own school). Delivery webhooks (bounces) are not in the MVP; if added later they need signature checks.

### D-084. Notice board data model
- `notices` (school_id, title, plain-text body, kind manual or system, pinned, status, author, timestamps), `notice_audiences` (what the admin chose), `notice_recipients` (actual people, worked out when posted), `notice_reads`.
- Recipients are fixed at posting time (exact audience, honest record of who was told, supports system notices to specific people). Pinned notices for everyone also reach people added later.

### D-085. Unread counts and automatic notices
- Unread count in `/auth/me` and `GET /notices/unread-count`, refreshed every 60 seconds while the tab is visible (no WebSockets).
- Automatic notices (results published; invoice paid to school admins) are created in the same transaction as the triggering action and its outbox emails.

### D-086. Notice safety and permissions
- Bodies shown as plain text, never HTML; edits and archiving audited; only school admins post (form teachers cannot, F17); same-school only through the application and RLS; platform announcements after the core reuse the tables with `school_id` null.

---

## Round 10: Payments and subscription billing (approved 2026-10-09)

### D-087. Gateway: Paystack, test mode only
- **Reason:** local fees capped at ₦2,000 per payment (Paystack support; the 1.5% + ₦100 rate to confirm by hand), so a ₦290,000 invoice costs ₦2,000 versus about ₦5,800 plus VAT on Flutterwave (2%, no cap shown, checked 2026-10-08). Test mode needs no business documents. Going live (business activation) is post-MVP.
- **Rejected:** Flutterwave (not registered; one gateway only per BUILD_PROMPT).

### D-088. Volume pricing in integer kobo
- Defaults: Basic 1 to 499 at ₦1,000; Standard 500 to 1,000 at ₦500; Premium 1,001+ at ₦300. The student count picks the plan; every student pays that plan's price. Pricing engine is a pure function.

### D-089. Cliff protection and price check
- On by default: a bill never exceeds the cheapest possible bill on any higher plan (Basic cap ₦250,000; Standard cap ₦300,300); the invoice records `cliff_cap_applied`.
- Verified by script 2026-10-09: off 499 → ₦499,000, 500 → ₦250,000, 1,000 → ₦500,000, 1,001 → ₦300,300 (AC19.2); on 499 → ₦250,000 capped, 580 → ₦290,000, 642 → ₦300,300 capped, 1,000 → ₦300,300 capped, 1,001 → ₦300,300 (AC19.3); price check flags 251 to 499 and 601 to 1,000 (AC19.4).

### D-090. Plan rules and versions
- First plan starts at 1; inclusive ranges with no gaps or overlaps; only the last plan open-ended; prices whole kobo above zero; unique names (AC19.1). Every save creates a new pricing version; issued invoices keep theirs (AC19.5); changes audited; super admin only.

### D-091. Invoices
- One per school per term, generated by the super admin for one or all billable schools. Billable students: active enrolled students for the term at generation; later additions billed next term or by an adjustment invoice. Snapshot: term, student count, plan, rate, pricing version, `cliff_cap_applied`, `amount_kobo`, due date (generation + 14 days default), status UNPAID, PAID or VOID. Issued invoices never change; voiding needs a reason and is audited.

### D-092. Subscription status
- FREE_PILOT or ACTIVE → DUE (invoice issued) → ACTIVE (paid) or OVERDUE (due date + 14-day grace), calculated on read and refreshed by the daily cron. Suspension is always manual and never deletes data. Billing off: no invoices, prompts or billing card (AC19.9).

### D-093. Payment flow
- `POST /school/invoices/{id}/pay` takes the amount from the invoice on the server, creates a payment attempt with our own unique reference, calls Paystack initialize and returns the checkout URL. The callback page `/school/billing/callback` only shows "Confirming payment" and polls the invoice status; the redirect never marks an invoice paid.

### D-094. Webhook handling
- Raw-body HMAC-SHA512 with the secret key compared in constant time against `x-paystack-signature` (reject with 401, store nothing on mismatch, AC19.6); store the event under a unique key (duplicates ignored, AC19.7); respond 200 quickly; a queued worker calls Verify Transaction and checks success, amount equals `amount_kobo`, currency NGN and the reference belongs to the invoice; one transaction marks the invoice PAID, creates the payment (unique gateway reference) and receipt, posts a notice to school admins and queues the receipt email. The daily cron reprocesses pending events. Paystack IP allowlisting optional, never a replacement for the signature.

### D-095. Receipts
- Numbered (for example `SF-RCPT-2026-000123`); simple page plus PDF from the WeasyPrint pipeline, regenerated from the payment record; emailed to the school admin.

### D-096. Fees, manual payments, separation, keys
- Gateway fees paid by the platform by default (Platform settings, Billing). Manual payments and voids by the super admin with reference, note or reason, audited. Another school's invoice returns 404 (AC19.8). Secret keys only in backend environment variables.

### D-097. Billing tests
- Pricing engine rows above, plan-edge counts, overlap and gap validation, versioning; webhook valid, invalid, missing and replayed signatures, duplicate events, amount, currency and reference mismatches; redirect alone never marks paid; browser tampering changes nothing; Paystack test card end to end on staging.

---

## Round 11: Testing (approved 2026-10-09)

### D-098. Backend test stack
- pytest, FastAPI `TestClient`/httpx, pytest-cov, Hypothesis (property-based tests for the results and pricing engines), time-machine (expiry tests), respx (fake Paystack API). `FakeEmailProvider` records emails; local-folder storage for files.

### D-099. Real PostgreSQL in tests
- PostgreSQL 17 in Docker with the real `app_user` role; migrated once per run; each test in a rolled-back transaction; `app.school_id` set exactly as in production. Never SQLite.

### D-100. Test data
- Fictional factory functions with Nigerian names; two schools always present.

### D-101. Backend test kinds
- Unit (engines, validators), service (workflow, separation of duties, assistants, teaches-all-subjects), API with at least one denied or invalid case each, role × endpoint matrix, ID-swap, RLS and immutability in raw SQL, log redaction, PDF.

### D-102. Frontend component tests
- Vitest, React Testing Library, user-event, MSW. Priority components tested first: ScoreGrid, RatingGrid, AssessmentStructureEditor, LoginTabs, Sidebar, ThemeToggle, ReasonDialog, ApprovalActionBar, PricingTierEditor, ColorPicker, ResponsiveTable.

### D-103. End-to-end tests
- Playwright against the real app and seeded test database; 360, 768 and 1440px × light and dark; no sideways scroll check on every page; the 38 demo steps as test files; Chromium plus a WebKit smoke run.

### D-104. Accessibility testing
- @axe-core/playwright (WCAG 2.2 AA) on every page in both themes, failing on serious issues; eslint-plugin-jsx-a11y; keyboard tests (login, score grid arrows, sidebar, dialogs, visible focus ring); reduced-motion check; one manual Windows Narrator pass per screen in Phase 9.

### D-105. Coverage
- 95% branch coverage enforced on security-critical backend modules (auth, permissions, tenant context, provisioning, workflow, pricing engine, results engine, webhook, verification); 85% lines elsewhere in the backend; frontend priority components must have tests. The denied-case rule is checked in review.

### D-106. Test naming and running
- Test names are behaviour sentences (for example `test_teacher_cannot_approve_own_sheet`). Commands recorded in `AGENT.md` in Phase 4; CI set in Round 12.

---

## Round 12: Development tools (approved 2026-10-09)

Installed on Chidimma's laptop (checked 2026-10-09): Node 24.21.0, npm 11.19.0, Bun 1.4.2, Python 3.14.7, uv 0.12.16, Git 2.55.0, Docker 29.8.0, WSL Ubuntu, VS Code 1.139.1. Not installed: pnpm, GitHub CLI.

### D-107. Node.js 24 LTS
- Pinned with `"engines": { "node": "24.x" }` and `.nvmrc`. Vercel supports 24.x (default), 22.x and 20.x (checked 2026-10-09).

### D-108. JavaScript package manager: Bun (Chidimma's choice, 2026-10-09)
- Bun 1.4.2 installs packages and runs scripts (`bun install`, `bun run dev`, `bun run test`, `bun run e2e`); `bun.lock` is committed and Vercel detects it (Bun 1 supported, checked 2026-10-09).
- Node 24 remains the runtime for Next.js on Vercel; we do not use the Bun runtime for the app.
- Tests stay on Vitest: `bun run test` runs Vitest; Bun's own `bun test` runner is not used.
- Packages' install scripts run only when listed in `trustedDependencies`.
- CI uses `oven-sh/setup-bun`. To confirm in Phase 4: Dependabot support for `bun.lock` and `bun audit` coverage (fallback `npm audit`).
- **Rejected:** npm (my first recommendation; Chidimma prefers Bun and already knows it); pnpm (not installed, new commands).

### D-109. Python 3.14 managed by uv
- uv for dependencies, virtual environments and running tools; `uv.lock` committed; Vercel reads uv projects. Fallback to 3.13 (`uv python pin 3.13`) if a library fails to install on 3.14.

### D-110. Monorepo layout
- `frontend/` (Next.js), `backend/` (FastAPI + `Dockerfile.vercel` with Pango), `design/`, `docs/`, root `vercel.json` (Services) and `docker-compose.yml`, plus the root docs (`AGENT.md`, `CLAUDE.md`, `MEMORY.md`, `LOG.md`, `DECISIONS.md`, `CHANGES.md`, `README.md`).

### D-111. GitHub: public repository (Chidimma's choice, 2026-10-09)
- **Reason:** free unlimited Actions minutes on standard runners, branch protection on `main`, free secret scanning (checked 2026-10-09).
- Turn on secret scanning and push protection when creating the repo; protect `main` (merge only with green CI). gitleaks still runs locally and in CI. Nothing secret or real is ever committed.
- No open-source licence by default (code readable, not reusable); add an "All rights reserved" notice to the README in Phase 4 unless Chidimma decides otherwise.
- Branch per step (`feat/auth-login`), Vercel preview URL per branch, conventional commits, install GitHub CLI (`gh`) in Phase 4.
- **Rejected:** private repo (2,000 Actions minutes a month, no branch protection or secret scanning on Free).

### D-112. Docker usage
- Postgres 17 always in Docker; backend runs natively with uv for daily work; a Linux backend container (matching production) runs PDF tests (`docker compose run backend pytest -m pdf`), skipped locally outside the container; CI always runs them. Frontend runs natively.

### D-113. API exploration
- FastAPI `/docs` in development only, plus committed `.http` files for the VS Code REST Client (no secrets). No Postman.

### D-114. Editor
- VS Code with Python, Pylance, Ruff, ESLint, Prettier, Tailwind CSS IntelliSense, Docker, Playwright Test, Vitest, EditorConfig and REST Client, listed in `.vscode/extensions.json`.

### D-115. Lint, format, types
- Python: Ruff (lint and format), Pyright (types). TypeScript: ESLint (Next.js config + jsx-a11y), Prettier with the Tailwind class-sorting plugin, `tsc --noEmit` strict.

### D-116. Pre-commit hooks
- The pre-commit tool (`uv tool install pre-commit`): Ruff, Ruff format, Prettier and ESLint on changed frontend files (through Bun), gitleaks, block `.env` files and files over 1 MB, line-ending tidy.

### D-117. CI on GitHub Actions
- Every push: backend (Ruff, Pyright, pytest with coverage gates on a Postgres 17 service, PDF tests in the Linux image), frontend (ESLint, Prettier check, `tsc`, Vitest via Bun), security (gitleaks full history, `pip-audit`, Bun or npm audit), Docker build of `Dockerfile.vercel`, Playwright (6 combinations) with axe. Dependabot weekly.

### D-118. Environment files
- `backend/.env` and `frontend/.env.local` git-ignored; `.env.example` with names only; real values in Vercel environment settings and GitHub Actions secrets.

---

## Round 13: Deployment, logging and monitoring (approved 2026-10-09)

### D-119. Hosting (all free tiers, D-00A)
- One Vercel Hobby project with Services (Next.js + FastAPI container) in `lhr1`; Neon Free in London with `production` and `staging` branches; Vercel Blob private store; Resend Free; Paystack test mode.

### D-120. Cold starts accepted; no keep-alive pinging
- Pinging to keep functions warm would keep Neon awake and burn the 100 free compute-hours; demo day uses a warm-up checklist instead.

### D-121. Environments
- Local (Docker Postgres, git-ignored `.env`), staging (`staging` branch + Neon `staging`, public, fictional data, "Staging" banner, noindex), previews (feature branches + Neon `staging`), production (`main` + Neon `production`, Paystack still test mode). Separate secrets per environment. **Domain names confirmed 2026-10-09:** production `schoolflow.meritiaa.com`, staging `staging.schoolflow.meritiaa.com`, email sending `notify.meritiaa.com`. App CNAME records are added in Phase 4 with the values Vercel shows (never before the project claims the name, to avoid dangling records).

### D-122. Paystack test webhook URL
- Paystack has one test webhook URL per account: points at staging during development; switched to production before the demo (BUILD_PROMPT section 14).

### D-123. Deployment pipeline
- For `main` and `staging`, GitHub Actions runs CI, then Alembic migrations on that environment's Neon branch (owner role from GitHub secrets), then deploys with the Vercel CLI (token in GitHub secrets). `vercel.json` sets `git.deploymentEnabled` false for `main` and `staging`; feature-branch previews deploy automatically. Migrations never run on app startup and are backward-compatible (add first, remove later). The running app holds only `app_user` credentials.

### D-124. Logging
- JSON logs to standard output (time, level, request ID, route, status, duration, school ID, user ID) with a tested redaction filter (passwords, tokens, cookies, scores, emails, full names). Vercel Hobby keeps 1 hour of logs and has no log drains; lasting records live in the audit, email log and payment event tables.

### D-125. Error monitoring: Sentry Developer (free)
- Free plan (checked 2026-10-09): 5,000 errors, 1 user, 30-day lookback, 5M spans. Backend and frontend. `send_default_pii` off; `before_send` scrubber removes bodies, cookies, headers, emails, names and scores; user identified by internal ID only; light trace sampling. Listed in `docs/SERVICES.md`.

### D-126. Health checks
- `GET /api/v1/health` (no database, safe to call often) and `GET /api/v1/health/ready` (checks the database; used for warm-up and after deploys). No external uptime monitor in the MVP.

### D-127. Backups (completes D-031)
- Manual `pg_dump` script from Git Bash to Chidimma's laptop (outside the repo) and a restore test before the demo. Never stored as GitHub artifacts (public repo). Neon Launch scheduled backups and 7-day restore on onboarding day.

### D-128. Demo-day warm-up checklist
- Open the site and call `/health/ready`; check Neon compute-hours used; check Resend's daily count; send a test webhook from Paystack's dashboard; have the Paystack test card ready; confirm Sentry is quiet. Written in full in Phase 11.

### D-129. Onboarding-day upgrade list
- Vercel Pro ($20 per developer seat per month; Hobby is non-commercial), Neon Launch (pay as you go, no suspension, 7-day restore), Resend Pro ($20/month, no daily limit), Paystack go-live (business activation), Sentry stays free until errors outgrow 5,000. Kept in `docs/SERVICES.md`.

## Phase 4 decisions

### D-130. Dependency audit in CI ignores one unpatched dev-only advisory (Chidimma's choice, 2026-10-11)
- CI fails on any high or critical advisory (`uv audit --locked`, `bun run audit` = `bun audit --audit-level=high`), with exactly one exception: **GHSA-vfj7-8cjw-p6xm** (`braces` <= 3.0.3, denial of service through deeply nested glob patterns, published 2026-09-18, no patched version).
- **Reason:** `braces` comes in only through `eslint-config-next` > `@next/eslint-plugin-next` > `fast-glob` > `micromatch`. It runs at development time on our own file patterns, never on user input, and never ships to the browser or the server.
- **Remove the ignore** as soon as a patched `braces` (or a dependency path without it) is available; Dependabot alerts will flag it.
- **Rejected:** letting CI stay red until a fix exists (blocks every merge with no date); report-only audits (new real problems could slip through).

### D-131. Staging deploy: project-scoped token, alias through the REST API (Chidimma's choice, 2026-10-11)
- The `deploy-staging` job in `.github/workflows/ci.yml` runs only on pushes to `staging`, after all five checks. It reads `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` from the GitHub environment **`staging`**, which only the `staging` branch may use.
- `VERCEL_TOKEN` is scoped to the **`schoolflow-result-portal` project only**, 30-day expiry (current one expires 2026-11-10), so it cannot reach the two other projects on the account.
- `vercel deploy --target=preview` (Vercel builds remotely; the `--prebuilt` path is not used because container-service support is unconfirmed), then the alias is assigned with **`POST https://api.vercel.com/v2/deployments/{url}/aliases?teamId=…`** via curl, then `/api/v1/health` on the staging domain must return `{"status":"ok"}`.
- **Why not the CLI alias:** `vercel alias set` and any command with `--scope` first load the user account, which a project-scoped token may not do ("User not found", tested 2026-10-11).
- Flow: features merge to `main` by pull request; `staging` is fast-forwarded to `main` (`git merge --ff-only origin/main`) to update staging.
- **Rejected:** team-wide token (reaches the other live projects); branch-domain assignment (CLI deploys are not full Git deployments per Vercel's guide, unverified).

## Phase 5 decisions

### D-132. Pages with no design are built from existing patterns (Chidimma's choice, 2026-10-12)
- The 13 demo pages without a board (activate; students list, add, import; teachers; parents; school audit; notices list and composer; notice board; notice bell; review queue; review sheet; child results) and the P2/P3 pages without one are built from the v0.5 pieces in `design/screens/sf.css` (shell, tables that become cards, dialogs, badges, the 4-step import pattern, the read-only score grid) and the content in design brief section 9. Chidimma reviews each in the browser in Phase 8. List in `docs/UI_REVIEW.md`.
- **Rejected:** a design-tool follow-up first (adds design time); text wireframes first (extra approval round).

### D-133. v0.3 boards get both themes from the tokens (Chidimma's choice, 2026-10-12)
- Verify, Approvals, Corrections, Parent home, Report view and Parent correction keep their approved layouts and get light and dark from the design tokens and the v0.5 shell. No redesign.

### D-134. Change password rule text follows D-036 (Chidimma's choice, 2026-10-12)
- The `ChangePassword` board shows "At least 8 characters" and "A letter and a number". The build shows the D-036 rules instead: at least 15 characters (10 on student accounts), no composition rules, common passwords blocked. Exact wording is settled with the section 5 labels. Recorded as an approved difference from the design.

### D-135. Report card gaps from Nigerian report card research (Chidimma, 2026-10-12)
- Research in `docs/REPORT_CARD_RESEARCH.md` (Ogun State CA report sheet, FCT UBEB termly report, two real school cards in summary, vendor and curriculum sources). Six complete real cards were not publicly available; real cards from known schools, with names covered, would complete UI_REVIEW item 8.
- Added (SPEC v0.5.1): optional student Department (Senior Secondary) and subject category, with report switches "Department" and "Group subjects by category"; summary switches "Marks obtainable", "Highest average in class", "Lowest average in class" (all off by default); written defaults for Secondary A1 to F9 bands, affective and psychomotor traits and the 1 to 5 key; nursery learning areas Pre-science and Handwriting.
- **Left out:** health block (sensitive data), next term fees (fee collection is roadmap), CA 30 and exam 70 as default (default stays CA1 20, CA2 20, Exam 60, editable). Cumulative third-term style stays after the core.

## Phase 7 decisions

### D-136. School levels: four rows per school, one Secondary toggle (option A, Chidimma, 2026-10-12)
- `school_levels` holds four rows per school (`nursery`, `primary`, `junior_secondary`, `senior_secondary`), each with its own `enabled`, `assessment_mode` and `head_title`. The single "Secondary report cards" toggle (F25) switches junior and senior secondary together.
- The database enforces it with a deferred constraint trigger checked at commit: all four rows exist, junior and senior secondary are on or off together, at least one level is on (AC25.5). Allowed values are text columns with CHECK rules built from Python `StrEnum`s (no PostgreSQL enum types, which are harder to change in later migrations).
- **Reason:** classes, assessment structures and grading bands later point at an exact level (a JSS class) without special cases.
- **Rejected:** three rows, one per toggle (JSS and SSS would share one assessment mode and head's title, and every later table would need another way to tell them apart).

### D-137. Row-level security and database roles arrive with each migration (Chidimma `ok`, 2026-10-12)
- Every migration that adds a school-owned table also adds its RLS policies, its grants for `app_user`, `app_platform` and `app_verifier`, and denied-case tests run as those roles. BUILD_PROMPT 9.1 item 12 becomes the final audit; a test already fails if any table with `school_id` lacks RLS or if any table grants anything to PUBLIC.
- The three roles are created by a migration with SQL (`NOLOGIN`, no superuser, no BYPASSRLS), and the migration refuses to run if any of them can bypass RLS. On Neon they must never be created in the Console: Console roles join `neon_superuser`, which has BYPASSRLS (Neon "Manage roles" docs, checked 2026-10-12). Login and passwords are added per environment, outside git.
- Each transaction sets `app.school_id` and `app.user_id` with `set_config(..., true)` from the signed-in session (D-027). Policies read them through `app_current_school_id()` and `app_current_user_id()`, which turn the empty string a reused connection returns into NULL (tested on PostgreSQL 17.11, 2026-10-12), so a connection without context sees nothing instead of failing.
- **Reason:** writing every module as a role that skips RLS and switching RLS on at the end would hide missing policies until the security gate.
- **Rejected:** RLS added only at item 12.

### D-138. One parent account across schools, with the parent's consent (Chidimma, 2026-10-12; amends D-044)
- A parent account can be linked to several schools, one membership per school. Every other account stays in one school at most: the super admin in none; school admins, reviewers, teachers and students in one.
- **Link request (option 2A):** when a school adds a parent whose email already belongs to a parent account, no second account is made. The school's request waits in its own link-request record, which holds only the email the school typed (built with the guardians table, migration 4), and the parent accepts or declines after signing in. The school gets the same response for every email, so it never learns whether someone already uses SchoolFlow, and it cannot see the account until the parent accepts. Requests expire after 14 days. The membership is created only when the parent accepts: the database lets only the parent add a parent membership for an account that is already linked to another school (memberships are `active` or `paused`; there is no `invited` membership, so a school's own data never hints that an email already had an account).
- **Shared accounts:** once an account has active or paused links in more than one school, only the parent changes its email, username and password (Forgot password). No school can reset it, issue a temporary password, sign it out of all devices or deactivate it; each school can pause or remove its own link. Enforced in the database as well as the API.
- **Each school sees only its own part:** RLS stays one school per transaction; the parent's pages read each linked school in turn and group children by school. Per-school guardian details (relationship, phone) live in each school's guardian record.
- **Notices and emails name the school:** a school label on every notice; the school name as sender (D-079) and at the start of the subject.
- **Staff who are also parents (option 3A):** not in the MVP. An email that belongs to a staff or student account cannot be linked as a parent. The schema allows switching it on later without moving data (one non-parent membership per account; the "parent or staff" rule is one database trigger). Kept in MEMORY.md as a possible future upgrade (option 3B).
- **Rejected:** telling a school "this email already has an account" (option 2B: any school could check whether a person, and so their children, uses another SchoolFlow school); one account across schools for every role with a school switcher (more work and new screens).

### D-139. Pupils' names: surname, first name, other names (Chidimma, 2026-10-13)
- The `students` table stores `surname`, `first_name` and `other_names` (optional). Class lists and broadsheets sort by surname, report cards can print the surname first, the verify page masks reliably ("Chuk*** O." from first name and surname), and it matches how Nigerian schools and WAEC/NECO record pupils. The CSV import template gets three name columns.
- Staff and parent accounts keep one `full_name` (the design's "Full name").
- **Rejected:** one "Name" box for pupils, as the Add student design shows (sorting and masking would have to guess the surname). Listed under approved differences from the design.

### D-140. Parents with an email are always added by link request (Chidimma, 2026-10-13; completes D-138 option 2A)
- When a school adds a parent with an email, the only login method is the link request: an existing account accepts after signing in, and a new person sets a password from the same emailed link. The school sees "Waiting for the parent" either way. A temporary password slip is offered only for parents without an email.
- **Reason:** a slip cannot be made for an email that already has an account, so offering slips to parents with an email would tell the school whether the email already uses SchoolFlow, which D-138 option 2A rules out.
- **Rejected:** slips for parents with an email.

### D-141. How the grading set-up is stored (2026-10-13; reading of SPEC F08)
- `grade_bands` (BUILD_PROMPT's "grading_scales"): one row per band per level (grade, minimum, maximum, remark). A level's bands cover 0 to 100 with no gaps or overlaps, checked at commit so a school can replace all bands in one save.
- `remark_bands`: suggested class teacher comments for an average range (F22 rule 3), per level, 1 to 3 comments per band ("2 or 3 suggestion chips"), also covering 0 to 100. The spec gives no default wording, so schools write their own until Chidimma approves defaults.
- `assessment_structures`: one per level per term, holding the assessment mode as well as `locked_at`, because AC08.6 makes a mode change wait for the next term like a structure change. Once locked (first score or rating saved), mode, components and the lock itself cannot change. `school_levels.assessment_mode` stays the school's choice for future terms.
- `school_settings`: a new one-row-per-school table for the pass mark (1 to 99, default 40) and later school-level settings, so the built `schools` table is not changed. A value like 40.5 is refused by the API's whole-number check (the database column would round it).
- Defaults from SPEC F08 live in `backend/src/schoolflow_api/grading/defaults.py`; a new school gets a copy during set-up (service layer, later).

### D-142. Approving a sheet nobody reviewed (Chidimma, 2026-10-13)
- A school admin (not the submitter) may approve a Submitted or Resubmitted sheet directly only when no reviewer's scope covers it (department, subject or class). Where a reviewer exists, review is never skipped. Fits small schools such as BSA (demo step 32) that have no HODs.
- **Rejected:** admins may always skip review; admins must mark reviewed first (two clicks for the same effect).

### D-143. When a changed score needs a reason (Chidimma, 2026-10-13)
- While a sheet is a first draft, teachers fix their own entries freely; the audit trail still keeps old and new values. Once the sheet has been submitted at least once (Returned for correction) or is a reopened revision, every change to a saved score needs a reason.
- **Rejected:** a reason for every change of a saved score, even in the first draft (many reasons for routine typing).
- **Built (migrations 11 to 13; approved CHANGE 2026-10-13):** the same rule applies to skill ratings. A reason counts only when the change gives it: the reason already stored, left out or repeated word for word, counts as none. A reason is never edited on its own, without a change.

### D-144. Staff who also teach: teaching comes from assignments (Chidimma, 2026-10-13)
- School admins and reviewers can also be given teacher assignments: subjects in an arm, a form class (with "Teaches all subjects") or a class assistant place. On those sheets they act as teachers; they have no power over other sheets. Separation of duties still applies (D-052), which is what AT-14.3 tests.
- Built as a CHANGE: the login rule for `teacher_assignments` and `class_assistants` accepts the roles teacher, school admin and reviewer; permission checks for teaching actions (9.2) use assignments, not only the teacher role.
- **Rejected:** strict roles, where a principal or HOD who teaches needs a separate teacher account.

### D-145. How skill ratings are stored (2026-10-13; reading of SPEC F26 and the approved CHANGE "Rating sheets join the sheet workflow")
- `learning_areas` per level (a name once per level, only for levels that are on) and `skills` per area (a name once per area, optional description, retired rather than deleted). Defaults live in `backend/src/schoolflow_api/ratings/defaults.py` and follow SPEC F26 rule 1 and AT-30.1: ten areas, including Pre-science and Handwriting. `design/NAVIGATION_AND_SETTINGS.md` lists eight; on behaviour the spec wins. No document gives sample skills for Pre-science or Handwriting, so schools add their own until Chidimma approves defaults.
- Areas are given to classes (`class_learning_areas`, the design's "Assign to classes"), only to classes of the area's level. An area stays with a class while the class has a rating sheet or a teacher for it, as a subject stays with an arm.
- One `rating_scales` row per school with its `rating_scale_points`, best point first, each with a word, a code shaped like a grade code (E, VG, NI) and an optional description. Exactly one point is the attention point, checked at commit so a school can move it in one save; "at or below" means that point and every point after it.
- Rating sheets are `result_sheets` rows for a learning area: one per area per arm per term, only for an area of the arm's class, on a Skill ratings structure. A teacher gets an area through a learning area row in `teacher_assignments`, or through "Teaches all subjects", which covers every area of the class except one given to a specialist.
- `skill_ratings` follow the score rules: locked once submitted, a reason after a return or reopen (D-143), removed only in the first draft, an author on each. Only active skills are rated, and submitting needs every pupil of the arm rated on every active skill of the area (AC26.2). The first rating locks the level's structure for the term (AT-30.2).
- `area_comments`: one optional comment per pupil per rating sheet, up to 300 characters, locked once submitted; no reason is asked for before then.
- Review: a reviewer scope that names only a class covers that class's rating sheets; department and subject scopes cover score sheets only. D-142 applies unchanged.

### D-146. Class sections after publication work like score sheets (Chidimma, 2026-10-14; SPEC v0.5.5)
- A class's form teacher sections become Published when the class is published. To correct them, a school admin reopens them with a reason, which starts a new revision; the form teacher edits and submits again, as with a reopened sheet. Every move (submit, return, publish, reopen) is kept in a history that never changes.
- **Rejected:** publication only locks the sections, with corrections designed later with the correction queue (item 8).

### D-147. Students needing attention entries are built with publication (Chidimma, 2026-10-14)
- `attention_entries` moves from BUILD_PROMPT 9.1 item 6b to item 7, next to `report_documents`: both are written inside the publish and republish transaction from the same snapshot (BUILD_PROMPT 9.2 j2), with the results engine's totals, grades and averages.
- **Rejected:** creating the table in 6b and filling it later (its shape depends on the snapshot that item 7 defines).

### D-148. How the form teacher's class sections are stored (2026-10-14; reading of SPEC F22, F10 and section 8)
- `class_report_sections`: one row per arm per term with the status (Open, Submitted, Returned, Published), the revision, the comment that came with the last move, and times school opened (once for the class, 1 to 366). Only the arm's form or class teacher submits, never an assistant; a return needs a comment; a reopen needs a reason. `class_section_actions` keeps every move and is written only by the database.
- `student_term_entries`: one row per pupil (enrolment) per section with the form or class teacher's comment, the head's comment (each up to 300 characters) and times present, which never exceeds times school opened (checked from both sides). Teacher fields change only while the sections are Open or Returned; the head's comment, entered on the publish screen (F10), changes until the class is published. Entries are never deleted; a field is cleared instead.
- `student_trait_ratings`: one rating per pupil per trait, linked to the school's own trait (new ratings only for active traits) and to its 1 to 5 key; locked with the teacher fields.
- Whether every pupil is complete depends on the blocks the active template shows (F10), so that check comes with templates (item 7) and the publish step. The database checks who moves the sections, the locks and the numbers, and records the author of every entry and rating from the signed-in user.

### D-149. A report's QR code is kept on the report document (Chidimma, 2026-10-14)
- PDFs are regenerated from the snapshot (D-058) and must print the same QR code each time, which its hash alone cannot give back. So the plain code is stored on the report document, which only that school's users can read (it is printed on the card anyway). `verification_tokens` keeps only the SHA-256 hash (D-073), and the verification role can only call the lookup function, never read the tables.
- **Rejected:** deriving the code from the server's secret key (never stored, but changing that key would make newly printed QR codes fail unless every old key were kept).

### D-150. How report templates, report documents, verification and attention entries are stored (2026-10-14; reading of SPEC F11 to F13, F23, D-058, D-061, D-071 to D-077, D-147)
- `report_templates`: each save is a new version for its level, numbered by the database; versions are never changed or deleted, so a published report keeps the version it was issued with; the newest version is the one in use. The style and the settings (JSON, checked against the API's schema, D-061) are stored per version; no templates for a level that is off.
- `report_documents`: one row per pupil (enrolment) per term per revision, with the snapshot (JSON), its SHA-256 hash (worked out by the database from the stored snapshot, so it always matches), the template version, the calculation version, the report ID, the verification code (D-149), the masked name for the verify page (D-074, worked out by the database from the pupil's names) and the status. A report is made only when every sheet of the class is published and its template is for the pupil's level. A new revision keeps the report ID and marks the previous Valid revision Superseded; revoking needs a reason; nothing else ever changes, and reports are never deleted (AC11.1).
- `verification_tokens`: written only by the database when a report is published: the code's SHA-256 hash, one per revision. `verify_report()` takes the code as typed (lowercase, spaces and missing dashes accepted, D-072) and returns only school, masked name, session, term, status, revision, report ID, publication date and whether a newer revision exists; it ignores level switches and school suspension (D-075). It is the only thing the verification role can use.
- `attention_entries`: written in the publish transaction, never changed: one row per finding, linked to the report revision it came from: a subject below the pass mark (score, grade, pass mark, subject teacher), a skill at or below the attention point (the rating word at publication), and one summary row per pupil (number failed, average) for the By student view. Lists read only the rows of each pupil's current Valid report, so a republish replaces them without deleting history (AT-23.1).
- The report ID rule (AT-16.2 shows `GMC-2627-T1-JSS1A-014`) is set with publication in 9.2; the database only checks its shape and keeps it the same across revisions.

### D-151. A correction ticket links to the report revision that fixed it (Chidimma, 2026-10-14)
- When the school resolves a ticket after a correction, the ticket links the pupil's newer report revision for that term, which is what the parent sees ("Revision 2 ... new code") and what AC15.1 asks the ticket to show. The reopen of the subject sheet stays as built; its reason can name the ticket ("Raised by parent in CR-0012", as the design shows).
- **Rejected:** also storing the ticket on the reopened sheet and its revision rows (a CHANGE to the item 6 tables for little gain).

### D-152. How correction requests and uploaded files are stored (2026-10-14; reading of SPEC F15, section 8, D-055 to D-057 and the Corrections and ReportView designs)
- `files` (D-057): one row per uploaded file with its school, purpose (logo, signature, stamp, correction attachment), type (PNG, JPEG or WebP; PDF only for attachments; never SVG), size (up to 1 MB for images, 4 MB for attachments), SHA-256, random storage path under `schools/{school_id}/`, original name (a label only) and uploader. Rows never change. Content checks (magic bytes, Pillow re-save) belong to the upload code. The platform role can store and read logos only (school creation sets the logo), never other files.
- `correction_requests`: numbered per school (shown as CR-0012), about one Valid published report and optionally one subject or learning area on it (none means the whole report), with an issue type (A score looks wrong, A name or detail is wrong, Something else) and an explanation. The requester is the signed-in user with a role the permission matrix allows (school admins, reviewers, teachers, parents; never students); a parent only for their own linked wards. Refused when the school's Correction queue is off.
- Statuses follow SPEC section 8: Open, Investigating, then Resolved, Rejected or Needs more information, which goes back to Investigating when the requester replies (only the requester). Rejecting, asking for more information, resolving and replying each need a message, which comes with the move and is never edited afterwards. Resolving may link the pupil's newer, Valid report revision (D-151). `correction_events` keeps the timeline and is written only by the database.
- `correction_attachments`: one optional attachment per request (F15: "optional attachment"), added by the requester while the request is Open or Needs more information; never changed, so the evidence stays as sent.

### D-153. A fourth database role, app_sender, sends the emails (Chidimma, 2026-10-14; adds to D-137)
- The background email sender logs in as `app_sender`, made by migration with SQL like the other three (no RLS bypass, checked). It reads the email outbox of every school, including the template data it needs to write each email, and marks emails sent, retried or failed. It reads no other table.
- **Rejected:** sending as `app_platform` (the platform role would then read every email's template data, which it otherwise never needs).

### D-154. How notices and the email outbox are stored (2026-10-14; reading of SPEC F17, F18, D-080 to D-086)
- `notices`: school, title, plain-text body, kind (manual or system), pinned, status (Published, Archived), author. Only a school admin posts or edits a manual notice; system notices (results published, invoice paid) may have no signed-in author (a payment webhook) and their text never changes; archiving is final. `notice_audiences` keeps what the admin chose (everyone, roles, classes); `notice_recipients` the people worked out at posting, each a member of the notice's school (AC17.2); `notice_reads` one mark per person, made only by that person. Audiences, recipients and reads never change.
- `email_outbox`: type, address, template, template data (no password, token, secret link or score keys, checked by the database), priority, status (Queued, Sent, Failed), up to 5 attempts, next attempt, cleaned last error, a unique idempotency key (one email per recipient per event, AC18.1), provider message id. Queued becomes Sent (with proof), is retried (one more attempt) or Failed; Failed can be queued again (the super admin's Retry); Sent is final; the content never changes. School users queue their school's emails and see status only; the platform queues platform emails and sees every email's status; only `app_sender` reads template data. `school_id` is empty for platform emails.
- The 95-a-day limit and the order of sending (priority, then oldest) belong to the sender (9.2); the database keeps each email's state honest.

### D-155. How billing is stored (2026-10-15; reading of SPEC F19, D-087 to D-097)
- `pricing_versions` and `pricing_tiers`: each save of the pricing table is a new version, numbered by the database, with its tiers (name, minimum, maximum or open-ended, price in kobo). At commit a version's tiers start at 1, follow on with no gaps or overlaps, and only the last is open-ended (AC19.1). Versions and tiers never change (AC19.5). Only the platform writes them; school users may read them (projected next-term cost).
- `school_subscriptions`: one per school: billing on or off (free pilot) and the status (Free pilot, Active, Due, Overdue, Suspended), written by the platform.
- `invoices`: one term invoice per school per term (plus adjustment invoices), with the snapshot of D-091 in kobo. The database checks the arithmetic: the amount is students times rate, or less exactly when the cliff cap applied. Only the status moves: Unpaid to Paid (only with a succeeded payment of exactly the invoice amount) or Void (with a reason); Paid and Void are final; nothing else changes.
- `payments`: a school admin starts a payment for an unpaid invoice of their school; the database copies the amount from the invoice (never from the request) and fixes the currency at NGN. Only the platform's worker marks it Succeeded (with the verified time and gateway reference, or a note for a manual payment) or Failed; one succeeded payment per invoice; a numbered receipt goes with success.
- `payment_events`: the raw log of signature-verified webhook events, one row per gateway event id (duplicates refused, AC19.7), platform only; only its processing columns change.

### D-156. The audit log and the final database audit (2026-10-15; reading of SPEC F11, BUILD_PROMPT 9.1 items 11 and 12)
- `audit_events`: actor, role at the time, action (`area.action`), target table and id, old and new values, reason, revision and time; school events carry the school, platform events none. Rows are written by the app in the same transaction as the change and never change or get deleted, even by the owner; they never hold password, token or hash keys.
- Item 12 is a test file that checks the whole database: every table has row-level security except the listed platform-level tables, no app role owns or can create tables, every function that runs as the owner fixes its search path and is not open to everyone, and no app role can delete from or rewrite the history and snapshot tables.

### D-157. Billing and audit defaults chosen while building migration 18 (2026-10-15; Chidimma asked for defaults instead of questions)
- A voided term invoice frees its term, so the super admin can issue a corrected one; only one live term invoice per school per term.
- An invoice's plan and rate must be a plan of the pricing version it names (same name and price), so a typo cannot invent a price.
- Receipt numbers are platform-wide and numbered by the database: `SF-RCPT-000001`. Our payment reference is 6 to 64 letters, digits or dashes; Paystack is the only gateway in the MVP.
- Subscriptions are written only by the platform role (grants), with the five SPEC statuses.
- `app_current_user_is_super_admin()` runs as the owner (search path fixed, not open to everyone) so the rules can read the super admin flag whatever the caller can see.
- Audit roles are the six membership roles plus `super_admin` and `system` (webhooks, scheduled jobs). Rows cannot be truncated either.
- `platform_settings` joins the pricing tables and the permission tables on the short list of platform-level tables without row-level security: they hold no school rows and grants keep them read-only for schools.

### D-158. The API core (2026-10-15; reading of BUILD_PROMPT 9.2a, D-015, D-016, D-020, D-021, D-042, D-124, D-126)
- Errors: RFC 9457 `application/problem+json` with `type`, `title`, `status`, `request_id`, and `detail`, `code` or `errors` when useful. Validation errors list only where and why (never the values sent). Database refusals log only the SQLSTATE and our rule name and answer 409 with that name as `code` (403 for a permission refusal, 503 when the database is unreachable, 500 otherwise). A crash answers a plain 500.
- Every request gets a fresh request ID (a caller's `X-Request-ID` is ignored). Headers on every response: `nosniff`, `DENY` framing, `no-referrer`, a `default-src 'none'` content security policy, same-origin resource policy, `no-store`, and HSTS outside local. No CORS at all (same domain, D-015).
- `/api/v1/docs` and `/api/v1/openapi.json` exist only when `APP_ENV=local`. If the settings cannot be read, the app treats itself as production (no docs, HSTS on) rather than crash at import; database routes then fail at request time. (The Docker smoke test starts the image without settings; making start-up fail fast there needs a CHANGE to CI, proposed separately.)
- Logs: one JSON line per event on standard output; keys for passwords, tokens, cookies, sessions, emails, phones, names and scores are redacted, emails inside text become `[email]`; exceptions are logged by type and stack, never by message; the access log records the route template, never the real path or query.
- Database session per request: one transaction, committed before the response (`Depends(get_db, scope="function")`, FastAPI docs checked 2026-10-15), rolled back on error.
- Rate limits: fixed windows counted by `rate_limit_hit()` (migration 19) on an HMAC of the key, each hit in its own short transaction so a failed request still counts; 429 with `Retry-After`. The client IP comes only from `x-vercel-forwarded-for` outside local (Vercel overwrites it to prevent spoofing; vercel.com/docs/headers/request-headers, checked 2026-10-15). `rate_limit_forget_old()` clears day-old buckets (daily cron).

### D-159. Login, sessions and passwords (2026-10-21; reading of BUILD_PROMPT 9.2b, D-033 to D-042, D-081; defaults chosen while building)
- Before anyone is signed in, row-level security shows `app_user` nothing. Migration 20 adds owner-run functions (search path fixed, callable only by `app_user`) that each do one job: find the account a login names (inactive and not-yet-activated accounts are not found), find a live session's account, use up a link, queue a reset email, queue the "password changed" email, show an active school's code, name and colour. `login_throttles` (keyed hashes only) has RLS on with no policies.
- **Argon2id cost:** OWASP's first setting (46 MiB, 1 pass, 1 lane) instead of pwdlib's defaults (64 MiB, 3 passes, 4 lanes), which took about 2 seconds a check on the development machine. Hashes upgrade at the next login if the cost is raised; measure on Vercel at the first staging deploy.
- **Common passwords:** the 9,126 entries of 10 or more characters from SecLists' `100k-most-used-passwords-NCSC.txt` (MIT licence, taken 2026-10-21), bundled in `auth/common_passwords.txt`. Maximum length 128. A new password must differ from the current one (D-134 "Different from your temporary password").
- **One generic answer:** wrong school code, name or password, deactivated, not activated, expired temporary password and throttled all answer 401 `login_failed` ("That login didn't work. Check your details and try again.") after exactly one password check (a dummy hash when no account matched). The paused message (403 `school_paused`) comes only after a correct password, for a suspended school or a paused link to the school.
- **Throttling:** 5 failures free, then 30 s, 1 min, 5 min and 15 min locks, counted per account (so the email and the username share one count) or per typed name when no account matched; cleared by a success; a day without failures starts again. Failed logins are answered as a response, not raised, so the count commits. Per IP: 300 logins per 15 minutes (a school computer lab shares one address), 30 link uses, 10 forgot requests per 15 minutes, 60 school-page lookups a minute; forgot password also sends at most 3 emails an hour per address (silently, same answer).
- **Cookies:** `__Host-sf_session` (HttpOnly) and `__Host-sf_csrf` (readable by our pages), both `Secure`, `SameSite=Lax`, `Path=/`, lasting the session's lifetime. The CSRF token is an HMAC of the session token with its own label, so a token from another session never matches; every state change needs it in `X-CSRF-Token`, and any request with an `Origin` from another site is refused (`csrf_failed`), login included. No CSRF endpoint is needed.
- **Sessions:** refresh swaps the token (absolute end unchanged); change password keeps this session with a new token and ends the others; activation and reset end every session and start a new one (the person is logged in); logout and logout-all delete rows. `last_seen_at` is written at most once a minute.
- **Forgot password** answers 202 with the same text for any input and queues `password_reset` (priority 1, template data `user_id` and `full_name` only) for an active, non-student account with a verified email; the sender makes the link at send time (D-081, sender module). Emails carry the school when the account has exactly one.
- **School login link:** `GET /auth/schools/{code}/public` returns code, name and colour of an active school (404 otherwise); `logo_url` stays empty until uploads (9.2e).
- **Audit:** a self-service password change writes `accounts.password_change` in the current school; the super admin's own change is logged in the JSON log only (`app_user` cannot write platform audit rows).

### D-160. The authorization chain (2026-10-21; reading of BUILD_PROMPT 9.2c, D-018, D-047, D-049 to D-052)
- Dependencies in `authz/deps.py`: `current_session` (cookie, CSRF and Origin on changes, live, not idle, account active; the database now works for the user), `current_principal` (membership chosen, membership and school active; the database now works for the school), `require(permission, feature=...)` (temporary password changed, 403 `password_change_required`; feature on, 404 `feature_disabled`; permission, 403 `permission_denied`). In routes: `ensure_level_enabled()` (404 `level_disabled`), `found()` (404 for a record the caller cannot see, the same as one that does not exist), `require_status()` (409 `wrong_status`) and `require_someone_else()` (403 `separation_of_duties`). The database checks scope, workflow and duties again.
- **Parents in several schools (D-138):** the first active membership by default; an `X-School-Id` header may name another of the person's own memberships, anything else is 404. The school id still comes from a membership, never from data the request supplies about other schools.
- **Public routes** are one explicit list (`PUBLIC_ROUTES`): health, ready, login, the school login page, activate, forgot and reset. Logout and logout-all need only a session (so a paused person can still log out); every other route needs the full chain. A test calls every route the app serves without a session and requires 401 `not_signed_in` from all but that list (FastAPI 0.143 keeps included routers nested, so the check reads the app's OpenAPI description instead of `app.routes`).


### D-161. The super admin's platform module (2026-10-22; reading of BUILD_PROMPT 9.2d, SPEC F03 rule 5, F24, F25, D-051; defaults chosen while building)
- **Two sessions per platform request:** the chain checks the super admin through `app_user` (the session cookie), then the work runs through a second connection as `app_platform` (`DATABASE_URL_PLATFORM`, `platform/deps.py`), which refuses anyone who is not the super admin even before the permission check. `DATABASE_URL_PLATFORM` is optional in settings for now, and the platform pages answer 503 without it; making it required outside local needs a CHANGE (an existing settings test builds staging settings without it).
- **Migration 21:** owner-run functions callable only by `app_platform`, returning numbers or names, never records: `platform_school_usage` (active pupils, active staff, parents, valid published reports, last audited activity), `platform_unpublished_classes` (F25 rule 5's confirmation), `platform_username_taken` and `platform_email_taken` (usernames and emails are platform-wide, D-033, but the platform role cannot see teachers, parents or pupils).
- **Create school** makes the school, six features, four level rows from the school type (Nursery on Skill ratings, the others on Scores; head's title "Head teacher" for Nursery and Primary, "Principal" for Secondary), the subscription (billing on is Active, otherwise Free pilot), the principal (id made in Python, no password) and two queued emails: `activation` (user id, name, username, school code and name) and `school_setup` (school name, code, login path). The sender makes the activation link at send time (D-081). A taken code, username or email answers 409 with a field error (`code_taken`, `username_taken`, `email_taken`) before anything is written. Codes are uppercased before the format check, so `gmc` means GMC. The logo arrives with uploads (9.2e) and the school's grading defaults with the grading module (D-141).
- **School events carry the school:** every platform action on a school writes an audit event with that school's id and `super_admin` as the role, so its Activity tab lists events by the super admin and the system; settings changes carry no school. A suspension's reason is stored in the audit event (`schools` has no reason column). Changing the code needs `confirm: true` (409 `confirmation_needed` first, with the warning text).
- **Levels:** the three toggles (Secondary sets Junior and Senior together); all off is refused (422 `at_least_one_level`, before the commit-time database rule); turning a level off while the active term has unpublished sheets at it needs `confirm: true`, and the 409 names the classes; the school type is worked out from the toggles (a preset or Custom).
- **Login support** finds the person among the school's admins first (404 otherwise) and reaches nobody else: a teacher, parent, pupil or another school's admin is not found (AT-29.2). Changing an admin's email clears `email_verified_at` (the next link verifies it). Temporary passwords are four words from EFF's short word list 1 (CC BY 3.0, `auth/temporary_words.txt`, about 41 bits), shown once, valid 7 days, end every session, and are never written to the audit. Make principal clears the old principal first (one per school).
- **Platform settings:** tabs General (platform name "SchoolFlow", support email and phone), Email (sender name, reply-to), Billing (grace 14 days, invoice due 14 days, fees paid by the platform, cliff protection on: SPEC section 12) and Security (additional admins 2, 0 to 10); stored per key in `platform_settings`, defaults for missing keys, a partial change validated as a whole, unknown keys refused, each change audited with before and after. School defaults, the logo, session length and two-factor login come with their own modules.
- **Logs:** audit log filtered by school, action and person; email log with status columns only (never template data, D-083); payments list; all newest first, 50 a page (at most 200).


### D-162. A school sets itself up (2026-10-22; reading of BUILD_PROMPT 9.2e first part, SPEC F03, F04, F08 rule 0, F12 rule 0, F25; defaults chosen while building)
- **9.2e is built in two parts:** this one (settings, levels, calendar, structure, additional admins, login support) and then people (staff, pupils with CSV import, parents and link requests, assignments, learning areas and skills, uploads).
- **Migration 22:** `app_user` may update `schools` email, phone, address, city, state, country, colour and logo, and `school_levels` assessment mode and head's title, in its own school only; a trigger requires the signed-in person to be an active school admin of that school (the platform role and the owner are not affected). Name, code, status, school type and `enabled` stay the super admin's.
- **Assessment mode:** any level that is on may use Scores or Skill ratings (F08 rule 0). Changing it updates the level's setting at once; the active term's structure takes the new mode only while it is unlocked, otherwise the answer says it applies from next term (AC08.6).
- **Calendar:** session names like 2026/2027 (two years in a row); sessions never overlap; terms 1 to 3 sit inside their session's dates (422 `term_outside_session`) and never overlap each other (409 `terms_overlap`); activating a term deactivates the previous one (AC04.1). Everyone in the school reads the calendar, classes, departments and subjects; school admins change them.
- **Names:** a name already used (classes, arms, departments, subjects, sessions, term numbers; compared without capitals) answers 409 `name_taken`. Deleting something still in use answers 409 with the database rule's name. Ids from another school are not found (404).
- **Additional admins:** only the principal adds (login method: activation email, which needs an email, or a temporary password slip shown once) and removes them; the limit comes from Platform settings (Security, default 2) and is refused with "You can add up to {n} school admins." (409 `admin_limit`). A taken username or email answers 409 `username_taken` or `email_taken`. Removing an admin ends their sessions and deletes their link to the school; the account stays.
- **Login support** (`/school/people/{id}/...`): any school admin for reviewers, teachers, parents and pupils; only the principal for additional admins; nobody in the school for the principal or for themselves (409 `own_account`); an account linked to another school is refused (403 `shared_account`, D-138). Audit actions are `school_admins.*` for admins and `users.*` for everyone else; temporary passwords are never audited.
- **Shared helpers:** `audit/log.write_audit()` and `emails/queue.queue_email()` for new modules. The platform module (D-161) still has its own copies; moving it onto these is a small refactor for a later CHANGE.

---

# Stack Summary (one page, for final approval)

| Layer | Choice | Decision |
|---|---|---|
| Budget rule | Free tiers only until real schools onboard; upgrade list ready | D-00A, D-129 |
| Hosting | One Vercel Hobby project with Services: Next.js at `/`, FastAPI container at `/api`, region London `lhr1` | D-000, D-119 |
| Frontend | Next.js App Router, TypeScript strict, Tailwind mapped to `tokens.css`, shadcn/ui (lucide-react, React Icons where needed), next-themes, next/font, mobile-first | D-001 to D-007 |
| Frontend data | React Hook Form + Zod (browser checks), no global store, server components + TanStack Query, typed client from OpenAPI, per-role layout guards; no Redis (browser cache + private ETags + indexed snapshots) | D-008 to D-012 |
| Backend | FastAPI on Python 3.14 (uv), REST `/api/v1`, RFC 9457 errors, Pydantic with unknown fields rejected, feature modules, pure engines | D-013 to D-016, D-109 |
| Database access | SQLAlchemy 2.x sync + psycopg 3, separate Pydantic schemas, Alembic migrations | D-017, D-023 |
| Database | PostgreSQL 17 on Neon Free (London; production and staging branches), roles owner / app_user / app_platform / app_verifier, RLS via `set_config` per transaction, random UUIDs, immutability triggers, Docker Postgres locally | D-022, D-024 to D-030, D-051 |
| Background work | Postgres outbox + Vercel Queues + daily cron sweep | D-019 |
| Authentication | Custom: Argon2id (pwdlib), passwords 15 (staff, parents) / 10 (students, accepted risk), opaque `__Host-` session cookies hashed in the database, CSRF double-submit, activation 72 h, reset 1 h, temporary 4-word passwords, growing-delay throttling, TOTP for super admins after the core, one school per account | D-032 to D-044 |
| Authorization | Six fixed roles, `area.action` permissions from one file, 9-step check chain (404 across schools), provisioning and scope rules, separation of duties, matrix and ID-swap tests | D-045 to D-053 |
| Files | One private Vercel Blob store behind authorised routes; strict upload rules; PDFs regenerated from immutable snapshots | D-054 to D-059 |
| PDF | WeasyPrint in the FastAPI container, Jinja2 block templates, CSS style presets, bundled fonts, segno QR, Chromium fallback | D-060 to D-070 |
| Verification | Opaque 12-character Crockford Base32 codes, SHA-256 stored, page as designed, rate limited | D-071 to D-077 |
| Email and notices | Resend Free from `notify.meritiaa.com` (Ireland region), school name + School email as Reply-To, outbox with priority, idempotency and 95/day cap; notices with recipients fixed at posting | D-078 to D-086 |
| Payments | Paystack test mode; volume pricing in kobo with cliff protection (verified numbers); versioned plans; invoice snapshots; signed, idempotent webhook + Verify Transaction | D-087 to D-097 |
| Testing | pytest (+ Hypothesis, time-machine, respx) on real Postgres; Vitest + RTL + MSW; Playwright 360/768/1440 × light/dark; axe WCAG 2.2 AA; 95% branch coverage on security-critical modules | D-098 to D-106 |
| Tools | Node 24, **Bun** (package manager and scripts; Node runtime; Vitest), uv, VS Code, Ruff + Pyright, ESLint + Prettier + tsc, pre-commit with gitleaks, Docker | D-107 to D-118 |
| Source control and CI | Public GitHub repo (branch protection, secret scanning, push protection), branch per step, GitHub Actions (all checks + Playwright every push), Dependabot | D-111, D-117 |
| Deploy pipeline | CI → migrations (owner role) → Vercel CLI deploy for `main` and `staging`; previews automatic | D-123 |
| Observability | JSON logs with redaction; Sentry Developer with scrubbing; health and ready endpoints; audit, email and payment tables as lasting records | D-124 to D-126 |
| Backups | Manual `pg_dump` + restore test; Neon Launch on onboarding day | D-031, D-127 |

**Status:** approved by Chidimma on 2026-10-09. Phase 2 complete; Phase 3 (services and accounts) started.
