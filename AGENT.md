# AGENT.md: SchoolFlow Result Portal

Instructions for any coding agent working in this repo. Project state and progress live in `MEMORY.md`; read it at the start of every session.

## What this is

SchoolFlow Result Portal (planning name ResultChain): a results-first, multi-school SaaS for Nigerian nursery, primary and secondary schools, built around the "Audit-ready Result Trust Chain". Only the MVP (features F01 to F26) is built now; the wider school management system and LMS is roadmap.

The owner is Chidimma, a WordPress developer learning TypeScript, Next.js, React, Python, FastAPI, PostgreSQL and Tailwind. **Teach while building**: for every file say what it is, why it exists, where it lives and how it connects; explain each new concept plainly before using it, linking it to WordPress, PHP or MySQL where that helps, with Nigerian school examples.

## Sources of truth

| Question | Source |
|---|---|
| Behaviour (features, roles, permissions, state machines, data model, 38-step demo) | `docs/SPEC.md` (v0.5) |
| Process, phases, build inventory, security gate | `docs/BUILD_PROMPT.md` |
| Why the MVP looks like this | `docs/Revised_Two_Week_Results_Trust_Chain_MVP.md` |
| Long-term vision | `docs/School_Management_Platform_Capstone_Proposal.md` |
| Look, feel, screens | `design/README.md`, `design/design-system/`, `design/screens/` |
| Exact labels (menus, titles, tabs, buttons, settings, messages) | `design/NAVIGATION_AND_SETTINGS.md` |

When the spec, the build prompt and the design disagree, stop and ask Chidimma. On behaviour the spec wins over a screen.

## Working rules

1. **One step at a time.** Do exactly one step, explain it, then stop and wait for `next`, `done`, `approve` or a question.
2. **Exact commands for Git Bash on Windows 11**, each in its own block with what it does and the expected output. When a command fails, help read the error before fixing it.
3. **Tests first.** State the behaviour in one sentence, write the test (with at least one denied or invalid case for anything touching security, tenants, accounts or data), show it red, write the minimum code, show it green, refactor, commit.
4. **Change protocol** (`docs/BUILD_PROMPT.md` section 10) before modifying anything already built; append approved blocks to `CHANGES.md`. Database changes always get a new migration.
5. **Facts come from current official docs**, linked with the date checked. Say "not sure, check here" rather than guess versions, APIs, prices, URLs or dashboard paths.
6. **Fictional data only** in seeds, tests, prompts and screenshots.
7. **Small commits** after every green step: `feat:`, `test:`, `fix:`, `refactor:`, `docs:`, `chore:`, `security:`.
8. **Plain, human writing** in UI copy, emails and docs, with commas, colons or full stops where a dash would go (no em dashes).
9. **Keep docs current:** `MEMORY.md`, `LOG.md`, `DECISIONS.md`, `CHANGES.md`, `docs/RESEARCH_TECH.md`, `docs/SERVICES.md`.
10. **Sessions:** at the start, read `MEMORY.md` and `LOG.md`, then say where we stopped, what is next and roughly how much is left. At the end, finish or safely undo the current step, run the tests, commit, and update `LOG.md` and `MEMORY.md` with the exact next step.
11. **Full scope, always.** "Build after the core" items come last but are still built; tests and security are never cut.

## Non-negotiable rules

- No public registration. The super admin creates school admins; school admins create every other account, only inside their own school.
- Passwords are never emailed, logged or stored in plain text. Activation and reset tokens are hashed, single use and expiring.
- Every school-owned table has `school_id`; every query is tenant-scoped; row-level security is on.
- Authorization is enforced on the server. Hiding a button is never security.
- A disabled feature's endpoints reject requests.
- Teachers see only assigned sheets; form teachers only their own form class; reviewers only their scope; guardians only linked wards; students only themselves.
- Login errors never reveal whether the school code, username or password was wrong. Students never get self-service password reset. The super admin resets school admins only. There is no impersonation.
- Additional school admins cannot add, remove or reset other admins.
- Only the super admin switches report card levels on or off; every request for a level that is off is rejected on the server.
- Class teacher assistants can enter but never submit.
- Skill ratings levels never compute totals, averages, grades or positions; each report keeps the rating scale and skills it was published with.
- Assessment structures add up to 100 and lock per term once scores exist; each result stores the structure it used.
- Students needing attention is built only from published results, is staff-only and is scoped by role.
- Published results are immutable. Corrections create a new revision with a reason.
- Notices and emails go only to the intended audience in the same school. Emails never contain scores.
- Secrets stay on the server: out of the frontend, git and logs.
- Every screen works from 320px upward and in both light and dark mode. PDFs and print are always light.
- Money is stored as integer kobo. Payment amounts come from server-side invoices, never the browser.
- An invoice is marked paid only after a signature-verified webhook and a server-side transaction check. Webhooks are idempotent.
- Only the super admin changes pricing; pricing is volume only, with cliff protection; issued invoices never change price.
- Payment gateway secret keys stay on the server; only test keys in the MVP.
- Every security-sensitive change ships with tests, including denied cases.

## Design rules

Read `design/README.md` (section "Rules that must carry into the build") before any UI work. In short: copy every label word for word from `design/NAVIGATION_AND_SETTINGS.md` and ask before inventing one; colours, type, spacing and radius come only from the design tokens; every status shows an icon and a word; 44px touch targets, 14px minimum body text on phones, a visible 2px focus ring; money as `₦321,000`, dates as `5 Jan 2027`.

## Stack and commands

Not chosen yet. Stack decisions are made in Phase 2 and recorded in `DECISIONS.md`; this section gets the agreed stack, repo layout and run/test commands once Phase 4 scaffolds the repo.
