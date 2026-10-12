# MEMORY.md: project state

The living record of where the project stands. Update it at the end of every session and whenever a decision is made. Rules live in `AGENT.md`; the session-by-session diary lives in `LOG.md`; decisions with full reasoning live in `DECISIONS.md`.

## Where we are

| | |
|---|---|
| Last updated | 2026-10-12 (end of Session 4) |
| Phase | 1 to 6 done (all planning and design). **Phase 7 (backend, test-first) starts next session** |
| Current step | Phase 6 complete: `docs/ACCEPTANCE_TESTS.md` (128 cases, 54 denied, covers all 44 BUILD_PROMPT Phase 6 items) |
| Next step | **Phase 7, step 1** (BUILD_PROMPT 9.2a core + 9.1 item 1): Postgres 17 in Docker for local dev and tests (`compose.yaml`), pydantic-settings config that fails fast on missing values, SQLAlchemy 2 + psycopg 3 + Alembic wiring, a pytest fixture on the real database with rollback per test, then migration 1 (`schools`, `school_features`, `school_levels`, `platform_settings`) test-first. Each step: tests red, green, commit through a PR |
| Code | Monorepo on GitHub `chidimmamogbo/schoolflow-result-portal` (public). `backend/` FastAPI skeleton (health + tests), `frontend/` Next.js 16.4 skeleton (page, staging banner, tests), CI with 5 required checks + staging deploy. No database code yet. Production deploy job comes in Phase 11, after the Phase 10 security gate |

## Key documents for building (read before Phase 7 work)

| Need | Where |
|---|---|
| What to build, in order | `docs/BUILD_PROMPT.md` section 9 (9.1 database, 9.2 backend modules, 9.3 frontend routes) |
| Behaviour and rules | `docs/SPEC.md` v0.5.1 (`design/docs/SPEC.md` is an identical copy: copy after every spec edit) |
| Tests each feature must pass | `docs/ACCEPTANCE_TESTS.md` (IDs `AT-<step>.<n>`; fixtures GMC, BSA, RCS) |
| Stack choices and why | `DECISIONS.md` D-001 to D-135, Stack Summary at the end |
| Pages, boards, labels | `docs/UI_REVIEW.md` (route-to-board map, approved label fixes, content for pages without a board) |
| Services, env names, accounts | `docs/SERVICES.md` |

## Phase checklist

- [x] Section 15 step 1: OS confirmed (Windows 11 Pro, Git Bash), source documents read
- [x] Section 15 step 2: MVP scope summarised (20 bullets) and accepted
- [x] Phase 1: technical research, `docs/RESEARCH_TECH.md`
- [x] Phase 2: stack decisions, 13 rounds, `DECISIONS.md` and Stack Summary (approved 2026-10-09)
- [x] Phase 3: services and accounts, `docs/SERVICES.md` (done 2026-10-09)
- [x] Phase 4: install, scaffold, CI, staging skeleton (done 2026-10-12, PRs #1 to #13)
- [x] Phase 5: UI/UX review, `docs/UI_REVIEW.md` (2026-10-12; item 8 open)
- [x] Phase 6: `docs/ACCEPTANCE_TESTS.md` (2026-10-12, 128 cases)
- [ ] Phase 7: backend, test-first
- [ ] Phase 8: frontend, test-first
- [ ] Phase 9: end-to-end demo flow (all breakpoints, both themes)
- [ ] Phase 10: security gate, `docs/SECURITY_AUDIT.md`
- [ ] Phase 11: production deploy and demo
- [ ] Build after the core: Bold Banner, Ink Saver, Cumulative styles; platform announcements; super admin two-factor login

## Decisions so far

Decided in the spec (not up for debate unless Chidimma reopens them): volume pricing with cliff protection on; 1,000 students is Standard; one payment gateway in test mode; student login by school code; super admin resets school admins only; up to 2 additional admins; nursery report cards in scope with Scores or Skill ratings per level; Primary grading A to F; "Teaches all subjects" plus up to 2 assistants; flexible pace.

Frontend (Round 1, approved 2026-10-09): Next.js App Router, TypeScript strict, Tailwind mapped to `tokens.css`, shadcn/ui (lucide-react icons, React Icons allowed where needed), next-themes, next/font, mobile-first, React Hook Form + Zod (Pydantic is the authority), no global state library, server components + TanStack Query + typed client from OpenAPI. Full entries in `DECISIONS.md`.

Backend (Round 2, approved 2026-10-09): FastAPI, Python 3.12+, REST `/api/v1` on the same domain via Vercel Services, RFC 9457 errors, Pydantic with unknown fields rejected, SQLAlchemy 2.x sync + psycopg 3 with separate Pydantic schemas, auth dependency chain, outbox + Vercel Queues + daily cron, pydantic-settings, JSON logs with redaction, Postgres-backed rate limits.

Database (Round 3, approved 2026-10-09): PostgreSQL 17, Alembic, Neon Free (production + staging branches; Neon Launch or move on onboarding day), London region (Neon aws-eu-west-2 + Vercel lhr1, latency test in Phase 3), roles owner/app_user/app_verifier, `set_config` per transaction, random UUIDs, immutability triggers, Docker Postgres locally and in tests, pg_dump backups.

Authentication (Round 4, approved 2026-10-09): custom in FastAPI; Argon2id via pwdlib; **passwords min 15 staff/parents, 10 students (option C, accepted risk)**; opaque `__Host-` session cookie hashed in `user_sessions`; CSRF double-submit; activation 72 h, reset 1 h, temp passwords 4 words / 7 days; growing-delay throttling; TOTP for super admins after core; **one school per account (option A)**.

Authorization (Round 5, approved 2026-10-09): six fixed roles (principal = school_admin + is_primary), `area.action` permissions seeded from one file, 9-step check chain (404 for other schools), provisioning "never your own level or above", scope rules incl. assistants enter-not-submit, `app_platform` DB role cannot read pupil scores, separation of duties, matrix + ID-swap + RLS tests.

File storage (Round 6, approved 2026-10-09): one private Vercel Blob store via authorised `/files/{id}` route; PNG/JPEG/WebP (+PDF attachments), no SVG, Pillow re-save, 1 MB / 4 MB; **PDFs regenerated from immutable snapshots (not stored)**, bulk prints temporary 24 h; `FileStorage` interface (local folder vs Blob).

PDF (Round 7, approved 2026-10-09): WeasyPrint in the FastAPI container (Chromium fallback); snapshot + validated template JSON → Jinja2 block HTML → PDF; Score and Skills cards on one engine; styles are CSS presets; fonts bundled; segno QR; same HTML for previews; fixed metadata date; bulk prints queued; pypdf + pypdfium2 tests; backend in Docker on Windows (confirm Round 12).

QR verification (Round 8, approved 2026-10-09): opaque code + lookup; **12-char Crockford Base32 codes `XXXX-XXXX-XXXX` (option B; design shows 8, report the difference when building Verify)**; SHA-256 stored; page exactly as `Verify` design; still verifies when level off or school suspended; rate limits, no-store, noindex.

Email and notices (Round 9, approved 2026-10-09): Resend Free (100/day) behind `EmailProvider`; send from `mail.meritiaa.com`; **school name as sender name + School email as Reply-To** (custom sending domain per school = later paid add-on); outbox with priority, idempotency key, 95/day cap, 5 retries; tokens minted at send time; notices with recipients fixed at posting, pinned reach new members, 60 s unread refresh, plain text only.

Payments (Round 10, approved 2026-10-09): Paystack test mode; volume pricing in kobo; cliff caps ₦250,000 / ₦300,300, numbers verified by script; versioned plans; one invoice per school per term with snapshot; redirect only polls; webhook = raw-body HMAC + unique event + queued Verify Transaction + amount/currency/reference checks; numbered receipts; platform pays fees.

Testing (Round 11, approved 2026-10-09): pytest + TestClient + pytest-cov + Hypothesis + time-machine + respx; real Postgres 17 in Docker with rollback per test; Vitest + RTL + MSW; Playwright 3 sizes × 2 themes; axe WCAG 2.2 AA; 95% branch coverage on security-critical modules.

Dev tools (Round 12, approved 2026-10-09): Node 24 LTS; **Bun 1.4.2 as package manager and script runner** (Node stays the runtime; tests via Vitest with `bun run test`, never `bun test`); Python 3.14 via uv; monorepo frontend/ backend/ design/ docs/; **public GitHub repo** with branch protection, secret scanning, push protection; Postgres in Docker, backend native, PDF tests in Linux container; Ruff + Pyright, ESLint + Prettier + tsc; pre-commit with gitleaks; GitHub Actions incl. Playwright every push.

Deployment and monitoring (Round 13, approved 2026-10-09): environments local / staging / previews / production with separate secrets; Paystack test webhook on staging until the demo; GitHub Actions does CI → migrations → Vercel CLI deploy for main and staging; no keep-alive pinging; Sentry Developer with scrubbing; `/health` + `/health/ready`; manual pg_dump backups (never GitHub artifacts). Full Stack Summary at the end of DECISIONS.md.

**Budget rule (D-00A, Chidimma 2026-10-09): free tiers only (Vercel Hobby incl. cron, Neon Free, Resend Free, Blob Free, Paystack test). Upgrade only when onboarding real schools.** Every recommendation must fit free limits.

Rest of the stack: not decided yet. **Preference stated 2026-10-08: Chidimma prefers Vercel over Render for deployment.** Research treats Vercel as the baseline host. Caveat: Vercel Hobby is non-commercial only (fair use guidelines), so a paying school needs Pro ($20 per user per month, checked 2026-10-08). Confirm in Round 13. Store PDFs or regenerate from snapshots: decided, regenerate (D-058).

## Facts worth remembering

- **Daily commands.** Backend (in `backend/`): `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`. Frontend (in `frontend/`): `bun run test` (never `bun test`), `bun run lint`, `bun run typecheck` (`next typegen && tsc`), `bun run format:check`, `bun run build`, `bun run audit`. Use `bunx`, not `npx`.
- **Git flow.** `main` is protected: pull request, 5 required checks (GitHub Actions app 15368), up to date, linear, squash only, admins included. Update staging with `git switch staging && git merge --ff-only origin/main && git push`.
- **Git Bash clipboard trap (2026-10-11):** Windows programs such as `gh` receive nothing from `< /dev/clipboard`. Always pipe: `cat /dev/clipboard | gh secret set NAME --env ENV`, and check the length first with `cat /dev/clipboard | wc -c`.
- **Git Bash path trap:** commands with an argument starting with `/` (for example `vercel api /v9/...`, `gh api /advisories/...`) get rewritten to `C:/Program Files/Git/...`. Prefix with `MSYS_NO_PATHCONV=1` or drop the leading slash for `gh api`.
- **Vercel CLI side effects:** `vercel link` appended `.vercel` and `.env*` to the root `.gitignore`, and the trailing `.env*` silently ignored every `.env.example`. Check `.gitignore` after any `vercel link` or `vercel env pull`.
- **Vercel:** project `schoolflow-result-portal` (team `chidimma2`), Services: Next.js + FastAPI container in `lhr1`. The very first deployment (from a feature branch) was labelled Production; later CLI deploys are Preview. Deployment URLs are behind Vercel Authentication; custom domains are public.
- **Deploy token** `schoolflow-github-actions`: project-scoped, expires **2026-11-10**, stored only in the GitHub `staging` environment. A project-scoped token cannot use `vercel alias set` or `--scope` ("User not found"); the pipeline uses the REST API instead (D-131).
- **Dependency audit:** CI ignores only GHSA-vfj7-8cjw-p6xm (`braces`, dev-only via ESLint, no patch yet). Remove the ignore once patched (D-130).
- **Spec v0.5.1 (2026-10-12, D-135):** report card additions from `docs/REPORT_CARD_RESEARCH.md`; `design/docs/SPEC.md` is kept identical to `docs/SPEC.md` (copy after every spec edit).
- **Pace (2026-10-12):** Chidimma asked for 2 or 3 steps per turn instead of one, and to move fast into code (AGENT.md rule 1 updated). Still stop for decisions, CHANGE `ok`s, secrets and anything outward-facing.
- **Not done yet for Phase 7:** Neon roles (`app_user`, `app_platform`, `app_verifier`, owner) and the Neon `staging` branch were planned "in Phase 4" (`docs/SERVICES.md`) but are **not created**; do it when the first migration is ready to run on staging. No Vercel env values for databases exist yet.
- **Database error text can contain data (found 2026-10-12, Phase 7 step 1):** PostgreSQL's own messages quote values (`invalid input syntax ... "value"`, unique violation `Key (email)=(...)`). `hide_parameters=True` on the engine only hides SQLAlchemy's parameter list. The 9.2a error handler and log redaction must never log or return raw database error text (log the SQLSTATE code instead). Test it there.
- **Phase 7 first-step tools:** Docker 29.8.0 is installed (Docker Desktop must be running); backend tests run natively on Windows against Postgres in Docker (D-031 area, Round 11/12); PDF tests run in the Linux container.
- **Labels:** NAVIGATION section 5 approved 2026-10-12 with fixes listed in `docs/UI_REVIEW.md` section 4; teacher menu is "Result sheets", page title "My result sheets".
- **Change protocol:** every change to something already built (code, CI, config, branch protection, Vercel settings) needs a CHANGE block and Chidimma's `ok` first; it was skipped seven times in Phase 4 (recorded retroactively in `CHANGES.md`).
- **Reminders:** renew the Vercel token before 2026-11-10; re-check Vercel image storage after several deploys (Hobby: 50 images per repo).
- **GitHub runners:** `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19; watch the first CI runs after that date.
- Tools installed (checked 2026-10-09/11): Node 24.21.0, npm 11.19.0, Bun 1.4.2, Python 3.14.7, uv 0.12.16, Git 2.55.0, Docker 29.8.0, WSL (Ubuntu), VS Code 1.139.1. Not installed: pnpm, `py` launcher. Added in Phase 4 (2026-10-09): GitHub CLI 2.102.0, pre-commit 4.6.2 (via `uv tool`), Vercel CLI 63.1.0 (via `bun add -g`, logged in as `chidimmamogbo`, team `chidimma2`).
- Developer machine: Windows 11 Pro, shell Git Bash. Commands use Git Bash syntax (Python venvs activate with `source .venv/Scripts/activate`).
- `docs/SPEC.md` and `design/docs/SPEC.md` are identical copies (hash checked 2026-10-08).
- The design handoff is v0.5 with 110 screen files; BUILD_PROMPT still says "21 screens". Not yet designed: reviewer screens and add-parent screens (`design/README.md`, flows 2 and 7). Handle in Phase 5.
- Superseded v0.3 boards are kept in `design/screens/` for comparison; build from the v0.5 versions (list in `design/README.md`).
- Section 5 of `design/NAVIGATION_AND_SETTINGS.md` holds proposed labels that need Chidimma's sign-off before use.
- Paystack: Chidimma's login also owns the live **meritiaa** business (webhook in use). SchoolFlow must use its own separate business (own keys and webhooks). Never touch meritiaa's settings; always check the selected business.
- GitHub: username `chidimmamogbo`; commits must use `288715556+chidimmamogbo@users.noreply.github.com` (public repo; keep the personal email out of history).
- Domain `meritiaa.com`: DNS in Namecheap shared hosting cPanel Zone Editor (nameservers `dns1/dns2.namecheaphosting.com`); existing website and Namecheap-hosted email in use. Only ever add subdomain records; never touch nameservers, root SPF, MX or root A. `mail.meritiaa.com` is cPanel's mail host: leave it alone. Confirmed names: `schoolflow.meritiaa.com`, `staging.schoolflow.meritiaa.com`, `notify.meritiaa.com` (email).

## Approved differences from the design (list them when each screen is built)

- Verify and VerifyAfter: verification code is 12 characters (`7KQ4-M2XD-P9QA`) instead of the designed 8 (D-072).
- ChangePassword: rule text follows D-036 (15 characters, 10 for students, no letter-and-number rule) instead of "At least 8 characters" (D-134).
- Pages with no board are built from v0.5 patterns (D-132); v0.3 boards get both themes from tokens (D-133).

## Open questions

- None blocking right now.
