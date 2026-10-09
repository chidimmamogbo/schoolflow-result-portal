# Technical research: SchoolFlow Result Portal MVP

| | |
|---|---|
| Phase | 1 (BUILD_PROMPT section 5) |
| Date checked | 2026-10-08 |
| Status | Provisional. Nothing here is a decision; every choice is made in Phase 2 with Chidimma's approval and recorded in `DECISIONS.md` |
| Fixed input | Chidimma prefers **Vercel** for deployment (stated 2026-10-08). Every topic below is judged on how well it runs on Vercel |

## How to read this document

Each topic has: the options considered, a comparison against the ten criteria from BUILD_PROMPT section 5, sources, and a provisional recommendation. Ratings are **High / Medium / Low** (higher is better for the project; for "Cost" High means cheap). Where I could not confirm a fact on an official page today, it says **"to verify"**. Versions are not pinned here; we pin exact versions when we install in Phase 4.

The ten criteria, in table order: **Docs** (documentation quality), **Ease** (ease of implementation), **Security**, **Cost** (cost and free tier), **Nigeria** (sign-up and payment from Nigeria), **Speed** (development speed), **Long-term** (fits the full proposal roadmap), **Learning** (learning value for Chidimma), **Deploy** (ease of deployment on Vercel), **Fit** (integration with the rest of the stack).

---

## 0. The Vercel picture (read this first)

Choosing Vercel shapes almost every other topic, so here is what the official docs say today.

| Fact | What it means for us | Source |
|---|---|---|
| The **Hobby (free) plan is "non-commercial, personal use only"** | Fine for building and demoing the capstone. Before a real school pays us, we move to **Pro, $20 per developer seat per month** | [Hobby plan](https://vercel.com/docs/plans/hobby) |
| **FastAPI runs on Vercel** as one Vercel Function (Python 3.12 default, 3.13 and 3.14 available), bundle up to 500 MB | A Python backend is fully supported | [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python) |
| **Services (Beta, all plans)** put a Next.js frontend and a FastAPI backend in **one project on one domain**, for example `/api/*` to FastAPI and everything else to Next.js | Login cookies stay first-party (same domain), and we avoid cross-site cookie and CORS problems | [Services](https://vercel.com/docs/services) |
| **Container Images (Beta, all plans)**: a `Dockerfile.vercel` lets a service install operating-system packages with `apt-get` | This is how we get the system libraries PDF tools need (see section 9) | [Container images](https://vercel.com/docs/functions/container-images), [Docker Python guide](https://vercel.com/kb/guide/vercel-docker-python-apps) |
| **Cron jobs on Hobby run at most once per day**, with up to 59 minutes of drift. Pro allows once per minute | Hobby cron is too slow to drive an email outbox on its own | [Cron usage and pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing) |
| **Queues (Beta, all plans)**: durable topics, automatic retries, delays up to 7 days, idempotency keys, a Python SDK (`vercel-queue`). Hobby includes the first 1,000,000 operations | A good engine for the email outbox and background PDF work (see section 13) | [Queues](https://vercel.com/docs/queues), [Queues pricing](https://vercel.com/docs/queues/pricing) |
| **Blob** storage, Hobby includes 1 GB, 10 GB transfer; **private stores** supported (files served only through our function) | Suitable for logos, signatures, stamps and correction attachments (see section 11) | [Blob pricing](https://vercel.com/docs/vercel-blob/usage-and-pricing) |
| Request and response bodies are limited to **4.5 MB** per function call | Upload limits for logos and attachments must stay under this, or use Blob client uploads | [Docker Python guide](https://vercel.com/kb/guide/vercel-docker-python-apps) |
| Functions scale to zero when idle; container functions scale down after 5 minutes without traffic in production | Cold starts on demo day; the warm-up checklist covers it | [Container images](https://vercel.com/docs/functions/container-images) |

**Risk to note:** Services, Container Images and Queues are all **Beta**. Mitigation: keep the backend a plain FastAPI app in a standard Dockerfile, with the outbox in our own database table. If a beta feature fails us, the same container runs unchanged on another host (Render, Fly.io, Railway), and the outbox still works with a different trigger.

---

## 1. Authentication

**Needs:** login only (no sign-up), login by email or username, student login by school code plus username or admission number, generic errors, activation links, temporary passwords with forced change, reset rules that differ by role, sign out of all devices, two-factor for super admins later.

**Options:** (A) custom auth in our FastAPI backend; (B) Clerk; (C) Auth0; (D) Supabase Auth.

| Criterion | A. Custom in FastAPI | B. Clerk | C. Auth0 | D. Supabase Auth |
|---|---|---|---|---|
| Docs | High (OWASP cheat sheets, library docs) | High | High | High |
| Ease | Medium (we write it, with tests) | High for standard flows, Low for our school-code login | Medium | Medium |
| Security | High if we follow OWASP and test it; the risk is ours | High | High | High |
| Cost | High (free) | To verify (per-user pricing) | To verify | Free tier, but ties us to Supabase |
| Nigeria | High (nothing to sign up for) | To verify | To verify | High |
| Speed | Medium | High at first, then slower working around our rules | Medium | Medium |
| Long-term | High (full control as roles grow) | Medium | Medium | Medium |
| Learning | **High** (sessions, hashing, CSRF learned properly) | Low | Low | Medium |
| Deploy | High | High | High | Medium |
| Fit | High (lives beside RBAC and tenants in one database) | Low (users live outside our database and our row-level security) | Low | Medium |

**Why managed providers fit poorly:** our model has student usernames that are unique **per school** and found through a **school code**, a provisioning flow with no self sign-up, reset rules that depend on the role, and a rule that the super admin can reset only school admins. Managed providers model one global identity per user. We would end up writing most of this logic ourselves anyway, while splitting user data across two systems.

**Provisional recommendation: A, custom auth in FastAPI**, following OWASP:
- Passwords hashed with **Argon2id** (OWASP's first choice).
- **Opaque session tokens** (random strings) in `httpOnly`, `Secure`, `SameSite=Lax` cookies. Only a hash of each token is stored in `user_sessions`, so "sign out of all devices" means deleting rows.
- Activation and reset tokens stored hashed, single use, with an expiry.
- Two-factor later with TOTP (authenticator app), which needs no external service.

*Teaching note:* a session cookie works like WordPress's `wordpress_logged_in_` cookie: the browser holds a ticket and the server checks it on every request. The difference is that we store only a hash of the ticket, so a stolen database cannot be replayed.

Sources: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html), [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

---

## 2. Authorization and RBAC

**Needs:** permissions per role per school (`students.create`, `results.approve`, ...), plus **scoped** rules that a plain role check cannot express: assigned sheets, own form class, assistants who enter but never submit, reviewer scope, linked wards, self only, per-level toggles, feature flags, and separation of duties.

**Options:** (A) our own `roles`, `permissions`, `role_permissions` tables plus small "policy" functions per rule; (B) a policy engine library such as Casbin or Oso; (C) checks written inline in each endpoint.

| Criterion | A. Tables + policy functions | B. Policy engine | C. Inline checks |
|---|---|---|---|
| Docs | High (spec section 5 is our matrix) | Medium | High |
| Ease | High | Medium (a new language to learn) | High at first, Low later |
| Security | High (each rule written once and tested) | High | **Low** (easy to forget one endpoint) |
| Cost | High | High | High |
| Nigeria | n/a | n/a | n/a |
| Speed | High | Medium | High then Low |
| Long-term | High | High | Low |
| Learning | High | Medium | Low |
| Deploy | High | High | High |
| Fit | High (FastAPI dependencies) | Medium | Medium |

**Provisional recommendation: A.** Each request passes through a FastAPI **dependency chain**: current user, then school membership, then feature enabled, then level enabled, then permission, then ownership or scope, then workflow state guard. A test matrix (role × endpoint × expected status) proves it. Permission names follow the spec, for example `scores.enter` and `results.publish`.

*Teaching note:* this is WordPress's `current_user_can( 'edit_post', $post_id )` idea, which checks the capability **and** the specific object, enforced on the server for every request.

Sources: [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/).

---

## 3. Assessment modes (Scores and Skill ratings)

**Needs:** one workflow, audit and revision system that serves both score sheets and rating sheets. Rating levels must never compute totals, grades or positions.

**Options:** (A) one `result_sheets` table with a `kind` (`score` or `rating`), shared workflow, and separate entry tables (`scores`, `skill_ratings`) and separate pure calculators; (B) two fully separate subsystems; (C) one generic "entry" table with JSON values.

| Criterion | A. Shared sheet, separate entries | B. Two subsystems | C. Generic JSON entries |
|---|---|---|---|
| Docs | High (spec F08, F26) | High | Medium |
| Ease | High | Low (everything twice) | Medium |
| Security | High (one workflow to secure) | Medium (two to secure) | Medium (weak constraints) |
| Cost | High | High | High |
| Nigeria | n/a | n/a | n/a |
| Speed | High | Low | Medium |
| Long-term | High (CBT or other modes plug in later) | Low | Medium |
| Learning | High | Medium | Medium |
| Deploy | High | High | High |
| Fit | High | Medium | Low (loses database constraints) |

**Provisional recommendation: A.** The state machine, approvals, revisions, publication, verification and corrections are written once. Database constraints keep each entry table strict: score cells have component maximums, and rating cells must reference a point on the rating scale. The results engine has a score calculator only; rating sheets skip it by design.

---

## 4. PostgreSQL / database engine

**Options:** (A) PostgreSQL; (B) MySQL; (C) MongoDB.

| Criterion | A. PostgreSQL | B. MySQL | C. MongoDB |
|---|---|---|---|
| Docs | High | High | High |
| Ease | High | High (you know it) | Medium |
| Security | **High (native row-level security)** | Low (no row-level security) | Low for our needs |
| Cost | High (many free hosts) | High | High |
| Nigeria | High | High | High |
| Speed | High | High | Medium |
| Long-term | High | Medium | Medium |
| Learning | High | Low (familiar already) | Medium |
| Deploy | High (Neon on Vercel Marketplace) | Medium | Medium |
| Fit | High (SQLAlchemy, Alembic) | High | Low (relational data, transactions, triggers needed) |

**Provisional recommendation: A, PostgreSQL.** The spec needs relational data, transactions (all-or-nothing imports and publishing), constraints, **row-level security** and **triggers** that block updates to published snapshots and audit events. MySQL has no row-level security, and MongoDB fits our relational, transaction-heavy model poorly.

Sources: [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [PostgreSQL triggers](https://www.postgresql.org/docs/current/plpgsql-trigger.html).

---

## 5. Multi-tenancy

**Options:** (A) one shared schema, `school_id` on every school-owned table, row-level security; (B) one schema per school; (C) one database per school.

| Criterion | A. Shared schema + RLS | B. Schema per school | C. Database per school |
|---|---|---|---|
| Docs | High | Medium | Medium |
| Ease | High | Low (migrations per schema) | Low |
| Security | High (application check **and** database check) | High | High |
| Cost | High | Medium | Low |
| Nigeria | n/a | n/a | n/a |
| Speed | High | Low | Low |
| Long-term | High (hundreds of schools fine) | Medium | Low |
| Learning | High | Medium | Low |
| Deploy | High | Medium | Low |
| Fit | High (spec section 9 assumes it) | Low | Low |

**Provisional recommendation: A.** Each request opens a transaction and runs `SELECT set_config('app.school_id', :id, true)` (true means "local to this transaction"). The row-level security policies compare each row's `school_id` with that setting. The app connects as a **least-privilege role without `BYPASSRLS`** that does not own the tables, so policies always apply. Migrations run as a separate owner role.

*Teaching note:* in WordPress Multisite each site gets its own `wp_2_posts` tables (option B). We take the other path: one `posts`-style table for everyone, and the database itself refuses to show School A's rows to School B.

**Gotcha to test early:** with connection poolers in transaction mode, a setting made outside a transaction can leak to the next request. Using `set_config(..., true)` inside every transaction avoids this. We prove it with a test.

Sources: [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [set_config](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADMIN-SET), [Neon connection pooling](https://neon.com/docs/connect/connection-pooling).

---

## 6. Backend framework

**Options:** (A) FastAPI (Python); (B) Django + Django REST Framework; (C) NestJS (TypeScript); (D) Next.js route handlers only (no separate backend).

| Criterion | A. FastAPI | B. Django/DRF | C. NestJS | D. Next.js only |
|---|---|---|---|---|
| Docs | High | High | High | High |
| Ease | High | Medium (big framework) | Medium | High at first |
| Security | High (Pydantic validation; we add auth) | High (lots built in) | High | Medium (security logic mixed into the UI codebase) |
| Cost | High | High | High | High |
| Nigeria | n/a | n/a | n/a | n/a |
| Speed | High (you have trained in it) | Medium | Low (new to you) | High |
| Long-term | High | High | High | Medium (LMS, CBT and payroll later want a real API) |
| Learning | High (on your training path) | Medium | Medium | Medium |
| Deploy | High (zero-config on Vercel, or a container) | Medium | Medium | High |
| Fit | High (SQLAlchemy, Alembic, WeasyPrint, pytest) | High | Medium | Medium |

**Provisional recommendation: A, FastAPI.** It is on your training path and deploys on Vercel, either through the Python runtime or as a container service (which the PDF topic favours). Pydantic gives strict input validation. Response models keep sensitive fields such as password hashes out of responses. The OpenAPI docs are automatic, and we turn them off or protect them in production.

Sources: [FastAPI docs](https://fastapi.tiangolo.com/), [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/), [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi).

---

## 7. Frontend framework

**Options:** (A) Next.js App Router; (B) Next.js Pages Router; (C) Vite + React single-page app.

| Criterion | A. Next.js App Router | B. Next.js Pages Router | C. Vite + React SPA |
|---|---|---|---|
| Docs | High (current docs lead with it) | Medium (still supported, less new content) | High |
| Ease | Medium (new mental model) | High (you know it) | High |
| Security | High (server components keep data fetching on the server) | High | Medium (everything runs in the browser) |
| Cost | High | High | High |
| Nigeria | n/a | n/a | n/a |
| Speed | Medium at first, then High | High | High |
| Long-term | High | Medium | Medium |
| Learning | High | Low | Medium |
| Deploy | High (native to Vercel) | High | High |
| Fit | High (Services: Next.js plus FastAPI on one domain) | High | Medium |

**Provisional recommendation: A, App Router, with TypeScript.** For phones on slow connections (the parent report view), server-rendered pages send less JavaScript.

*What changes for you, coming from the Pages Router:*
- `pages/students/[id].tsx` becomes `app/students/[id]/page.tsx`.
- `_app.tsx` becomes `app/layout.tsx`. Layouts nest, which suits our dashboard shell with the sidebar layout wrapping every role's pages.
- `getServerSideProps` disappears: components are **server components** by default and can `await` data directly.
- Anything with clicks or state (the score grid, the sidebar toggle) is marked `"use client"`.
- `loading.tsx` and `error.tsx` give us the empty, loading and error states the design asks for.

Sources: [Next.js App Router docs](https://nextjs.org/docs/app), [Migrating from Pages to App Router](https://nextjs.org/docs/app/guides/migrating/app-router-migration).

---

## 8. UI component system, theming, responsive

**Needs:** accessible collapsible sidebar with icon-only mode and tooltips, mobile drawer, dialogs, tables that become cards on phones, tabs, toasts, switches, light/dark/system with no flash, and **our own design tokens** (`design/design-system/tokens.css`, `design/screens/sf.css`).

**Options:** (A) Tailwind CSS + shadcn/ui (Radix primitives, code copied into our repo); (B) MUI; (C) Mantine; (D) hand-written CSS ported from `sf.css` only.

| Criterion | A. Tailwind + shadcn/ui | B. MUI | C. Mantine | D. Port `sf.css` only |
|---|---|---|---|---|
| Docs | High | High | High | Low (we write the docs) |
| Ease | High (tokens map to CSS variables) | Low (Material look must be undone) | Medium | Medium |
| Security | High | High | High | High |
| Cost | High | High | High | High |
| Nigeria | n/a | n/a | n/a | n/a |
| Speed | High (ready sidebar, sheet, dialog, tabs) | Medium | High | Low (accessibility by hand) |
| Long-term | High (we own the code) | High | High | Medium |
| Learning | High (Tailwind is on your path) | Medium | Medium | Medium |
| Deploy | High | High | High | High |
| Fit | **High** (CSS-variable theming matches `tokens.css` one to one) | Low | Medium | Medium |

**Provisional recommendation: A.** shadcn/ui components are built on Radix primitives, which handle keyboard use, focus and ARIA. The components live in our repo, so we restyle them with **our** tokens, and no default look leaks through. Tailwind reads colours from the same CSS variables as `tokens.css`. Theme switching uses `next-themes` (a small script sets `data-theme` before first paint, so there's no flash of the wrong theme). Only the non-sensitive theme choice is stored on the device. Tables on phones follow the design's cards pattern from `sf.css`.

Sources: [shadcn/ui](https://ui.shadcn.com/docs), [shadcn sidebar](https://ui.shadcn.com/docs/components/sidebar), [Radix primitives accessibility](https://www.radix-ui.com/primitives/docs/overview/accessibility), [Tailwind CSS](https://tailwindcss.com/docs), [next-themes](https://github.com/pacocoursey/next-themes).

---

## 9. PDF generation

**Needs:** school-branded report cards from versioned template JSON, two card types, four styles now (three later), a variable number of assessment columns, fonts Inter, Merriweather and Nunito, always light, fast bulk printing for a class, testable, and running **on Vercel**.

**Options:** (A) **WeasyPrint** (Python, HTML/CSS to PDF); (B) **headless Chromium** via Playwright (HTML to PDF); (C) **ReportLab** (draw the PDF in Python code); (D) **react-pdf** (`@react-pdf/renderer`, PDF from React components).

| Criterion | A. WeasyPrint | B. Chromium (Playwright) | C. ReportLab | D. react-pdf |
|---|---|---|---|---|
| Docs | High | High | Medium | Medium |
| Ease | High (HTML + CSS you already know) | High (HTML + CSS) | Low (coordinates by hand) | Medium (its own layout subset) |
| Security | High (Jinja2 autoescape; no JavaScript runs) | Medium (a full browser; must block network and scripts) | High | High |
| Cost | High | Medium (heavy memory per render) | High | High |
| Nigeria | n/a | n/a | n/a | n/a |
| Speed | High | High | Low | Medium |
| Long-term | High (paged media: `@page`, repeating footers, page numbers) | High | Medium | Medium |
| Learning | High | Medium | Low | Medium |
| Deploy | Medium (needs Pango, so a **container** on Vercel) | Low to Medium (a browser binary in a container; large and slow to start) | High (pure Python) | High (runs in Node) |
| Fit | High (same Python backend, same snapshot data) | Medium | Medium | Medium (render on the Next.js side, away from the snapshot) |

Key facts checked today: WeasyPrint needs **Python 3.10+ and Pango 1.44+**. On Debian the packages are `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`. On Windows, Pango comes from MSYS2. Vercel's plain Python runtime cannot `apt-get`, but a **container service** can.

**Provisional recommendation: A, WeasyPrint, in the FastAPI backend running as a Vercel container service.**
- Report cards are HTML templates (Jinja2 with autoescape) plus print CSS. Styles are CSS presets over the same blocks, and the fonts are bundled as files.
- Tests compare the extracted PDF text and a visual snapshot.
- The PDF renders from the **immutable published snapshot** plus the **template version**, so it is reproducible.
- **Local development on Windows:** you can install Pango with MSYS2, or (simpler and identical to production) run the backend in Docker. We decide this in Round 12.
- **Fallback** if WeasyPrint misbehaves: Chromium (option B) in the same container.

Sources: [WeasyPrint first steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html), [Vercel container images](https://vercel.com/docs/functions/container-images), [Docker Python on Vercel](https://vercel.com/kb/guide/vercel-docker-python-apps), [Jinja2 autoescaping](https://jinja.palletsprojects.com/en/stable/api/#autoescaping).

---

## 10. QR and report verification

**Options:** (A) **opaque random code** (for example 128 bits from `secrets.token_urlsafe`) stored hashed or indexed, looked up on the server; (B) **signed token** (data plus a signature inside the QR).

| Criterion | A. Opaque code + lookup | B. Signed token |
|---|---|---|
| Docs | High | High |
| Ease | High | Medium |
| Security | **High** (no data in the QR; status always live; unguessable) | Medium (data inside the token; revocation still needs a lookup) |
| Cost | High | High |
| Nigeria | n/a | n/a |
| Speed | High | Medium |
| Long-term | High (transcripts and certificates later) | Medium |
| Learning | High | High |
| Deploy | High | High |
| Fit | High (SUPERSEDED and REVOKED must be live states anyway) | Medium |

**Provisional recommendation: A.**
- The QR holds only `https://<domain>/verify/<code>`.
- The public page shows school, masked name, session, term, status, revision and publication date.
- Lookups are rate limited.
- The human-readable report ID (for example `GMC-2026-1T-000123`) is separate from the secret code.
- QR images are generated in Python with **segno** (pure Python, no system libraries).

Sources: [OWASP Insecure Direct Object Reference prevention](https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html), [Python secrets module](https://docs.python.org/3/library/secrets.html), [segno](https://segno.readthedocs.io/).

---

## 11. File storage

**What we store:** school logos, principal signature and stamp images, correction attachments, and possibly generated PDFs.

**Do we need object storage?** Yes. Vercel Functions have no lasting disk: files written at runtime disappear when the instance scales down or redeploys. So uploads must live outside the function.

**Options:** (A) **Vercel Blob** (private store); (B) Cloudflare R2; (C) Supabase Storage; (D) Amazon S3; (E) store files in Postgres (`bytea`).

| Criterion | A. Vercel Blob | B. Cloudflare R2 | C. Supabase Storage | D. S3 | E. Postgres bytea |
|---|---|---|---|---|---|
| Docs | High | High | High | High | High |
| Ease | High (same dashboard) | Medium | Medium | Low | High |
| Security | High (private store; served through our authorised endpoint) | High | High | High | High |
| Cost | High (Hobby 1 GB included) | To verify (free tier) | High (1 GB free) | To verify | Uses database space (Neon free tier is 1 GB) |
| Nigeria | High (same Vercel account) | To verify | High | To verify (needs a card) | High |
| Speed | High | Medium | Medium | Low | High |
| Long-term | High | High | Medium | High | Low |
| Learning | Medium | Medium | Medium | Medium | Medium |
| Deploy | High | Medium | Medium | Medium | High |
| Fit | High | Medium | Medium | Medium | Medium |

**Provisional recommendation: A, a Vercel Blob private store**, behind our own authorised download endpoint. Uploads are validated by content type and size, and stored under random names.

**Store PDFs or regenerate them?** Provisionally **regenerate** from the immutable snapshot plus the template version, and store a **content hash** so we can prove a regenerated PDF matches. This saves storage, and the snapshot is the real record. If bulk class printing turns out slow, we cache PDFs in Blob. (This is the spec's open question, decided in Round 6.)

Sources: [Vercel Blob pricing and private storage](https://vercel.com/docs/vercel-blob/usage-and-pricing), [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

---

## 12. Email provider

**Needs:** set-up, activation, reset, password-changed, result-published and receipt emails; a sending subdomain of `meritiaa.com`; free tier for the demo.

**Options:** (A) **Resend**; (B) **Brevo**; (C) Postmark; (D) Amazon SES.

| Criterion | A. Resend | B. Brevo | C. Postmark | D. Amazon SES |
|---|---|---|---|---|
| Docs | High | Medium | High | Medium |
| Ease | High (simple API, Python SDK) | Medium | High | Low (sandbox approval) |
| Security | High (domain verification: SPF, DKIM) | High | High | High |
| Cost | Free: **3,000/month, 100/day**, 3 domains; Pro **$20/month** for 50,000 with no daily limit (checked today) | Free: **300/day** with Brevo branding; paid from about **$9/month** (third-party sources, **to verify**) | To verify | Very cheap per email, but needs an AWS account (to verify) |
| Nigeria | To verify (sign-up likely fine; paid plans need a card) | To verify | To verify | To verify |
| Speed | High | Medium | High | Low |
| Long-term | High | Medium | High | High |
| Learning | High | Medium | High | Medium |
| Deploy | High | High | High | Medium |
| Fit | High | Medium | High | Medium |

**The daily limit matters:** publishing one JSS 1A class of about 25 students emails around 25 to 50 guardians, the students who have email, and the staff involved. Resend's 100 per day covers one class a day in the demo. The outbox design (section 13) keeps everything else queued and sends it the next day, which the spec already requires.

**Provisional recommendation: A, Resend**, sending from a subdomain such as `mail.meritiaa.com`, so the main domain's reputation stays separate (Round 9). We keep a small `EmailProvider` interface so we can switch to Brevo or a paid plan for real pilots.

Sources: [Resend pricing](https://resend.com/pricing), [Brevo pricing](https://www.brevo.com/pricing/) (the page did not load in my check; figures from [third-party 2026 summaries](https://dreamlit.ai/blog/brevo-review), **to verify**).

---

## 13. Background jobs (email outbox, bulk PDFs)

**Needs:** publishing a class must not wait for emails. Failed emails retry. Daily limits leave mail queued. All of it must work on Vercel, where nothing runs between requests.

**Options:** (A) **outbox table in Postgres + Vercel Queues** to trigger sending, with a daily cron sweep as a safety net; (B) outbox table + **Vercel Cron only**; (C) Celery or RQ with Redis; (D) send inline during the request.

| Criterion | A. Outbox + Queues | B. Outbox + Cron only | C. Celery/RQ + Redis | D. Inline sending |
|---|---|---|---|---|
| Docs | Medium (Beta) | High | High | High |
| Ease | Medium | High | Low (Vercel has a Celery guide, but it adds Redis) | High |
| Security | High | High | High | Medium |
| Cost | High (1,000,000 operations on Hobby) | High | Medium (Redis host) | High |
| Nigeria | n/a | n/a | n/a | n/a |
| Speed | Medium | High | Low | High |
| Long-term | High | Medium | High | Low |
| Learning | High (the transactional outbox pattern) | High | Medium | Low |
| Deploy | High | **Low on Hobby (once a day only)**; High on Pro (every minute) | Medium | High |
| Fit | High (Python SDK `vercel-queue`) | High | Medium | Low (slow publish; lost emails on failure) |

**Provisional recommendation: A.**
- The **outbox table is the source of truth**: rows are written in the same transaction as the publish, so an email is never lost or sent for a rolled-back publish.
- After the commit, we post a small message to a Vercel Queue. A consumer sends the email and marks the row `SENT` or `FAILED`.
- A **daily cron** picks up anything left `QUEUED`, for example after hitting the daily limit. On Pro, the cron can run every few minutes.
- Bulk class PDFs can use the same queue.

*Teaching note:* this is like WordPress's `wp_mail` queue plugins: write the job down first, send it later, and record what happened.

Sources: [Vercel Queues](https://vercel.com/docs/queues), [Queues pricing and limits](https://vercel.com/docs/queues/pricing), [Vercel Cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing), [Transactional outbox pattern](https://microservices.io/patterns/data/transactional-outbox.html).

---

## 14. Payment gateway and subscription billing

**Needs:** Naira, test mode, signature-verified webhooks, server-side verification, one-time payment per invoice, and invoices that are large (for example ₦290,000).

**Options:** (A) **Paystack**; (B) **Flutterwave**.

| Criterion | A. Paystack | B. Flutterwave |
|---|---|---|
| Docs | High | High |
| Ease | High (initialize, redirect, verify, webhook) | High |
| Security | High (HMAC-SHA512 signature in `x-paystack-signature` using the secret key; Verify Transaction endpoint) | High |
| Cost | Local: **1.5% + ₦100, ₦100 waived under ₦2,500, capped at ₦2,000** per transaction (cap and waiver from Paystack support; the 1.5% rate from third-party sources, **to verify** on the pricing page, which blocked my request) | Local: **2% (1.4% + 0.6% platform fee), no cap shown**, plus 7.5% VAT on fees (checked today) |
| Nigeria | High (Nigerian company, test mode needs no compliance documents) | High |
| Speed | High | High |
| Long-term | High (fee collection from parents later) | High |
| Learning | High | High |
| Deploy | High | High |
| Fit | High | High |

**Worked example, a ₦290,000 invoice:** Paystack fee is capped at **₦2,000**. Flutterwave at 2% is **₦5,800** before VAT. For our large termly invoices, Paystack's cap is much cheaper.

**Provisional recommendation: A, Paystack, in test mode.**
- The server initializes the transaction with the invoice amount in **kobo** and a unique reference.
- The webhook verifies the HMAC over the **raw request body** with a constant-time comparison, stores the event (unique event ID), then calls Verify Transaction and checks the amount, currency and reference before marking the invoice PAID.
- Paystack's docs note that webhooks fire for successful transactions. Our callback page also calls Verify, but never marks an invoice paid on the redirect alone.
- One-time payments (not Paystack subscription plans), because the amount changes each term.

Sources: [Paystack webhooks](https://paystack.com/docs/payments/webhooks/), [Paystack verify payments](https://paystack.com/docs/payments/verify-payments/), [Paystack transaction pricing (support)](https://support.paystack.com/en/articles/2130306), [Flutterwave Nigeria pricing](https://flutterwave.com/ng/pricing).

---

## 15. Money handling

**Options:** (A) **integer kobo** everywhere (Python `int`, Postgres `bigint`); (B) Postgres `numeric` + Python `Decimal`; (C) floats.

| Criterion | A. Integer kobo | B. numeric/Decimal | C. Float |
|---|---|---|---|
| Docs | High | High | High |
| Ease | High | Medium | High |
| Security | High (no rounding surprises) | High | **Low (0.1 + 0.2 ≠ 0.3)** |
| Cost | High | High | High |
| Nigeria | High (Paystack amounts are in kobo) | Medium | Low |
| Speed | High | Medium | High |
| Long-term | High | High | Low |
| Learning | High | Medium | Low |
| Deploy | High | High | High |
| Fit | High (spec and BUILD_PROMPT require it) | Medium | Low |

**Provisional recommendation: A.**
- All amounts are whole kobo.
- Volume pricing is `students × price_kobo`, which is exact integer arithmetic.
- The cliff cap is `min(volume_amount, smallest bill on any higher plan)`.
- Formatting to `₦290,000` happens only at display time.
- Receipts are simple HTML pages, plus a PDF made with the same WeasyPrint pipeline.

Unit tests cover AC19.2, AC19.3 and AC19.4 exactly. For example, 642 students: ₦321,000 without the cap, ₦300,300 with it.

---

## 16. CSV import

**Options:** (A) Python's standard `csv` module plus one **Pydantic model per row**, validated on the server, committed in one transaction; (B) pandas; (C) parse in the browser and send JSON.

| Criterion | A. csv + Pydantic | B. pandas | C. Browser parsing |
|---|---|---|---|
| Docs | High | High | High |
| Ease | High | Medium | Medium |
| Security | High (server is the authority; strict types) | Medium (type guessing can mangle admission numbers like `2026/014`) | Low (the browser cannot be trusted) |
| Cost | High | Medium (large dependency) | High |
| Nigeria | n/a | n/a | n/a |
| Speed | High | Medium | Medium |
| Long-term | High | Medium | Low |
| Learning | High | Medium | Medium |
| Deploy | High (no extra weight) | Medium | High |
| Fit | High (same Pydantic used by the API) | Medium | Low |

**Provisional recommendation: A.**
- Every cell is read as text, then validated per row: unknown students, duplicates, out of range, missing fields.
- The preview returns row errors, plus an error CSV to download.
- The commit re-validates and writes in a **single transaction** (all or nothing).
- File size and row limits are enforced, and formula-injection characters are neutralised on export (cells starting with `=`, `+`, `-`, `@`).

Sources: [Python csv](https://docs.python.org/3/library/csv.html), [Pydantic](https://docs.pydantic.dev/latest/), [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection).

---

## 17. Testing

| Layer | Recommended tool | Why |
|---|---|---|
| Backend unit and API | **pytest** + FastAPI `TestClient` / `httpx` | Standard for FastAPI; fixtures for two schools and every role |
| Database tests | pytest against a **real PostgreSQL** (Docker locally, a service container in CI) | Row-level security and triggers only exist in Postgres; SQLite would hide bugs |
| Frontend components | **Vitest** + **React Testing Library** | Fast; tests behaviour the way a user sees it |
| End-to-end | **Playwright** | Runs the 38-step demo at 360, 768 and 1440px, with `colorScheme` light and dark |
| Accessibility | **@axe-core/playwright** | Automated WCAG checks on every page in both themes |
| Coverage | `pytest-cov`; security-sensitive modules (auth, RBAC, tenancy, billing, webhook) target **near 100% branch coverage** | Spec: every security change ships with tests, including denied cases |

Options compared: Jest vs Vitest (Vitest is faster and works with Vite and Next.js tooling), Cypress vs Playwright (Playwright makes multiple viewports, colour schemes and parallel browsers simpler). Ratings: all High on docs, cost and learning; Playwright and Vitest win on speed and fit.

Sources: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [Vitest](https://vitest.dev/), [Testing Library](https://testing-library.com/docs/react-testing-library/intro/), [Playwright emulation](https://playwright.dev/docs/emulation), [axe-core Playwright](https://playwright.dev/docs/accessibility-testing).

---

## 18. Deployment

**Fixed by preference: Vercel.** The question is how to arrange it.

**Options:** (A) **one Vercel project with Services**: Next.js at `/`, FastAPI as a **container service** at `/api`; (B) two Vercel projects (frontend and API on separate subdomains); (C) Next.js on Vercel and the API elsewhere.

| Criterion | A. One project, Services | B. Two Vercel projects | C. API elsewhere |
|---|---|---|---|
| Docs | Medium (Beta) | High | High |
| Ease | High (one deploy) | Medium | Medium |
| Security | **High** (same origin: first-party cookies, no CORS) | Medium (cross-subdomain cookies) | Medium |
| Cost | High (Hobby for demo; Pro for paying schools) | High | Medium |
| Nigeria | High | High | Depends |
| Speed | High | Medium | Medium |
| Long-term | High | High | High |
| Learning | High | Medium | Medium |
| Deploy | High | Medium | Low (two platforms) |
| Fit | High | Medium | Medium |

**Provisional recommendation: A.**
- Environments are local, preview/staging (Vercel preview deployments with a staging database branch) and production.
- **Demo-day notes:** functions scale to zero, and Neon's free compute suspends after 5 minutes idle, so the warm-up checklist hits the health endpoint first.
- **Commercial note:** move to Pro before charging a real school.

Sources: [Vercel Services](https://vercel.com/docs/services), [Hobby plan](https://vercel.com/docs/plans/hobby), [Container images](https://vercel.com/docs/functions/container-images).

---

## 19. Database hosting

**Options:** (A) **Neon** (also available through the Vercel Marketplace); (B) **Supabase**; (C) a separate Postgres host.

| Criterion | A. Neon | B. Supabase |
|---|---|---|
| Docs | High | High |
| Ease | High (Vercel integration injects env vars) | High |
| Security | High (Postgres roles, RLS, TLS) | High |
| Cost | Free: **1 GB per project**, 100 CU-hours per project, **6-hour restore window**, pooling included; paid Launch is pay-as-you-go | Free: **500 MB**, **no automatic backups**, **paused after 1 week inactive**; Pro **$25/month** |
| Nigeria | To verify (free needs no card) | To verify |
| Speed | High (**branches** give each preview its own copy) | High |
| Long-term | High | High |
| Learning | High (plain Postgres) | Medium (much of Supabase's platform we won't use) |
| Deploy | High (Vercel Marketplace) | Medium |
| Fit | High | Medium |

**Provisional recommendation: A, Neon.**
- Compute scales to zero after 5 minutes (it wakes on the next query). There is no week-long pause like Supabase's, and more storage on the free plan.
- **Region:** choose the one closest to West Africa that Neon offers (likely Europe), **to verify** in the dashboard.
- **Backups:** the 6-hour restore window is short, so we add a `pg_dump` backup and a restore test before the demo (spec section 11).
- **Local and test database:** PostgreSQL in Docker, the same major version as Neon.

Sources: [Neon pricing](https://neon.com/pricing), [Supabase pricing](https://supabase.com/pricing), [Neon on Vercel Marketplace](https://vercel.com/marketplace/neon).

---

## 20. Security baseline

Not a choice between products but a checklist to build in from day one, mapped to BUILD_PROMPT section 13.

| Area | Approach | Source |
|---|---|---|
| Standard | OWASP ASVS as the checklist; OWASP Top 10 for awareness | [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) |
| CSRF | Same-origin deployment + `SameSite=Lax` cookies + a CSRF token (double submit) on state-changing requests + `Origin` header check | [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) |
| Headers | CSP, HSTS, `X-Content-Type-Options`, Referrer-Policy, Permissions-Policy, `frame-ancestors` | [OWASP HTTP headers](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html) |
| Rate limiting | **In-memory limits do not work on serverless** (each instance has its own memory). Use a Postgres-backed counter (or Upstash Redis via Marketplace, to verify), plus Vercel WAF rules (Hobby allows 3 custom rules) | [Vercel Hobby limits](https://vercel.com/docs/plans/hobby) |
| Uploads | Allowlist by real content type, size limits, random names, private storage, authorised download | [OWASP File Upload](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) |
| Secrets | Vercel environment variables per environment; only `.env.example` in git; secret scanning in pre-commit and CI | [Vercel env vars](https://vercel.com/docs/environment-variables) |
| SQL | SQLAlchemy bound parameters only; a code search for string-built SQL | [OWASP SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) |

---

## 21. Logging and error monitoring

**Options:** (A) structured JSON logs (Python `logging` with a JSON formatter or `structlog`) **with a redaction filter**, read in Vercel's runtime logs; (B) A + **Sentry** for errors; (C) no extra tooling.

| Criterion | A. JSON logs + redaction | B. A + Sentry | C. Nothing extra |
|---|---|---|---|
| Docs | High | High | n/a |
| Ease | High | High | High |
| Security | High (passwords, tokens, scores and personal data redacted; tested) | Medium (must scrub data before sending to a third party) | Low |
| Cost | High | Free developer tier (**to verify** limits) | High |
| Nigeria | n/a | To verify | n/a |
| Speed | High | High | High |
| Long-term | High | High | Low |
| Learning | High | Medium | Low |
| Deploy | High | High | High |
| Fit | High | High | Low |

**Note:** Vercel Hobby keeps only **1 hour** of runtime logs (Pro 1 day). Errors that matter are easy to miss, which argues for Sentry or a log drain later.

**Provisional recommendation: A now, B optional** (decide in Round 13). The audit timeline, email log and payment events live in our database, so they don't depend on log retention.

Sources: [Vercel Hobby plan (log retention)](https://vercel.com/docs/plans/hobby), [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html), [Sentry Python](https://docs.sentry.io/platforms/python/).

---

## 22. Database migrations and ORM

**Options:** (A) **SQLAlchemy 2.x + Alembic** (with Pydantic schemas kept separate); (B) **SQLModel + Alembic**; (C) Prisma (TypeScript side).

| Criterion | A. SQLAlchemy + Alembic | B. SQLModel + Alembic | C. Prisma |
|---|---|---|---|
| Docs | High | Medium | High |
| Ease | Medium | High | High |
| Security | High (database models and response schemas separate, so a hash can't leak) | Medium (one class is both table and schema; leaks are easier) | High |
| Cost | High | High | High |
| Nigeria | n/a | n/a | n/a |
| Speed | Medium | High | High |
| Long-term | High (full SQL features: RLS policies, triggers, raw SQL in migrations) | Medium (built on SQLAlchemy, so we fall back to it often) | Medium (backend is Python) |
| Learning | High (both on your training path) | High | Low |
| Deploy | High | High | Medium |
| Fit | High | High | Low |

**Provisional recommendation: A.**
- SQLAlchemy 2.x models for tables, separate Pydantic models for requests and responses.
- **Alembic** migrations, including hand-written SQL for RLS policies and immutability triggers.
- We never edit a migration after it has run.

SQLModel stays possible, but our row-level security, triggers and "no leaking fields" rule fit plain SQLAlchemy better.

Sources: [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/), [Alembic](https://alembic.sqlalchemy.org/), [SQLModel](https://sqlmodel.tiangolo.com/).

---

## Summary of provisional recommendations

| # | Topic | Provisional pick |
|---|---|---|
| 0 | Hosting shape | One Vercel project with Services: Next.js + FastAPI container on one domain (Hobby for demo, Pro before paying schools) |
| 1 | Authentication | Custom in FastAPI: Argon2id, opaque sessions in httpOnly cookies, hashed tokens |
| 2 | Authorization | Role/permission tables + FastAPI dependency chain + role × endpoint test matrix |
| 3 | Assessment modes | One sheet and workflow engine; separate score and rating entry tables |
| 4 | Database | PostgreSQL |
| 5 | Multi-tenancy | Shared schema, `school_id`, RLS via `set_config` per transaction, least-privilege app role |
| 6 | Backend | FastAPI (Python) |
| 7 | Frontend | Next.js App Router + TypeScript |
| 8 | UI | Tailwind + shadcn/ui (Radix), our tokens, `next-themes` |
| 9 | PDF | WeasyPrint in the FastAPI container (Chromium as fallback) |
| 10 | QR | Opaque random code + server lookup; `segno` |
| 11 | File storage | Vercel Blob private store; regenerate PDFs from snapshots, store a hash |
| 12 | Email | Resend (100/day free) from a `meritiaa.com` subdomain, behind an interface |
| 13 | Background jobs | Postgres outbox + Vercel Queues + daily cron sweep |
| 14 | Payments | Paystack test mode, one-time payments, HMAC webhook + Verify Transaction |
| 15 | Money | Integer kobo |
| 16 | CSV | `csv` + Pydantic per row, one transaction |
| 17 | Testing | pytest on real Postgres, Vitest + RTL, Playwright (3 sizes × 2 themes), axe |
| 18 | Deployment | As row 0; environments local, preview/staging, production |
| 19 | DB hosting | Neon (+ `pg_dump` backup); Docker Postgres locally |
| 20 | Security | OWASP ASVS checklist; Postgres-backed rate limits; CSRF token + SameSite |
| 21 | Logging | JSON logs with redaction; Sentry optional |
| 22 | ORM and migrations | SQLAlchemy 2.x + Alembic, separate Pydantic schemas |

## Open items to verify before Phase 3

- Paystack's current 1.5% local rate on its pricing page (the page blocked automated reading).
- Brevo free plan details on its official page.
- Sentry free tier limits.
- Clerk and Auth0 pricing (only needed if we reconsider managed auth).
- Neon region closest to Nigeria.
- Whether each provider accepts sign-up and card payment from Nigeria.
