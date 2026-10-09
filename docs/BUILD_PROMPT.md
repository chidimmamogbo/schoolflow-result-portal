# BUILD_PROMPT.md: SchoolFlow Result Portal MVP

> **How to use this file:** start a new session with your coding agent. Put `SPEC.md`, `Revised_Two_Week_Results_Trust_Chain_MVP.md` (the updated version) and `School_Management_Platform_Capstone_Proposal.md` in `docs/`, unzip the approved UI handoff (`schoolflow-ui-handoff`) into `design/`, save this file as `docs/BUILD_PROMPT.md`, and tell the agent: "Read docs/BUILD_PROMPT.md, docs/SPEC.md, the MVP document and design/README.md, then begin at Section 15."

---

## 1. Your role

Act as my:

- Senior Software Architect
- Full-Stack Engineer
- UX/UI Engineer
- Database Architect
- Backend Engineer
- Frontend Engineer
- QA/Test Engineer
- Security Engineer
- DevOps Engineer
- Technical Researcher
- Software Engineering Tutor
- Coding Agent

**But most importantly, teach me while we build.**

About me: I am Chidimma, a WordPress developer and designer with 7+ years of experience (WordPress, Elementor, PHP, HTML, CSS, JavaScript, Figma). I am training in TypeScript, Next.js, React, Python, FastAPI, PostgreSQL, MongoDB, SQLModel, SQLAlchemy and Tailwind. I want to understand every file we create, not just receive working code. Explain things plainly, connect new ideas to things I already know (WordPress roles and capabilities, PHP forms, MySQL) where that helps, and use Nigerian school examples.

---

## 2. What we are building

**SchoolFlow Result Portal** (planning name ResultChain): a results-first, multi-school platform for Nigerian schools built around an "Audit-ready Result Trust Chain". The full SchoolFlow school management system plus LMS in the capstone proposal is the long-term vision. **Only the MVP is built now.** `SPEC.md` (features F01 to F26) is the source of truth for behaviour, and the approved UI handoff in `design/` is the source of truth for look, feel and exact labels. If this prompt, the spec and the design ever disagree, stop and ask me.

**Pace:** there is no fixed deadline. The target is about two weeks, but we may finish in fewer or more days. We work session by session: each day we do as much as we can, until I am tired or the session limit is reached. Done means working, tested, secured, deployed and demoed. Nothing in scope is dropped to save time.

### MVP scope at a glance

1. Multi-tenant platform for nursery, primary and secondary schools: super admin creates schools, sets each school's **type** (Nursery and Primary, Secondary only, or Nursery, Primary and Secondary) and **report card toggles** per level (Nursery, Primary, Secondary; super admin only, enforced on the server), manages branding and per-school feature flags (`results`, `report_cards`, `parent_portal`, `correction_queue`, `notice_board`, `email_notifications`). Disabled features are rejected by the server.
2. **Login only, no public registration.** Super admin creates each school's Administrator/Principal. The Administrator/Principal creates every other account: Reviewer/HOD, Teacher, Student, Parent/Guardian.
3. Safe login details: email activation links for users with email; one-time temporary passwords (shown once, printable slip, forced change at first login) for users without email. Passwords are never emailed or stored in plain text.
   - **Login page:** tab **Staff and parents** (Email or username, Password) and tab **Student** (School code, Username or admission number, Password). Each school has a login link that pre-fills its school code. Every failed login shows the same generic error.
   - **Password resets:** forgot password by email for everyone except students; students ask their school admin; school admins reset their people; the super admin resets school admins only; resets sign the user out of all other devices. No impersonation.
   - **Additional school admins:** the principal can add school admins such as a vice principal (limit set by the super admin, default 2); they cannot add, remove or reset other admins.
4. School administration: sessions, terms, levels (only those switched on), classes/arms, subjects, departments; class teachers who "teach all subjects" of an arm in one step, plus up to 2 class teacher assistants per arm (enter, never submit); student registration (single and CSV) with class enrolment and per-student subject assignment; teacher registration with subject + class assignments; reviewer/HOD scoping; parent/guardian registration linked to their ward(s).
5. Nigeria-first result engine: **assessment mode per level** chosen by the school (**Scores** or **Skill ratings**; Nursery defaults to Skill ratings); **assessment structures per level** with any number of components from 1 to 8 (CAs, assignment, project, test, practical, exam) whose maximums add up to 100, locked per term once scores exist; editable grading bands per level (A1 to F9 for Secondary, A to F for Primary and scored Nursery); pass mark (default 40); averages; positions with ties; remarks; affective/psychomotor ratings on school traits; validation.
6. Score sheets per subject per class/arm with filters, search by name or admission number, a grid built from the assessment structure, CSV import (preview, row errors, all-or-nothing commit) and CSV export.
7. Approval workflow (DRAFT, SUBMITTED, RETURNED_FOR_CORRECTION, RESUBMITTED, REVIEWED, APPROVED, PUBLISHED) with separation of duties.
8. Immutable audit history and immutable published revisions.
9. Constrained block-based report-card designer with two card types (**Score report card** and **Skills report card**), one template per level, a Head's title setting (Head teacher, Principal and so on), styles (Modern, Classic, Compact, Early Years; Bold Banner, Ink Saver and Cumulative after the core), detailed block settings and template settings, versioned JSON templates. Report ID, revision, publication date and QR are always shown.
10. School-branded PDF report cards with QR/report-ID verification (VALID, SUPERSEDED, REVOKED).
11. Parent and student portals scoped to their own records.
12. Correction and dispute queue linked to new revisions.
13. Results-week exception dashboard.
14. **Notice board** (admin notices targeted by role/class, unread badge, automatic notice when results are published) and **email notifications** to everyone affected when results are published (no scores in emails, queued with retry).
15. **SaaS-style dashboard** for every role with a **collapsible sidebar** (expand/collapse toggle icon, icon-only mode with tooltips, mobile slide-out drawer), header with notice bell, theme toggle and profile menu.
16. **100% responsive** from 320px phones to large desktops.
17. **Dark and light mode** (plus "follow system"), every screen designed and tested in both. PDFs and printing always use the light print design.
18. Privacy-by-design basics from the MVP document.
19. **School subscription billing:** the super admin edits a versioned pricing table (per student, per term, in plans such as Basic, Standard, Premium) using **volume pricing** with **cliff protection** (on by default) and a **price check** that flags cliffs, switches billing on or off per school, and generates termly invoices. The school admin/principal sees their plan, billable students, amount due, next renewal date and invoice history (PAID/UNPAID with receipts), and pays online through a Nigerian payment gateway in **test mode**. Invoices are marked paid only after a signature-verified webhook and a server-side check.

20. **Form teacher tools:** My class with a class broadsheet, class teacher's comments with suggestions, affective and psychomotor ratings, attendance numbers for the report card, report card preview, and submission of the class sections (required before publishing). Principal's comments are entered on the publish screen.
21. **Students needing attention:** generated on publication; By subject and By student views of results below the pass mark, with filters, export and print; scoped by role (school admins all, HOD scope, subject teacher own subjects, form teacher whole class); staff only.
22. **Super admin platform administration:** full Create school form (details, address with state dropdown, unique school code, levels, free colour picker with contrast warning, logo, features, billing, principal's full name, username and email) that sends the principal's activation email and the school's set-up email; school detail tabs (Overview with usage, Features, School admins, Subscription, Invoices, Activity); edit, change code, suspend or reactivate with reason; school admin login support; platform settings (General, Email, School defaults, Billing, Security); payments, audit log and email log.
23. **Skill ratings:** learning areas and skills per level, an editable rating scale (default Excellent, Very good, Good, Fair, Needs improvement) with an attention rating, rating sheets per learning area per class with the same workflow as score sheets, and the Skills report card (no totals, grades or positions).
24. **Build after the core** (nothing dropped; built last, with tests): Bold Banner, Ink Saver and Cumulative template styles; platform announcements; two-factor login for super admins.

Everything else (school fee collection from parents, live payment processing, attendance module, LMS, CBT, live classes, hostel, transport, payroll, SMS, WhatsApp, offline sync, native apps) stays in the roadmap.

---

## 3. Working rules (follow every time)

1. **One step at a time.** Do exactly one step, explain it, then STOP and wait for me to reply `next`, `done`, `approve`, or ask a question. Never run ahead.
2. **Teach as you go.** For every file: what it is, why it exists, where it lives, and how it connects to what we built before. For every new concept (for example RLS, JWT, CSRF, migrations, server components), give a short plain explanation before using it.
3. **Exact commands.** Ask my OS at the start. Every command goes in its own code block with what it does and the output I should expect. If a command fails, help me read the error before fixing it.
4. **Tests first, always** (Section 11).
5. **Change protocol** for any modification to something already built (Section 10).
6. **Do not invent facts.** No made-up library APIs, versions, prices, URLs or dashboard menu paths. When you are not sure, say so and show me where to check in the official docs. Prices, free tiers and dashboards change, so verify them at the time we use them.
7. **No real student data, ever.** All seed and test data is fictional.
8. **Small commits** after every green step, with conventional messages (`feat:`, `test:`, `fix:`, `refactor:`, `docs:`, `chore:`, `security:`).
9. **Keep docs current:** `LOG.md`, `DECISIONS.md`, `CHANGES.md`, `docs/RESEARCH_TECH.md`, `docs/SERVICES.md`.
10. **Writing style** in UI copy, emails and docs: plain, human, natural. No em dashes.
11. **Work session by session.** There is no fixed deadline.
    - **Start of every session:** read `LOG.md`, then tell me where we stopped, what is next, and roughly how much is left.
    - **During the session:** keep going one step at a time for as long as I want to continue.
    - **End of every session** (when I say I'm stopping, or when you notice the session is getting long): finish or safely undo the current step, run the tests, commit, and write in `LOG.md` what we did, the test status and the exact next step, so the next session can start in seconds.
    - Never drop scope to save time. "Build after the core" items come last but are still built. Never cut security or tests.

---

## 4. Phase plan (do not reorder)

| Phase | What happens | Rough guide (not a deadline) |
|---|---|---|
| 1 | Technical research | Day 1 |
| 2 | Stack discussion and decisions (my approval required) | Day 1 |
| 3 | Services, accounts and API registration | Day 1 to 2 |
| 4 | Install tools and scaffold the repo, deploy a staging skeleton | Day 2 |
| 5 | UI/UX design (flows, wireframes, design system, both themes, all breakpoints) | Day 2 to 3 |
| 6 | Acceptance tests written up front | Day 3 |
| 7 | Backend, test-first, one module at a time | Day 3 to 7 |
| 8 | Frontend, test-first, one route/component at a time | Day 7 to 11 |
| 9 | End-to-end demo flow tests (all breakpoints, both themes) | Day 11 |
| 10 | Security gate and full audit | Day 12 |
| 11 | Production deploy, demo prep, documentation | Day 13 to 14 |

The order of building is: **UI/UX first, then backend, then frontend.**

---

## 5. Phase 1: Technical research

Research only what the MVP actually needs. Use **current official documentation** wherever possible (framework docs, provider docs, pricing pages, security guidance such as OWASP). Link every source you rely on and note the date you checked it.

### Topics to research

- Authentication (login by email or username, student login with school code, password reset rules, sign out of all devices, two-factor login after the core)
- Authorization / RBAC (including scoped access for form teachers, class teacher assistants and the Students needing attention list, and per-school report card level toggles)
- Assessment modes: score-based and skill-rating report cards, and how one engine can serve both
- PostgreSQL / database
- Multi-tenancy (tenant isolation, row-level security)
- Backend framework
- Frontend framework
- UI component system (including a collapsible sidebar, responsive layout and dark/light theming)
- PDF generation
- QR / report verification
- File storage
- Email notification (and how to send to many recipients reliably on a free tier)
- Background jobs for the email outbox (and what works on free hosting)
- Payment gateway and subscription billing (Nigerian gateways, test mode, webhooks, fees, compliance for going live)
- Money handling (integer kobo, rounding, receipts)
- CSV import
- Testing (unit, API, component, end-to-end, responsive and theme checks)
- Deployment
- Security
- Logging and error monitoring
- Database migrations

### Criteria for every option

- Current documentation quality
- Ease of implementation
- Security
- Cost and free tier (with limits that would affect a demo or a pilot school)
- Availability and payment in Nigeria where relevant (can I sign up, does it need a foreign card, are there region or latency issues)
- Development speed (no fixed deadline, but we still want to move quickly)
- Long-term suitability (will it survive the full proposal's roadmap)
- Learning value for me
- Ease of deployment
- Integration with the rest of our stack

**Do not choose a technology simply because it is popular.** Also weigh what I already know from my training, since that saves time, but do not let familiarity override security or suitability.

### Output

Write `docs/RESEARCH_TECH.md` with one section per topic: options considered, a comparison table against the criteria, sources, and a provisional recommendation. Then present a short summary to me and wait.

---

## 6. Phase 2: Stack discussion and decisions

Do not silently choose everything. For each important choice:

1. Give the options.
2. Compare them.
3. Recommend one.
4. Explain why.
5. Wait for my agreement where the decision is significant.

Group the discussion into the rounds below. Present one round at a time, wait for my `approve` or changes, then record the decision in `DECISIONS.md` (decision, reason, alternatives rejected, date).

### Round 1: Frontend
- Framework
- Language
- Styling
- UI/component library (must support an accessible collapsible sidebar, drawer on mobile, data tables, dialogs, and theming)
- Dark/light mode approach (including how to avoid a flash of the wrong theme on page load; storing only the non-sensitive theme preference on the device is fine)
- Responsive strategy (mobile-first, breakpoints, how wide tables behave on phones)
- Form handling
- State management, only if necessary
- Data fetching / API client
- Note: my training used the Next.js Pages Router. If you recommend the App Router, explain what changes for me.

### Round 2: Backend
- Framework
- Language
- API architecture (REST structure, versioning, error format, how the frontend talks to it, and whether to proxy the API through the frontend domain so auth cookies stay first-party)
- Validation
- ORM / database access (consider keeping database models separate from response schemas so sensitive fields can never leak)
- Authentication integration
- Background tasks (needed for the email outbox and possibly PDF generation; consider what works on free hosting tiers)

### Round 3: Database
- PostgreSQL or an appropriate alternative (justify against our needs: relational data, transactions, constraints, row-level security, triggers for immutability)
- Migration tool
- ORM
- Database hosting (free tier limits, pausing or expiry rules, backups, connection pooling, region)
- Local development and test database (tests must run against the same engine as production)

### Round 4: Authentication
- Authentication provider or custom authentication (compare at least one managed provider against building it in our backend; consider cost, learning value, control over our login-only, admin-provisioned model, login by email or username, and student login by school code plus username or admission number)
- Username rules and uniqueness (platform-wide for staff and parents, per school for students) and how to avoid revealing which part of a login was wrong
- Session/token strategy (where tokens live, lifetimes, refresh and revocation; tokens must not sit in insecure browser storage)
- Email verification (through activation links)
- Temporary passwords and forced change at first login
- Password reset (self-service by email for everyone except students; school admins reset their people; super admin resets school admins only) and ending other sessions after a reset
- Sign out of all devices
- Two-factor login for super admins (after the core)
- Password hashing algorithm
- Role handling

### Round 5: Authorization
- RBAC design (roles, permissions, role_permissions, scoped per school)
- Permission naming (for example `students.create`, `results.approve`, `notices.post`)
- Account provisioning rules (super admin creates the principal; the principal adds additional school admins up to the limit; school admins create everyone else inside their school only)
- Level toggles enforced on the server (super admin only; requests for a level that is off are rejected)
- Class teacher assistants (enter scores, ratings, comments and attendance for their class; never submit)
- Scoped data rules for form teachers (own form class) and Students needing attention (school admins all, HOD scope, subject teacher own subjects, form teacher whole class)
- School/tenant isolation (application checks plus database row-level security, and how the current school is passed to the database safely)
- Ownership rules (teacher to assigned sheets, reviewer to scope, guardian to linked wards, student to self)
- Server-side authorization on every request (the UI hiding a menu item is never security)

### Round 6: File storage
Determine whether the MVP actually needs external object storage or whether local/deployment storage is enough. Consider what we store (school logos, principal signature and school stamp images, correction attachments, generated PDFs), whether the hosting filesystem survives restarts and redeploys, whether PDFs should be stored or regenerated from immutable snapshots, privacy of children's documents, and cost. Recommend and explain.

### Round 7: PDF
Determine the best approach for generating school-branded report cards from versioned template JSON: compare server-side HTML-to-PDF options, headless-browser rendering, and PDF libraries. Consider fidelity, Nigerian report-card layouts (tables, domains, signatures), two card types (Score report card and Skills report card), several styles (Modern, Classic, Compact, Early Years) driven by block and template settings, a variable number of assessment columns, fonts (Inter, Merriweather, Nunito), deployment requirements (system libraries, memory on free tiers), speed for bulk class printing, and testability.

### Round 8: QR verification
Determine how verification works without putting sensitive student data in the QR code. Consider opaque random codes with server lookup versus signed tokens, guessability and rate limiting, what the public verification page may show (masked name, school, term, status, revision), and how SUPERSEDED and REVOKED states are displayed.

### Round 9: Email and notice board
- Email provider (free tier daily/monthly limits, domain verification, Nigerian sign-up, deliverability)
- Sending domain (I own `meritiaa.com`; discuss using a subdomain)
- Outbox design, retries, and what happens when the daily limit is reached
- Notice board data model and unread counts

### Round 10: Payments and subscription billing
- Payment gateway options for Nigerian businesses (at least Paystack and Flutterwave): Naira support, payment channels (card, bank transfer, USSD), test mode, documentation, webhook security, transaction fees, settlement, and what business documents are needed to go live
- One-time invoice payments versus the gateway's built-in subscription plans (our amount changes every term with the student count)
- Pricing model is decided: **volume pricing** (the school's student count picks the plan and every student pays that plan's price). Do not build graduated pricing
- Cliff protection (a school never pays more than the smallest possible bill on a higher plan) and the price check that lists cliff ranges; show me the numbers for the default prices
- Plan boundary rules (no overlaps, no gaps, inclusive ranges) and pricing versions
- Invoice generation rules (when, which students count, adjustment invoices)
- Webhook verification, idempotency, and server-side transaction verification
- Who absorbs gateway fees (the platform or the school)
- Receipts (PDF using our report-card PDF approach, or a simple page)
- Recommend one gateway and wait for my approval

### Round 11: Testing
- Backend test framework
- Frontend test approach (component tests)
- API testing
- End-to-end testing, including running the demo flow at phone, tablet and desktop sizes in both themes
- Accessibility checks
- Coverage expectations for security-sensitive code

### Round 12: Development tools
- Node.js version
- npm vs pnpm vs bun
- Python version
- uv vs pip vs Poetry
- Git and GitHub (branching, commit style, branch protection, secret scanning, push protection)
- Docker, if needed (local database, deployment image, system libraries for PDFs)
- Postman/Insomnia, if needed (versus the framework's built-in API docs or test files)
- VS Code and useful extensions
- Linters
- Formatters
- Type checking
- Pre-commit hooks (formatting, linting, secret scanning)
- CI (what runs on every push)

### Round 13: Deployment, logging and monitoring
- Frontend hosting, backend hosting, database hosting (free tier behaviour such as sleeping or pausing, and what that means for demo day)
- Environments: local, staging, production
- Logging (structured logs, redaction of personal data)
- Error monitoring, if needed

After all 13 rounds, produce a one-page **Stack Summary** in `DECISIONS.md` and ask for my final approval before Phase 3.

---

## 7. Phase 3: Services, accounts and API registration

After the stack is agreed, identify **every external service, account or API the MVP actually requires**, and nothing more. Likely categories include database provider, authentication provider (only if we chose a managed one), email provider, file storage (only if Round 6 said we need it), frontend hosting, backend hosting, domain/DNS, monitoring (only if we chose it), and source control. Do not add a PDF service unless Round 7 concluded we need one. A **payment gateway account is required** for the MVP (the one chosen in Round 10), in test mode only. Explain the difference between test and live keys, and do not ask me to submit live compliance documents during the MVP.

### For every required or optional service, give me

| Field | What to tell me |
|---|---|
| Name | |
| Purpose | |
| Why we need it | |
| Required for MVP? | Yes / No |
| Optional? | Yes / No, and what we lose without it |
| Free or paid | |
| Expected cost | For the demo, and for one pilot school |
| Registration URL | Official URL, verified |
| Step-by-step registration | Numbered steps: sign up, verify email, enable 2FA, create project, configure, generate keys |
| Credentials we receive | Each key/URL and whether it is public or secret |
| Where credentials are stored | Local `.env` (never committed), hosting provider's environment settings, CI secrets; `.env.example` holds names only |
| Which part of the app uses them | Backend only, frontend build, CI, migrations |
| Security considerations | Least privilege, separate keys per environment, rotation, what must never reach the browser, what to do if a key leaks |

Do one service at a time and wait for `done`. Record everything in `docs/SERVICES.md` (names and purposes only, never secret values).

### Services we must NOT register for now

The MVP now needs **one** payment gateway, for school subscription billing in test mode. Register only the gateway we chose in Round 10. Do NOT tell me to register for a second gateway, Zoom, Agora, Google Meet, Jitsi, WhatsApp, SMS providers or any other service simply because it appears in the full project proposal. First check whether the MVP actually needs it. The MVP document places school fee collection from parents, live payment processing, live-class integrations, SMS/WhatsApp and several other modules outside the two-week build.

For each such service, say exactly:

> "Do not register for this yet. It belongs to the post-MVP roadmap."

Then add it to the roadmap section of `docs/SERVICES.md` with one line on what it will be for later.

---

## 8. Phases 4 to 6: Setup, UI/UX and acceptance tests

### Phase 4: Install and scaffold
1. Install and verify each agreed tool, one at a time, with version checks.
2. Create the repo structure agreed in Phase 2 (a monorepo with separate frontend, backend, design and docs folders unless we decided otherwise).
3. Before the first commit: `.gitignore` for env files, dependencies, build output, uploads and generated PDFs; `.env.example` with variable names only; secret-scanning pre-commit hook.
4. A health endpoint with its test, an empty frontend page with its test.
5. CI running lint, format check, type check, tests, secret scan and dependency audit.
6. **Deploy the empty skeleton to staging** so deployment problems show up on Day 2, not Day 13. Staging uses fictional data only.
7. Write `CLAUDE.md` with the architecture and the rules in Section 12.

### Phase 5: UI/UX design
The approved UI handoff is in `design/` (design system tokens, logos, 21 high-fidelity screens, `NAVIGATION_AND_SETTINGS.md` with the exact labels). Screens for the v0.4 features are being added in the design tool using `DESIGN_UPDATE_PROMPT.md`. Your job in this phase: read the handoff, list every screen in Section 9.3 that has no design yet, and review new screens against usability, accessibility, the spec and the checklist below. Use every label in `design/NAVIGATION_AND_SETTINGS.md` exactly as written.

1. **Role journeys** for super admin, school admin/principal, reviewer/HOD, teacher, parent/guardian and student, as numbered steps, including first login (activation link or temporary password and forced change).
2. **Screen inventory** for every page in Section 9.3: purpose, who sees it, data shown, actions, empty/loading/error states.
3. **Dashboard shell:** sidebar expanded and collapsed states, the expand/collapse toggle icon, tooltips in collapsed mode, mobile drawer, header with school branding, notice bell with unread badge, theme toggle and profile menu. Role-specific menus.
4. **Wireframes at every breakpoint:** small phone (320 to 375px), large phone, tablet, laptop, large desktop. Show how wide tables (score grid, student list) behave on phones.
5. **Design system in both themes:** colour tokens for light and dark (WCAG AA contrast in each), type scale, spacing, radius, shadows, focus rings, status colours for every workflow state and report validity state, form states, table styles, chart colours, and school-branding slots (logo, primary colour) that stay readable in both themes.
6. **Key interactions:** login tabs (Staff and parents, Student with school code), score sheet filters and search, score grid keyboard navigation and inline validation with a variable number of columns, assessment structure editor with a running total, My class broadsheet and student entry form, Students needing attention views, Create school form with colour picker, pricing price check, reason-required dialog, approval action bar, audit timeline, report-card block editor (ordered blocks with show/hide and reorder, not free-form), registration forms (student, teacher, reviewer, parent with ward picker), credential slip for temporary passwords, notice composer with audience selection, notice board, parent low-bandwidth report view.
7. **Print design:** the report card's light, print-friendly layout, independent of the app theme.
8. Two real-world report-card formats (redacted, fictional data) that the block editor must reproduce.
9. Accessibility checklist: labels, keyboard use, focus states, readable sizes, no colour-only meaning, reduced-motion support for sidebar animation.

### Phase 6: Acceptance tests
Write `docs/ACCEPTANCE_TESTS.md` from the 38-step demonstration flow in `SPEC.md`. Each step becomes a given/when/then case. These later become end-to-end tests. Must include at least:

- No register route exists for any role; only login.
- Staff and parents can log in with email or username; students log in with school code plus username or admission number; two schools with the same admission number never mix.
- A wrong school code, username or password all give the same error.
- Forgot password never sends anything for a student account; the Student tab shows "Ask your school admin".
- The super admin can reset a school admin's login (email change, reset link, temporary password, sign out of all devices) but cannot reset a teacher, parent or student.
- The principal can add additional admins up to the limit; additional admins cannot add or reset admins.
- An assessment structure that does not add up to 100 is rejected; a structure is locked for the term once scores exist; the grid shows the level's columns.
- Teacher sheet search finds a student by name or admission number.
- Only the form teacher of a class can open its My class area; times present cannot exceed times school opened; publishing is blocked until required class sections are submitted.
- Students needing attention is generated only from published results and scoped by role; parents and students are denied.
- Create school rejects a duplicate school code; creation queues the principal's activation email and the school's set-up email, neither containing a password; a suspended school's users see the paused message.
- Report ID, revision, date and QR cannot be hidden in any template.
- School type presets set the right report card toggles; only the super admin can change them; a level that is off rejects classes, templates and structures; turning a level off keeps published reports viewable and verifiable; at least one level must stay on.
- Each school can choose Scores or Skill ratings per level; the choice locks per term once entries exist.
- Primary defaults to A to F grading (65 is B); Secondary defaults to A1 to F9.
- "Teaches all subjects" gives a class teacher every subject of the arm, including subjects added later; assistants can enter but cannot submit, and their entries show their name.
- A rating sheet cannot be submitted with any skill unrated; a Skills report card shows ratings and the key and never totals, grades or positions; old reports keep the rating scale they were published with.
- Students needing attention shows skills at or below the attention rating for Skill ratings levels.
- A school admin cannot create a school admin or super admin; a super admin creates the school admin.
- A school admin cannot create users in another school.
- Activation links and reset links are single use and expire; temporary passwords force a change at first login.
- A teacher sees only sheets for their assigned subjects and classes; a reviewer only their scope.
- A guardian sees only linked wards; unlinking a ward removes access immediately.
- A student sees only their own published results.
- School B (results disabled) gets rejected by results endpoints even with a valid login.
- A teacher cannot approve their own sheet; a reviewer cannot silently change scores.
- Missing and out-of-range scores block submission.
- A CSV import (scores or students) with one bad row commits nothing.
- Published results are immutable; a correction creates a new revision; verification shows the old one as SUPERSEDED.
- A revoked report shows REVOKED on the verification page.
- Publishing results creates notices for the right audience only and queues emails that contain no scores.
- Users without email still see the result notice on their board.
- Notices from School A never appear for School B users.
- Every score change, account creation and notice edit appears in the audit timeline.
- Only the super admin can create or edit pricing tiers; overlapping or gapped tiers are rejected; edits create a new pricing version.
- Existing invoices keep their original price after the pricing table changes.
- An invoice's plan and amount match the school's billable student count (tested at 499, 500, 580, 642, 1,000 and 1,001 students, with cliff protection on and off, matching AC19.2 and AC19.3 in the spec).
- The price check lists 251 to 499 and 601 to 1,000 students for the default prices.
- A school admin sees only their own school's subscription, invoices and receipts.
- The payment amount cannot be changed from the browser.
- A webhook with a bad signature is rejected; a repeated valid webhook does not create a second payment; the browser redirect alone never marks an invoice paid.
- A successful test payment marks the invoice PAID, creates a receipt, posts a notice to the school admin and sends a receipt email.
- A school with billing switched off sees no invoices and no payment prompts.
- The demo flow passes at phone, tablet and desktop sizes, in light and dark mode.

---

## 9. What we will build (inventory)

Names below are guides; adapt them to the conventions of the stack we agree on. Build in this order, one item per step, tests first. Tick items off in `LOG.md`.

### 9.1 Database (one migration per logical group)

Every school-owned table has `school_id`, timestamps and non-guessable primary keys.

1. `schools` (email, phone, address, city, state, country, unique `code`, colour, logo, status, `school_type`), `school_features`, `school_levels` (per level: `enabled` set only by the super admin, `assessment_mode`, `head_title`), `platform_settings`
2. `users` (`username`, `must_change_password`, `is_active`, `email_verified_at`), `school_memberships` (`is_primary`), `roles`, `permissions`, `role_permissions`, `user_sessions` (hashed refresh tokens, revocable for sign out of all devices), `account_tokens` (activation and reset, stored hashed, single use, expiring). Unique indexes: staff/parent usernames platform-wide; student usernames and admission numbers per school
3. `academic_sessions`, `terms` (with next term begins), `classes` (with arms and level), `departments`, `subjects`
4. `students`, `guardians`, `guardian_students`, `enrolments`, `student_subjects`, `teacher_assignments` (form-teacher and teaches-all-subjects flags), `class_assistants` (up to 2 per arm), `reviewer_scopes`
5. `grading_scales`, `assessment_structures` (school, level, term, `locked_at`), `assessment_components` (name, label, max score, order), `remark_bands`, `rating_traits`, pass mark on school settings
6. `result_sheets` (score or rating sheets, with the structure or skill set used), `scores`, `result_revisions`, `approval_actions`
6a. `learning_areas`, `skills`, `rating_scales`, `rating_scale_points` (with the attention point), `skill_ratings`, `area_comments`; grading bands per level
6b. `class_report_sections` (form teacher status per class and term), `student_term_entries` (form teacher comment, principal comment, ratings, times school opened, times present), `attention_entries` (generated on publication)
7. `report_templates` (versioned JSON: style, block order, block settings, template settings), `report_documents` (snapshot, revision, status, file reference or regeneration data, content hash), `verification_tokens`
8. `correction_requests`, `correction_attachments`
9. `notices`, `notice_reads`, `email_outbox`
10. `pricing_versions`, `pricing_tiers`, `school_subscriptions`, `invoices` (with `cliff_cap_applied`), `payments`, `payment_events` (raw webhook log)
11. `audit_events` (append-only)
12. Row-level security on all school-owned tables, least-privilege app database role, immutability protection for published snapshots and audit events.

### 9.2 Backend modules and endpoints (versioned, for example `/api/v1`)

For each module: service unit tests, then API tests including denied cases, then implementation.

**a. Core:** settings validated at startup (fails fast on missing values, debug off outside development), database session that sets the current school safely per transaction, structured logging with redaction, standard error format, security headers, locked CORS, rate limiter, `GET /health`.

**b. Auth (login only):**
- `POST /auth/login` with either `{identifier, password}` (email or username, staff and parents) or `{school_code, identifier, password}` (username or admission number, students); rate limited per identifier and IP; one generic error for every failure; must-change-password response when flagged; suspended-school response after a correct login
- `GET /auth/schools/{code}/public` (name, logo and colour for the school login link; rate limited)
- `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`, `GET /auth/me` (user, school, roles, permissions, primary admin flag, form class, enabled features, unread notice count)
- `POST /auth/activate` (activation link: set password, verify email)
- `POST /auth/change-password` (required after temporary password)
- `POST /auth/password/forgot` (same response whether or not the account exists; never sends for student accounts or accounts without a verified email), `POST /auth/password/reset` (ends other sessions, sends a "password changed" email)
- CSRF token endpoint if our session strategy needs one
- **No register endpoint.**

**c. Authorization building blocks:** current user, current school membership, feature-enabled check, permission check, ownership checks, workflow-state guards, separation-of-duties guard.

**d. Platform (super admin only):**
- `GET/POST /platform/schools` (create with the full form: details, code, levels, colour, logo, features, billing, principal full name, username and email; queues the principal's activation email and the school's set-up email), `GET/PATCH /platform/schools/{id}`
- `GET /platform/schools/check-code?code=`, `GET /platform/usernames/check?username=`
- `GET /platform/schools/{id}/usage`, `GET /platform/schools/{id}/activity`
- `POST /platform/schools/{id}/suspend` (reason), `POST /platform/schools/{id}/reactivate`, `POST /platform/schools/{id}/resend-setup-email`, `POST /platform/schools/{id}/change-code` (confirmation required)
- `PUT /platform/schools/{id}/features`
- `PUT /platform/schools/{id}/levels` (school type preset or individual Nursery, Primary, Secondary toggles; at least one on; confirmation when unpublished results exist; audited). School admins have no endpoint that changes levels
- `GET /platform/schools/{id}/admins`; for each admin: `POST .../resend-activation`, `PATCH .../email`, `POST .../send-reset-link`, `POST .../temporary-password` (returned once), `POST .../sign-out-all`, `POST .../deactivate`, `POST .../reactivate`, `POST .../make-primary`. All audited. No endpoint resets teachers, reviewers, parents or students, and there is no impersonation endpoint
- `GET/PATCH /platform/settings` (General, Email, School defaults, Billing, Security; audited)
- `GET /platform/audit-log`, `GET /platform/email-log`, `GET /platform/payments`
- After the core: `POST /platform/announcements`, super admin two-factor setup and verification

**e. School administration (school admin/principal):**
- Settings and branding, logo, principal signature and school stamp uploads (validated)
- Additional school admins (principal only): list, add (username, login method), remove, resend activation, reset; refused beyond the limit
- Sessions, terms, classes/arms (only at enabled levels; requests for a disabled level are rejected), departments, subjects
- Assessment mode per level (`PUT /school/levels/{level}/assessment-mode`, locked per term once entries exist) and head's title per level
- Learning areas and skills per level, rating scale and attention rating (versioned with reports)
- Class teacher assignment with `teaches_all_subjects` (assigns every subject or learning area of the arm, including ones added later) and class teacher assistants (add, remove, up to 2)
- Students: create, update, deactivate, list with search and filters; CSV import preview and commit; enrol in class/arm; assign subjects (class defaults plus per-student changes); move between arms with history
- Teachers: create (sends activation or issues temporary password), update, deactivate; assign subject + class/arm pairs; set form teacher
- Reviewers/HODs: create, scope to department or subjects/classes
- Parents/guardians: create with one or more linked wards; add/remove ward links
- Login support for reviewers, teachers, parents and students: resend activation, send reset link (if they have email), issue temporary password with printable credential slip data (returned once, never stored in plain text), deactivate, reactivate, sign out of all devices
- Every create, update, link, unlink, reset and deactivate writes an audit event

**f. Grading configuration:** grading scales per level (A1 to F9 defaults for Secondary, A to F for Primary and scored Nursery), remark bands, pass mark, rating traits and scale; assessment structures per level (`GET/PUT /school/assessment-structures/{level}`, validates 1 to 8 components and a total of 100, saves for next term when the current term is locked).

**g. Results engine (pure functions, heavily unit tested):** weighted totals, grades, subject/class/overall averages, positions with ties, missing and out-of-range flags, duplicate detection, calculation version.

**h. Score entry and import:** list my sheets (scoped; filter by class, subject, status), create draft, view sheet (columns from the structure; search and filters are client-side), bulk save scores (reason required when changing an existing value), CSV template, import preview, import commit (single transaction), error CSV download, sheet CSV export.

**h1. Rating sheets (Skill ratings levels):** list my rating sheets, view (pupils against skills of the learning area), bulk save ratings and area comments, submit (every skill rated); same workflow endpoints as score sheets. Assistants can save but not submit.

**h2. Form teacher (own form class only; assistants can save, not submit):** `GET /form-class`, `GET /form-class/broadsheet`, `PUT /form-class/attendance-days`, `GET/PUT /form-class/students/{id}/entry` (comment, ratings, times present; validated), `GET /form-class/students/{id}/preview`, `POST /form-class/sections/submit`; school admin `POST /school/classes/{id}/sections/return` (comment).

**i. Approval workflow:** submit, return (comment required), resubmit, review, approve, principal's comments (`PUT /school/publications/{class}/{term}/principal-comments`), publish class + term (only when all sheets approved and required form teacher sections submitted; creates snapshots, PDFs or regeneration records, verification codes, notices and queued emails), reopen with reason (optionally linked to a correction ticket), revoke with reason.

**j. Audit:** readable, filterable school timeline.

**j2. Students needing attention:** generated inside the publish and republish transactions from the snapshot; `GET /attention?view=by_subject|by_student|by_learning_area&session&term&class&arm&subject&teacher` scoped by role (Skill ratings levels list skills at or below the attention rating) (school admins all, HOD scope, subject teacher own subjects in assigned classes, form teacher whole form class); `GET /attention/export.csv`; dashboard counts. Parents and students denied.

**k. Report templates and PDFs:** template CRUD with versioning, one template per enabled level; card type follows the level's assessment mode (Score or Skills report card); head's title; styles (Modern, Classic, Compact, Early Years; Bold Banner, Ink Saver, Cumulative after the core); Skills report card blocks (pupil details, skills table, rating key, attendance, comments, signatures, footer); block order, block settings and template settings validated against a schema; report ID, revision, date and QR cannot be switched off; preview with fictional data; authorised PDF download.

**l. Public verification:** rate-limited lookup returning only school, masked student name, session, term, status, revision and publication date.

**m. Parent and student portal:** linked children only, published reports only, low-bandwidth report view, PDF download; student self-only equivalents.

**n. Corrections:** create, list (scoped), view, update status, validated attachments, reopen linked to ticket.

**o. Notice board:**
- `GET /notices` (only notices addressed to me, in my school, newest first, pinned on top)
- `GET /notices/unread-count`
- `POST /notices/{id}/read`
- `POST /notices`, `PATCH /notices/{id}`, `POST /notices/{id}/archive` (school admin; audience: all, roles, optional classes; audited)
- Automatic notice creation on result publication, addressed to affected students, their guardians, and the relevant teachers and reviewers

**p. Email:**
- Outbox writer used by activation, password reset, result publication and (optionally) new notices
- Background sender with retries and status (queued, sent, failed)
- `GET /email-outbox` for admins (status only, no secrets)
- Emails contain no scores, only a message and a link to log in
- Handling for free-tier daily limits (stay queued, retry later, show status)

**q. Billing (super admin):**
- `GET /platform/pricing` (current version and tiers), `POST /platform/pricing` (save a new version; validates no overlaps or gaps; audited), `GET /platform/pricing/versions`
- `GET /platform/billing/schools` (plan, students, status, current invoice), `PATCH /platform/schools/{id}/subscription` (billing on/off, free pilot, grace period, suspend/reactivate; audited)
- `POST /platform/invoices/generate` (one school or all billable schools for a term), `POST /platform/invoices/{id}/void`, `POST /platform/invoices/{id}/manual-payment` (reference and note; audited)
- `GET /platform/billing/summary` (invoiced, paid, outstanding per term)

**r. Billing (school admin/principal):**
- `GET /school/billing` (plan, billable students, price per student, amount due, due date, next renewal date, status, projected next-term cost)
- `GET /school/invoices`, `GET /school/invoices/{id}`, `GET /school/invoices/{id}/receipt`
- `POST /school/invoices/{id}/pay` (server creates the gateway transaction using the invoice amount and returns the checkout link or reference)
- `GET /school/payments/verify?reference=...` (used after redirect; checks with the gateway server-side, does not trust the browser)

**s. Payment webhook (public, signature-verified):**
- `POST /webhooks/payments`: verify the signature over the raw request body, store the event, ignore duplicates, confirm the transaction with the gateway's API, check amount, currency and invoice reference, then mark the invoice paid, create the payment and receipt, post a notice and queue a receipt email. Always respond quickly; never expose internal errors.

**t. Pricing engine (pure functions, heavily unit tested):** plan lookup, volume calculation, cliff protection cap, price check (lists student ranges where a bigger school pays less), boundary cases, integer kobo, projected cost. No graduated pricing.

**u. Dashboard:** results-week exceptions (including open form teacher sections) plus role-specific summary cards, including the billing card for school admins and Students needing attention cards for school admins and teachers.

**v. Seed and CLI:** create-super-admin command (and a reset-super-admin command); two fictional schools; staff in every role; classes, subjects and 20 to 30 fictional students per demo class; guardians linked to wards; School B as Nursery and Primary (Nursery on Skill ratings with default areas and skills, Primary on Scores with A to F) with a Primary 4A class teacher who teaches all subjects and an assistant; School C as Nursery, Primary and Secondary; a vice principal; JSS and SS assessment structures (SS with CA1, CA2, CA3, Project, Exam); a form teacher with entries; published results that produce Students needing attention entries; sample notices; two report-card templates; the default pricing table; one school on a free pilot and one school with an unpaid invoice.

### 9.3 Frontend routes and components

Build shared pieces first, then pages role by role. For each page: component tests first, then the page, then wire it to the API. Every page must be checked at all breakpoints and in both themes before it is marked done.

**Shared foundations**
1. Theme provider (light, dark, system), theme toggle, no flash of wrong theme
2. Dashboard shell: collapsible sidebar with expand/collapse toggle icon, icon-only mode with tooltips, remembered state, mobile drawer, header (school logo/name, notice bell with unread badge, theme toggle, profile menu with change password and logout)
3. Role- and feature-aware navigation
4. API client (credentials, CSRF if used, error mapping, session refresh)
5. Auth context from `/auth/me`, route guards (UX only; the server is the real gate), forced change-password redirect
6. Responsive data table (scrolls inside its container or becomes cards on phones), forms, reason dialog, status badges, empty/loading/error states, toasts

**Public pages:** `/` (product landing), `/login` (tabs Staff and parents, Student), `/login/[schoolCode]` (Student tab with code pre-filled and school branding), `/school-paused`, `/activate`, `/change-password`, `/forgot-password`, `/reset-password`, `/verify`, `/verify/[code]`, `/privacy`. **No `/register` page.**

**Super admin:** `/platform` dashboard, `/platform/schools`, `/platform/schools/new` (full Create school form with School type and report card toggles), `/platform/schools/[id]` (tabs Overview, Features with Report cards by level, School admins, Subscription, Invoices, Activity), `/platform/settings` (tabs General, Email, School defaults, Billing, Security), `/platform/payments`, `/platform/audit`, `/platform/emails`, `/platform/announcements` (after the core), `/platform/pricing` (pricing table editor and version history), `/platform/billing` (schools, invoices, payments, term totals), `/platform/billing/invoices/[id]`.

**School admin/principal:**
- `/school/dashboard` (results-week exceptions, Students needing attention card, billing card)
- `/school/settings` (branding, signature and stamp images)
- `/school/setup/sessions`, `/school/setup/classes` (levels, classes and arms), `/school/setup/subjects`, `/school/setup/departments`, `/school/setup/grading` (grading bands, remark bands, pass mark), `/school/setup/assessment` (mode and structure per level), `/school/setup/skills` (learning areas, skills, rating scale), `/school/setup/rating-traits`
- `/school/admins` (principal only: additional school admins)
- `/school/students`, `/school/students/new`, `/school/students/import`, `/school/students/[id]` (enrolment, subjects, guardians, login details)
- `/school/teachers`, `/school/teachers/new`, `/school/teachers/[id]` (assignments, login details)
- `/school/reviewers`, `/school/reviewers/new`, `/school/reviewers/[id]` (scope)
- `/school/parents`, `/school/parents/new`, `/school/parents/[id]` (linked wards)
- `/school/approvals`, `/school/publish` (checklist including form teacher sections, principal's comments, preview, publish)
- `/school/attention` (Students needing attention: By subject, By student)
- `/school/notices`, `/school/notices/new`, `/school/notices/[id]`
- `/school/emails` (outbox status)
- `/school/billing` (plan, renewal, amount due, Pay now, invoice history), `/school/billing/invoices/[id]` (invoice and receipt), `/school/billing/callback` (shows "confirming payment" while the server verifies)
- `/school/audit`
- `/school/report-templates`, `/school/report-templates/[id]`
- `/school/corrections`, `/school/corrections/[id]`

**Reviewer/HOD:** `/review` dashboard, `/review/[sheetId]`, `/review/attention`, `/notices`.

**Teacher:** `/teacher` dashboard (attention card), `/teacher/sheets` (grouped by class, filters), `/teacher/sheets/[sheetId]` (score grid or rating grid, search, filters), `/teacher/sheets/[sheetId]/import`, `/teacher/attention`, `/teacher/my-class` (broadsheet; form teachers only), `/teacher/my-class/students/[id]` (comment, ratings, attendance), `/teacher/my-class/preview/[id]`, `/notices`.

**Parent/guardian:** `/parent` dashboard (ward switcher), `/parent/children/[studentId]`, `/parent/reports/[reportId]`, `/parent/corrections`, `/parent/corrections/new`, `/notices`.

**Student:** `/student` dashboard, `/student/reports/[reportId]`, `/notices`.

**Key components (each with its own tests):** `AppShell`, `Sidebar`, `SidebarToggle`, `MobileNavDrawer`, `ThemeToggle`, `NoticeBell`, `NoticeBoard`, `NoticeComposer`, `ResponsiveTable`, `ScoreGrid`, `ImportPreviewTable`, `StudentForm`, `TeacherAssignmentEditor`, `SubjectAssignmentEditor`, `WardLinker`, `CredentialSlip`, `StateBadge`, `ApprovalActionBar`, `ReasonDialog`, `AuditTimeline`, `TemplateBlockEditor`, `ReportCardPreview`, `VerificationResult`, `CorrectionForm`, `CorrectionStatusTimeline`, `ExceptionCards`, `FeatureToggleList`, `PricingTierEditor`, `PlanBadge`, `BillingSummaryCard`, `RenewalCountdown`, `InvoiceTable`, `PayNowButton`, `PaymentStatusBadge`, `ReceiptView`, `LoginTabs`, `SchoolCodeField`, `UsernameField` (with availability check), `LoginSupportMenu`, `TemporaryPasswordDialog`, `AdminList`, `AssessmentStructureEditor` (running total), `SheetFilters`, `SheetSearch`, `Broadsheet`, `StudentTermEntryForm`, `RatingScaleInput`, `CommentSuggestions`, `AttentionTable`, `AttentionFilters`, `ColorPicker` (with contrast warning), `StateSelect`, `UsageStats`, `PlatformSettingsTabs`, `PriceCheckPanel`, `TemplateStylePicker`, `BlockSettingsPanel`, `TemplateSettingsPanel`, `SchoolTypePicker`, `ReportCardLevelToggles`, `AssessmentModeSelect`, `LearningAreaEditor`, `SkillList`, `RatingScaleEditor`, `RatingGrid`, `RatingInput`, `SkillsReportCard`, `TeachesAllSubjectsToggle`, `AssistantPicker`, `HeadTitleSelect`.

---

## 10. Change protocol (mandatory)

Whenever you modify code, configuration, schema or a decision we already made, first write this block, wait for my `ok`, then make the change:

```
### CHANGE: <short title>
- Before: what existed and how it behaved
- Why it must change: the problem, bug, new requirement or risk
- When: why now (or the trigger that should make us change it later)
- What changes: files, functions, tables, migrations affected
- After: how it behaves once changed
- Proof: which tests cover it (new or updated) and the command to run them
```

Append every approved block to `CHANGES.md`. Database changes always use a new migration; never edit a migration that has already run.

---

## 11. Test-first protocol and project docs

### The loop for every unit of work
1. State the behaviour in one sentence ("A school admin cannot create another school admin").
2. Write the test(s), including at least one **denied** or **invalid** case for anything touching security, tenants, accounts or data.
3. Run them and show me the failing output (red).
4. Write the minimum code to pass.
5. Run the related tests and the full suite; show me green output.
6. Refactor if needed, run again, commit.

### Docs to keep updated
- `LOG.md`: date, what we did, test status, what is next, blockers, days remaining
- `DECISIONS.md`: every decision with reason and alternatives
- `CHANGES.md`: every change protocol block
- `docs/RESEARCH_TECH.md`: technical research and sources
- `docs/SERVICES.md`: services, purposes, where credentials live (never values), roadmap services
- `docs/ACCEPTANCE_TESTS.md`, `docs/API.md`, `docs/ERD` (diagram), `docs/SECURITY_AUDIT.md`
- `README.md`: setup, run, test, demo accounts (fictional), architecture, roadmap, limitations
- `RESEARCH.md`: my school interviews and findings (I write it, you help structure it)

---

## 12. Non-negotiable rules for `CLAUDE.md`

- There is no public registration. Super admin creates school admins; school admins create every other account, only inside their own school.
- Passwords are never emailed, logged or stored in plain text. Activation and reset tokens are hashed, single use and expiring.
- Every school-owned table has `school_id`; every query is tenant-scoped; row-level security is on.
- Authorization is enforced on the server. Hiding a button is never security.
- A disabled feature's endpoints reject requests.
- Teachers see only assigned sheets; form teachers see only their own form class; reviewers only their scope; guardians only linked wards; students only themselves.
- Login errors never reveal whether the school code, username or password was wrong. Students never get self-service password reset. The super admin resets school admins only. There is no impersonation.
- Additional school admins cannot add, remove or reset other admins.
- Only the super admin switches report card levels on or off; every request for a level that is off is rejected on the server.
- Class teacher assistants can enter but never submit.
- Skill ratings levels never compute totals, averages, grades or positions; each report keeps the rating scale and skills it was published with.
- Assessment structures add up to 100 and are locked per term once scores exist; each result stores the structure it used.
- Students needing attention is built only from published results, is staff-only and is scoped by role.
- Published results are immutable. Corrections create a new revision with a reason.
- Notices and emails go only to the intended audience in the same school. Emails never contain scores.
- No secrets in the frontend, in git, or in logs.
- No real child data in prompts, screenshots, seeds or tests.
- Every screen works from 320px upward and in both light and dark mode.
- Money is stored as integer kobo. Payment amounts come from server-side invoices, never the browser.
- An invoice is marked paid only after a signature-verified webhook and a server-side transaction check. Webhooks are idempotent.
- Only the super admin can change pricing; pricing is volume only, with cliff protection; issued invoices never change price.
- Payment gateway secret keys stay on the server; only test keys are used in the MVP.
- Every security-sensitive change ships with tests, including denied cases.

---

## 13. Phase 10: Security gate before production

Go through every item one at a time. For each: show how we implemented it, the files where it lives, and the command or test that proves it. Produce `docs/SECURITY_AUDIT.md` with a PASS/FAIL table. We do not deploy to production until every item passes or I explicitly accept a documented risk.

| # | Check | Verification |
|---|---|---|
| 1 | Admin routes are protected | Call every platform and school-admin endpoint as each lower role and anonymously; expect denial |
| 2 | Permissions enforced on the server | Role × endpoint × expected-status test matrix |
| 3 | Users can only access their own data | ID-swapping tests across users, wards and schools |
| 4 | Row-level security enabled where appropriate | Tests proving School A context cannot read or write School B rows, even with direct queries |
| 5 | No public registration; provisioning rules hold | No register route; additional admins cannot add admins; nobody creates cross-school users; super admin cannot reset teachers, parents or students; no impersonation endpoint exists |
| 5a | Login does not leak information | Same error and similar response time for a wrong school code, username or password; forgot password responds the same for every input and never sends for students |
| 5b | Scoped staff data | ID-swap tests on My class, broadsheets, student term entries and Students needing attention for every role |
| 5c | Level toggles and assistants | Requests for a disabled level rejected for every role; school admins cannot change levels; assistants cannot submit sheets or class sections |
| 6 | Email addresses verified | Activation required before login for email users; expired, reused and tampered tokens rejected |
| 7 | Passwords hashed securely | Stored values are modern password hashes; temporary passwords force change; never logged or emailed; resets end other sessions |
| 8 | Auth tokens kept out of insecure browser storage | Code search for browser storage use of tokens; inspect cookies and storage in DevTools |
| 9 | API keys and secrets kept on the server | No secrets in frontend env variables or the built bundle |
| 10 | Environment variables checked | App refuses to start with missing or invalid config; separate values per environment |
| 11 | `.env` files and secrets removed from GitHub | Only `.env.example` is tracked; push protection on |
| 12 | Git history checked for leaked secrets | Full-history secret scan; rotate anything found, then clean history |
| 13 | Sensitive data kept out of logs | Tests that captured logs redact passwords, tokens, personal data and scores |
| 14 | Parameterized database queries | Static analysis plus code search for string-built SQL |
| 15 | Form inputs validated and sanitized | Client validation for UX, server validation as authority; tests with invalid, oversized and unexpected fields, including CSV imports |
| 16 | Cross-site scripting prevented | No unsafe HTML rendering; template autoescaping on for PDFs and emails; content security policy; test that script text in remarks and notices renders as plain text |
| 17 | File uploads validated (logos, signatures, stamps, attachments) | Type allowlist by content, size limits, safe filenames, private storage, authorised download only; tests with disguised and oversized files |
| 18 | Webhook signatures verified | Payment webhook verifies the gateway signature over the raw body and confirms the transaction server-side; tests for valid, invalid, missing and replayed signatures and duplicate events; same rule for any email provider webhooks |
| 19 | Sensitive requests rate limited | Login, password flows, activation, verification page, imports, uploads, notice posting; tests that exceed limits |
| 20 | Security headers added | CSP, HSTS, content-type options, referrer policy, permissions policy, frame-ancestors; scan deployed URLs with an external header checker |
| 21 | Database and storage permissions locked down | Least-privilege app role, unused provider APIs disabled, private buckets, provider security advisor clean |
| 22 | API endpoints secured | Automated test that fails if any non-public route lacks authentication; CORS locked; CSRF protection if cookies are used |
| 23 | Debug mode off in production | No stack traces, interactive API docs disabled or protected in production |
| 24 | Vulnerable dependencies updated | Dependency audits for both frontend and backend clean or documented |
| 25 | Unused packages and endpoints removed | Unused-dependency check and route review |
| 26 | Exposed files and secrets scanned | Request `/.env`, `/.git/config` and backup files on deployed URLs; run an automated baseline scan |
| 27a | Payment integrity | Tests that the browser cannot change amounts, currency or invoice; amount mismatch from the gateway is rejected; redirect alone never marks paid; only super admin edits pricing; schools only see their own billing |
| 27 | Audit trail and immutability hold | Tests that try to change published snapshots and audit events as the app role |
| 28 | Full security audit before deploy | Re-run everything, every row PASS, signed off by me |

Also complete the privacy-by-design checklist from the MVP document, and state clearly that this is not a legal compliance certification.

---

## 14. Phase 11: Production deploy and demo

1. Create production environment variables with fresh secrets, separate from staging. The payment gateway stays in **test mode** for the MVP demo; set the webhook URL (HTTPS) in the gateway's test dashboard.
2. Run migrations with the migration-only credentials, then seed the fictional demo schools.
3. Deploy, run the full end-to-end demo flow against production at phone, tablet and desktop sizes in both themes, then re-run the header and exposed-file scans.
4. Demo-day warm-up checklist (wake sleeping services, check database is active, check email quota, send a test webhook from the gateway dashboard, have the gateway's test card details ready).
5. Demo script following the 38 demo steps in `SPEC.md` (aim for about ten minutes; mark which steps to skip if time is short).
6. Finalise `README.md`, `LOG.md`, `RESEARCH.md` and known limitations.
7. Post-MVP priorities linked to the proposal's phases (going live with payments, school fee collection from parents, attendance, LMS, CBT, SMS/WhatsApp, live classes, hostel, transport, payroll).

---

## 15. Start now

Do these in order, stopping after each:

1. Ask which OS I use and confirm you can read `SPEC.md`, the MVP document, the proposal and `design/README.md`.
2. Summarise the MVP scope back to me in 15 to 20 bullets, including school types and report card toggles, nursery and primary report cards with Scores or Skill ratings per level, class teachers and assistants, login and password reset rules, additional admins, assessment structures, form teacher tools, Students needing attention, super admin platform administration, templates, notice board, email, dashboard, responsive, theme and subscription billing, and the "build after the core" list, so we agree on what is in and out.
3. Begin **Phase 1: Technical research**.
