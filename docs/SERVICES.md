# SERVICES.md

Every external service, account and API the MVP uses: what it is for, where its credentials live, and who may see them. **Names and purposes only: no secret values ever go in this file or anywhere in git.**

Budget rule (D-00A): free tiers only until real schools onboard. Registration is done one service at a time in Phase 3 (BUILD_PROMPT section 7); each row is marked done when Chidimma confirms.

## Required for the MVP

| # | Service | Purpose | Plan | Status |
|---|---|---|---|---|
| 1 | GitHub | Source control, CI (Actions), secret scanning, Dependabot | Free, public repo | **Done 2026-10-09**: account `chidimmamogbo`, 2FA on, private commit email on |
| 2 | Vercel | Hosting for Next.js and FastAPI (Services), Blob storage, Queues, cron | Hobby | **Done 2026-10-09**: existing Hobby account (already hosts 2 other projects), signed in with GitHub, 2FA on. Note: Hobby usage limits are shared with those projects; the Phase 4 deploy token must be short-lived because it can reach every project in the account |
| 3 | Neon | PostgreSQL database (production and staging branches) | Free | **Done 2026-10-09**: direct Neon account (signed in with GitHub, no Vercel integration), project `schoolflow`, Postgres 17, AWS Europe West 2 (London), default branch `production`. Roles and the `staging` branch created in Phase 4 |
| 4 | Domain DNS for `meritiaa.com` | Subdomains for the app, staging and email sending | Already owned | **Done 2026-10-09**: names confirmed `schoolflow.meritiaa.com` (production), `staging.schoolflow.meritiaa.com` (staging), `notify.meritiaa.com` (Resend). Records added later: notify in service 5, app names in Phase 4. Public lookup 2026-10-09: nameservers `dns1/dns2.namecheaphosting.com` (edit in Namecheap shared hosting cPanel Zone Editor); root A `66.29.146.24` (existing website); MX `mx1/2/3-hosting.jellyfish.systems` (existing email in use); root SPF `v=spf1 +a +mx +ip4:66.29.146.23 include:spf.web-hosting.com ~all`; no DMARC. **Rule: add subdomain records only; never change nameservers, root SPF, MX or the root A record.** Never create these subdomains through cPanel's Subdomains page (it points them at the shared host). Namecheap 2FA on; Zone Editor access confirmed 2026-10-09. `mail.meritiaa.com` already exists (cPanel mail hostname, A `66.29.146.24`): leave it alone and do not use it for SchoolFlow |
| 5 | Resend | Transactional email (activation, reset, results, receipts) | Free | **Done 2026-10-09 (Verified)**: account created; domain `notify.meritiaa.com`, region Ireland (`eu-west-1`); DNS records added in cPanel and confirmed by lookup (DKIM TXT `resend._domainkey.notify`, CNAMEs `rsend.notify` and `send.notify`, DMARC TXT `_dmarc.notify` = `v=DMARC1; p=none;`). Domain verified in Resend. API keys created in Phase 4 (sending access, restricted to `notify.meritiaa.com`, one per environment) |
| 6 | Paystack | School subscription payments | Test mode only | **Done 2026-10-09**: separate **SchoolFlow** business added, test mode, test webhook URL empty (set once staging exists). Background: Chidimma's existing Paystack login (2FA on) owns the live **meritiaa** business, whose webhook is in use. **Never change or reuse meritiaa's keys or webhooks.** SchoolFlow gets its own business under the same login (own keys, own test and live webhook URLs, test mode, no compliance documents). Always check the selected business before copying keys |
| 7 | Sentry | Error monitoring for backend and frontend | Developer (free) | **Done 2026-10-09**: organisation `Meritia`, data stored in the European Union, Data Scrubber + Default Scrubbers + Prevent Storing of IP Addresses on. Projects (`schoolflow-backend`, `schoolflow-frontend`) created in Phase 4 |

Included inside Vercel (no separate sign-up): Vercel Blob, Vercel Queues, Vercel Cron.

Tools installed locally rather than accounts: Docker Desktop, uv, Bun, GitHub CLI (Phase 4).

## Account details (not secret)

| Service | Detail |
|---|---|
| GitHub username | `chidimmamogbo` (repo `github.com/chidimmamogbo/schoolflow-result-portal`, public, created in Phase 4 on 2026-10-09) |
| Vercel account | `Chidimma` (Hobby; usage low on 2026-10-09 with 2 other projects) |
| Sentry organisation | `Meritia` (EU data storage) |
| Paystack | Business **SchoolFlow** (test mode) under the same login as the live meritiaa business |
| Resend | Domain `notify.meritiaa.com`, Ireland, verified |
| Neon project | `schoolflow`, Postgres 17, `aws-eu-west-2` London, default branch `production` |
| Git commit email | `288715556+chidimmamogbo@users.noreply.github.com` (GitHub private address; set with `git config` in Phase 4 so the personal email never appears in the public history) |

## Credentials map

Filled in as each service is registered. Values live only in: local git-ignored `.env` files, Vercel environment settings (per environment), GitHub Actions secrets.

Planned names (finalised in `.env.example` files during Phase 4). Production and Preview (staging) always get **different values**.

| Credential (name only) | Service | Secret? | Used by | Stored in |
|---|---|---|---|---|
| `DATABASE_URL` (`app_user`, pooled) | Neon | Yes | Backend runtime | Vercel env (Production, Preview); local `backend/.env` points at Docker Postgres |
| `DATABASE_URL_PLATFORM` (`app_platform`) | Neon | Yes | Backend `/platform/*` | Vercel env; local `.env` |
| `DATABASE_URL_VERIFIER` (`app_verifier`) | Neon | Yes | Backend public verification | Vercel env; local `.env` |
| `MIGRATION_DATABASE_URL_STAGING`, `MIGRATION_DATABASE_URL_PRODUCTION` (owner, direct) | Neon | Yes | GitHub Actions migrations only | GitHub Actions secrets only |
| `APP_SECRET_KEY` | Generated by us | Yes | Backend (token hashing pepper, CSRF) | Vercel env; local `.env` |
| `RESEND_API_KEY` (sending access, `notify.meritiaa.com` only) | Resend | Yes | Backend email sender | Vercel env; local `.env` (optional, tests use a fake) |
| `EMAIL_FROM_DOMAIN` = `notify.meritiaa.com` | Resend | No | Backend | Vercel env; local `.env` |
| `PAYSTACK_SECRET_KEY` (`sk_test_...`, **SchoolFlow** business) | Paystack | Yes | Backend payments and webhook signature | Vercel env; local `.env` |
| Blob access (OIDC, automatic on Vercel) | Vercel | n/a | Backend file storage | Injected by Vercel; local dev uses the local-folder storage |
| `SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_DSN` | Sentry | No (still kept in env) | Backend, frontend | Vercel env; local `.env` files |
| `SENTRY_AUTH_TOKEN` | Sentry | Yes | CI source-map upload | GitHub Actions secrets only |
| `VERCEL_TOKEN` (with expiry) | Vercel | Yes | CI deploy | GitHub Actions secrets only |
| `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | Vercel | No | CI deploy | GitHub Actions secrets |
| `APP_ENV`, `APP_BASE_URL` | Ours | No | Backend, frontend | Vercel env; local `.env` |

## Onboarding-day upgrades (D-129)

| Service | Upgrade | Why |
|---|---|---|
| Vercel | Pro ($20 per developer seat per month, checked 2026-10-08) | Hobby is non-commercial only; longer logs, per-minute cron, log drains |
| Neon | Launch (pay as you go, checked 2026-10-09) | No compute suspension; up to 7-day restore |
| Resend | Pro ($20/month, checked 2026-10-08) | No daily sending limit |
| Paystack | Go live (business activation) | Real payments |
| Sentry | Stay on Developer until errors outgrow 5,000 | |

## Do not register (not needed, or roadmap)

| Service | Status | Later use |
|---|---|---|
| Flutterwave (second gateway) | Do not register for this yet. It belongs to the post-MVP roadmap. | Alternative gateway or fallback |
| Zoom, Google Meet, Agora, Jitsi, BigBlueButton | Do not register for this yet. It belongs to the post-MVP roadmap. | Live classes (proposal phase 5) |
| SMS providers, WhatsApp Business | Do not register for this yet. It belongs to the post-MVP roadmap. | Parent notifications (proposal phase 7) |
| Clerk, Auth0, Supabase Auth | Not needed: we build authentication ourselves (D-032) | |
| Supabase, Render | Not needed: Neon and Vercel chosen (D-024, D-000) | |
| Upstash Redis | Not needed in the MVP (D-012) | Possible rate limiting at scale |
| Cloudflare R2, Amazon S3 | Not needed: Vercel Blob chosen (D-055) | |
| Brevo, Amazon SES | Not needed: Resend chosen (D-078) | |
| Postman | Not needed: FastAPI `/docs` and `.http` files (D-113) | |
