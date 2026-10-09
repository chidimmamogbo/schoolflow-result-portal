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
