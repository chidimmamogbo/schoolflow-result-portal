# SchoolFlow Result Portal: UI/UX Design Brief

> **What this is:** everything needed to design SchoolFlow Result Portal's wireframes, visual design and clickable prototype (planning name ResultChain).
>
> **Status (7 October 2026):** the first round of design is approved and exported as `schoolflow-ui-handoff` (design system, logos, 21 screens, `NAVIGATION_AND_SETTINGS.md`). This version of the brief adds the v0.4 and v0.5 features (v0.5: nursery and primary report cards, school types, skill ratings, class teachers and assistants). Items marked **NEW** or **CHANGED** need design work; everything else is already designed. Use `DESIGN_UPDATE_PROMPT.md` to run the update.
>
> **Source of truth:** `SPEC.md` v0.5 (features F01 to F26). If this brief and the spec disagree, the spec wins. Existing labels in `NAVIGATION_AND_SETTINGS.md` stay as they are unless this brief changes them.

---

## 1. What to attach before you start

| Item | Required? | Notes |
|---|---|---|
| `DESIGN_BRIEF.md` (this file) | Yes | |
| `SPEC.md` (v0.5) | Yes | Features, roles, permissions, workflows, demo script |
| The approved design project or `schoolflow-ui-handoff` | Yes, for updates | Keep the existing design system, logo and screens; extend them |
| Two real report cards from Nigerian schools, plus one nursery and one primary report card | Strongly recommended | Redact every name, photo and score, or retype them with fictional data. The report-card designer must be able to reproduce these layouts |
| SchoolFlow logo | Done | In `brand/logos/` of the handoff |
| Screenshots of 2 or 3 apps whose feel you like | Optional | For mood only, never to copy |
| Notes from teacher/principal interviews | Optional | Real pain points make better screens |

Never upload real student names, photos, results or phone numbers.

---

## 2. Product in one paragraph

SchoolFlow Result Portal is a results-first, multi-school SaaS for Nigerian nursery, primary and secondary schools. A school can be nursery and primary only, secondary only, or all three, and each school chooses whether each level is assessed with scores or skill ratings. Teachers enter scores once, the system catches errors, reviewers and principals approve, each school publishes its own branded report card, and parents get a verifiable result with a full correction history. A super admin runs the platform, creates schools and their principals, supports school admins when they lose their login, sets per-student pricing, and bills each school every term. After publication, principals and teachers see which students scored below the pass mark.

---

## 3. Who we are designing for

| Role | Typical person | Main device | What they care about | Their top 3 tasks |
|---|---|---|---|---|
| Super admin | Platform owner | Laptop | Schools running smoothly, getting paid | Create schools and principals, help school admins with logins, set pricing and platform settings, track payments |
| School admin/principal | Principal, 40 to 60 years old, busy | Laptop and phone | Release results on time with no scandals | Register people, approve and publish results, see who needs attention, pay subscription |
| Additional school admin (NEW) | Vice principal or school administrator | Laptop | Taking setup and results work off the principal | Same as principal, except managing other admins |
| Reviewer/HOD | Senior teacher | Laptop or phone | Catching mistakes before the principal does | Review sheets, return with comments |
| Teacher | Subject teacher, often also form teacher of one class, entering scores late at night | Low-cost Android phone, sometimes a shared computer | Entering scores fast without errors; getting their class's report cards right | Find the right sheet and student, enter or import scores, submit; as form teacher, write comments, ratings and attendance |
| Class teacher assistant (NEW) | Teacher or aide helping a nursery or primary class teacher | Phone | Helping without taking over | Enter scores, ratings and comments for the class; cannot submit |
| Parent/guardian | Wide range of digital comfort, sometimes with 2 to 4 children at the school, including nursery pupils who have no login of their own | Low-cost Android phone on mobile data | Seeing the result, trusting it, downloading it | View result, download PDF, verify, report a problem |
| Student | 9 to 18 years old | Phone | Seeing their own result | View and download their report |

**Context that must shape the design**
- Many users are on low-cost phones with slow or expensive mobile data. Key parent and teacher screens must be light and fast.
- Many teachers are used to Excel and paper broadsheets; the score grid should feel familiar.
- Results week is high pressure. The principal's screens should answer "what is blocking release?" at a glance.
- Trust is the product. Every published result should look official and verifiable.
- Currency is Naira (₦). Dates display as `5 Jan 2027`. Times in West Africa Time.
- Language: clear, plain English. Avoid jargon such as "tenant", "revision hash" or "RBAC" in the interface.

---

## 4. Design principles

1. **Trust you can see.** Status, history and verification are always visible: who changed what, which version, whether it is valid.
2. **Errors before embarrassment.** Problems are caught and shown at the point of entry, in plain words, with the fix.
3. **One clear next action.** Every screen makes the main action obvious (Submit, Approve, Publish, Pay now).
4. **Phone first for teachers and parents, desk first for admins.** Design both, but start from the device each role actually uses.
5. **Calm, official, modern.** It should feel like a reliable institution, not a flashy startup.
6. **Accessible by default.** Readable sizes, strong contrast, never colour alone.

---

## 5. Visual direction

**Personality:** trustworthy, calm, official, modern, warm. Think "a well-run school office with good software".

**Starting colour tokens** (proposals; the design tool may refine them, but every pair must meet WCAG AA contrast in both themes):

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | #F7F8FA | #0B1220 | Page background |
| `surface` | #FFFFFF | #111A2C | Cards, panels, sidebar |
| `surface-2` | #F1F3F7 | #17223A | Table headers, hover, inputs |
| `border` | #E3E7EE | #24314D | Dividers, outlines |
| `text` | #0F172A | #E6EAF2 | Main text |
| `text-muted` | #5B6475 | #9AA4B8 | Secondary text |
| `primary` | #1F4FD8 | #6E8BFF | Main actions, links, active nav |
| `success` / verified | #0E9F6E | #34D399 | Approved, published, valid, paid |
| `warning` | #B7791F | #F6AD55 | Returned, due, superseded |
| `danger` | #C81E1E | #F87171 | Errors, overdue, revoked |
| `info` | #2563EB | #60A5FA | Submitted, informational |

**School branding:** each school has a logo and a primary colour. Use the school colour in limited places (school name area in the header, report card accents, parent portal header). It must stay readable in both themes; if a school colour fails contrast, fall back to the platform primary for text and buttons.

**Typography:** a clean sans-serif with good Naira sign (₦) support and tabular numbers for score tables (Inter or similar). Suggested scale: 12, 14, 16 (body), 18, 20, 24, 30, 36. Body text is never below 14px on phones; score grid numbers are at least 16px.

**Iconography:** one consistent outline icon set. Every icon in the collapsed sidebar has a tooltip.

**Shape and depth:** 8px base spacing; 8 to 12px corner radius on cards and inputs; subtle shadows in light mode, borders instead of shadows in dark mode.

**Motion:** short and functional (sidebar collapse, drawer slide, toasts). Respect "reduce motion".

---

## 6. Status system (use everywhere, always icon + text, never colour alone)

| Object | Status | Colour | Icon idea |
|---|---|---|---|
| Result sheet | Draft | neutral grey | pencil |
| | Submitted | info blue | paper plane |
| | Returned for correction | warning amber | arrow-back |
| | Resubmitted | info blue (outlined) | refresh |
| | Reviewed | teal/info | eye-check |
| | Approved | success green | check |
| | Published | success green (filled) | badge-check |
| Report validity | Valid | success | shield-check |
| | Superseded | warning | layers |
| | Revoked | danger | shield-x |
| Correction request | Open, Investigating, Needs more information, Resolved, Rejected | info, info, warning, success, neutral | |
| Subscription | Free pilot, Active, Due, Overdue, Suspended | info, success, warning, danger, neutral-danger | |
| Invoice | Unpaid, Paid, Void | warning, success, neutral | |
| Email | Queued, Sent, Failed | neutral, success, danger | |
| Form teacher class sections (NEW) | Open, Submitted, Returned | neutral, info, warning | pencil, paper plane, arrow back |
| School (NEW) | Active, Suspended | success, danger | check, pause |
| Assessment structure (NEW) | Editable, Locked for this term | neutral, info | pencil, lock |
| Account (NEW) | Invited, Active, Must change password, Deactivated | info, success, warning, neutral | mail, check, key, user-x |
| Invoice amount (NEW) | Capped by cliff protection | info | shield |
| Students needing attention (NEW) | Below pass mark, Average below pass mark, Needs attention (skills) | danger, danger (outlined), danger | alert triangle |
| Report card level (NEW) | On, Off | success, neutral | check, minus |
| Skill rating (NEW) | Excellent, Very good, Good, Fair, Needs improvement | success, success, info, warning, danger | always shown as word or code, never colour alone |

---

## 7. Layout shell (every signed-in role)

**Desktop and laptop (1024px and up)**
- Left sidebar: expanded about 256px wide with icon + label; collapsed about 72px with icons only and tooltips on hover/focus.
- Expand/collapse toggle icon at the top or bottom of the sidebar (chevron or panel icon). The choice is remembered.
- Sidebar top: SchoolFlow logo (or school logo for school users) and the school name.
- Sidebar groups with small headings (for example "Results", "People", "School", "Billing").
- Header bar: page title and breadcrumb on the left; on the right a search (optional), notice bell with unread count, theme toggle (light / dark / system), and profile menu (name, role, change password, log out).
- Content area: max readable width for forms; full width for tables and dashboards.

**Tablet (768 to 1023px)**
- Sidebar starts collapsed (icons only) and can be expanded over the content.

**Phone (320 to 767px)**
- No permanent sidebar. A menu icon in the header opens a slide-out drawer with the full navigation.
- Optional bottom navigation for parents and teachers with 3 or 4 key items (Home, Results/Sheets, Notices, Profile).
- Wide tables scroll inside their own container or turn into cards. The page itself never scrolls sideways.
- Primary actions are reachable with a thumb (sticky bottom action bar on long forms and the score grid).

**Breakpoints to design and check:** 320 or 360 (small phone), 390 to 414 (large phone), 768 (tablet), 1024 (small laptop), 1280 to 1440 (desktop).

**Themes:** every screen in light and dark. No flash of the wrong theme on load. Report cards, PDFs and print previews always use the light print design.

---

## 8. Navigation by role

**Super admin (CHANGED):** Dashboard · Schools · Pricing · BILLING (Invoices, Payments) · PLATFORM (Announcements *after the core*, Audit log, Email log, Settings)

**School admin/principal (CHANGED):** Dashboard · RESULTS (Approvals, Publish results, Students needing attention, Report templates, Audit trail) · PEOPLE (Students, Teachers, Reviewers, Parents, School admins *principal only*) · SCHOOL (School setup, Notices, Corrections, Emails, Billing, School settings). School setup tabs: Sessions and terms, Classes, Subjects, Departments, Grading, Assessment, Learning areas and skills (only when a level uses Skill ratings), Rating traits. Only levels switched on by the super admin appear anywhere.

**Additional school admin (NEW):** same as principal without the School admins item.

**Reviewer/HOD (CHANGED):** Dashboard · Review queue · Students needing attention · Notices · Profile

**Teacher (CHANGED):** phone bottom bar Home · Sheets · My class (form teachers, class teachers and assistants) · Notices; Students needing attention and Profile in the slide-out menu

**Parent/guardian:** Home (ward switcher) · Results · Corrections · Notices · Profile

**Student:** Home · My results · Notices · Profile

Menu items only show for features enabled for the school and permitted for the role.

---

## 9. Screen inventory

**Priority:** P1 = needed for the clickable demo prototype. P2 = design now, lighter detail. P3 = simple wireframe is enough.

Every screen needs: default, empty, loading, error, and (where relevant) no-permission states; phone and desktop versions; light and dark.

### 9.1 Public

| Screen | Priority | Purpose and key content |
|---|---|---|
| Landing page | P2 | What SchoolFlow Result Portal is, the trust story (enter once, approve, verify), pricing summary, "Log in" button. No sign-up button anywhere |
| Login (CHANGED) | P1 | Tabs **Staff and parents** (Email or username, Password, "Forgot password?") and **Student** (School code, Username or admission number, Password, and the line "Forgot your password? Ask your school admin for a new one." instead of a forgot link). Generic error text |
| School login link (NEW) | P1 | `/login/GMC`: Student tab with school code filled in, school logo and name at the top |
| School paused (NEW) | P2 | "Your school's access is paused. Contact your school admin." |
| Activate account | P1 | From email link: welcome with school name, set password with strength hints, confirm. Expired-link state |
| Change password (forced) | P1 | Shown after temporary-password login; cannot be skipped |
| Forgot / reset password | P2 | Same confirmation message whether or not the account exists. Note for people without email: "No email on your account? Ask your school admin to reset your password." |
| Verify a report (enter code) | P1 | Field for report ID or code, plus "scan the QR on the report" hint |
| Verification result | P1 | Large status (VALID / SUPERSEDED / REVOKED), school name and logo, masked student name (for example "Chuk\*\*\* O."), session, term, revision, publication date. Superseded shows "A newer version exists". Never shows scores |
| Privacy notice | P3 | Plain-language page |
| 404 / no access | P3 | Friendly, with a way back |

### 9.2 Super admin

| Screen | Priority | Purpose and key content |
|---|---|---|
| Platform dashboard | P2 | Number of schools, active/overdue subscriptions, term revenue (invoiced, paid, outstanding), recent payments |
| Schools list (CHANGED) | P1 | Table: school, code, state, principal, students, plan, subscription status, school status (Active, Suspended); search and filters |
| Create school (CHANGED) | P1 | Full-page form with School type and report card toggles, see Section 10.6 |
| School detail (CHANGED) | P1 | Tabs: Overview (details, usage, Edit, Change school code, Suspend school), Features (adds **Report cards by level**: School type select and the Nursery, Primary, Secondary toggles, with the turn-off confirmation), School admins (replaces Principal account, see Section 10.11), Subscription, Invoices, Activity |
| Reset login dialog (NEW) | P1 | From School admins tab: choose "Send reset link" (optionally change email first) or "Issue temporary password" (shown once, printable slip); "Also sign out of all devices" checked by default |
| Pricing table editor (CHANGED) | P1 | Editable rows: plan name, minimum students, maximum students (blank for "and above"), price per student per term (₦). No pricing model choice (volume only). Cliff protection switch with explanation. **Price check** panel listing cliff ranges. "Try it" calculator showing plan, amount and "Capped by cliff protection" when it applies. Inline errors for overlaps or gaps. "Save as new version". Version history |
| Payments (NEW) | P2 | All payments across schools: school, invoice, amount, method (gateway or manual), reference, date |
| Audit log (NEW) | P2 | Platform-wide timeline with filters: school, person, action, date |
| Email log (NEW) | P3 | Emails by school and type with Queued, Sent, Failed (no message bodies) |
| Platform settings (NEW) | P1 | Tabs General, Email, School defaults, Billing, Security, see Section 10.12 |
| Announcements (NEW, after the core) | P3 | Composer to all school admins (board and email) |
| Billing overview | P1 | Term selector; totals; table of schools with plan, billable students, invoice amount, status; "Generate invoices" for one or all schools |
| Invoice detail | P2 | Snapshot details; mark manual payment (reference, note); void |

### 9.3 School admin/principal

| Screen | Priority | Purpose and key content |
|---|---|---|
| Dashboard (results week) (CHANGED) | P1 | "What is blocking release?": sheets awaiting submission / review / approval (by class), form teacher sections still open, missing and invalid scores, open corrections, pass rate and averages, unusual score changes. **Students needing attention card** after publication ("37 subject results below 40% in First Term", View list). Billing card and latest notices |
| School settings | P2 | Logo upload, school colour with live preview in both themes, address, contacts |
| Sessions and terms | P2 | List, create, set active term (with start and end dates) |
| Classes and arms | P2 | Classes with arms (JSS 1A, 1B...) |
| Subjects and departments | P2 | Subjects per class; departments for HOD scoping |
| Grading setup (CHANGED) | P2 | Grading bands A1 to F9 editable; remark bands; **pass mark** (default 40) |
| Assessment structure (NEW) | P1 | See Section 10.7, including the Scores or Skill ratings choice per level |
| Learning areas and skills (NEW) | P1 | See Section 10.13 |
| Rating traits (NEW) | P3 | Affective and psychomotor trait lists and the 1 to 5 scale key |
| School admins (NEW, principal only) | P2 | List of the principal and additional admins; Add school admin (full name, username, email, login method); limit message "You can add up to 2 school admins." |
| Students list | P1 | Search, filter by class, status; actions: add, import, view |
| Add student (CHANGED) | P1 | Name, admission number, **username** (suggested, availability check), gender, date of birth, class/arm, house (optional), subjects (pre-filled from class, adjustable), optional guardian link, login method (activation email or temporary password) |
| Import students (CSV) | P1 | Step 1 download template, step 2 upload, step 3 preview table with row errors highlighted and an error count, step 4 commit (disabled while errors exist), result summary |
| Student detail | P2 | Tabs: Profile, Enrolment history, Subjects, Guardians, Results, Login (username, status, "Issue new temporary password", deactivate) |
| Credential slip | P1 | Printable slip with school logo, name, login ID, one-time temporary password, login URL, "you will be asked to change this". Shown once, with a clear warning |
| Teachers list, add teacher, teacher detail (CHANGED) | P1 | Username field; assignment editor: subject + class/arm pairs as chips; "Form teacher of" select (one arm); **Teaches all subjects** shortcut; Login tab with login support actions. See Section 10.15 |
| Class page: class teacher and assistants (NEW) | P1 | See Section 10.15 |
| Reviewers list, add reviewer | P2 | Scope picker: department or subjects/classes |
| Parents list, add parent, parent detail | P1 | Ward linker: search students and link one or more; relationship; login method |
| Approvals | P1 | Sheets by class and subject with status; filter; open sheet in read-only view with audit; Approve (confirm dialog) |
| Publish results (CHANGED) | P1 | Choose class + term; checklist showing every sheet approved **and form teacher sections submitted**; **Principal's comments** step (per student, with suggestions and "Apply to all with average above..." helper); preview a report card; Publish with clear consequences |
| Students needing attention (NEW) | P1 | See Section 10.9 |
| Report templates list and editor (CHANGED) | P1 | Style picker (Modern, Classic, Compact; Bold Banner, Ink Saver, Cumulative marked "after the core"); block list with show/hide and reorder; expanded block settings and a Template settings panel (Section 10.2); live preview (light only). Version history |
| Audit trail | P1 | Timeline filtered by student, subject, class or person: "12 Oct 2026, 10:14. Teacher A changed Mathematics CA2 for Student X from 12 to 15. Reason: corrected transcription error." |
| Corrections list and detail | P1 | Ticket status, requester, linked report version, conversation, actions: investigate, request info, resolve, reject, reopen result |
| Notices list and composer | P1 | Composer: title, message, audience (everyone / roles / classes), pin toggle, preview |
| Email outbox | P3 | Queued / sent / failed with retry |
| Billing | P1 | Plan card (plan name, billable students, price per student), amount due, due date, next renewal date, status, projected next-term cost; Pay now; invoice history (Paid with date and reference / Unpaid); receipt view |
| Payment confirming | P1 | "Confirming your payment" while the server verifies; then success (receipt) or problem state |

### 9.4 Reviewer/HOD

| Screen | Priority | Purpose |
|---|---|---|
| Review queue | P1 | Submitted sheets in scope, oldest first |
| Students needing attention (NEW) | P2 | Same as Section 10.9, limited to the reviewer's scope |
| Review sheet | P1 | Read-only grid with flags and change history; actions: Return with comment (required), Mark reviewed |

### 9.5 Teacher

| Screen | Priority | Purpose |
|---|---|---|
| Dashboard / my sheets (CHANGED) | P1 | Sheets **grouped by class**, with filter chips (class, subject, status) and a search; cards show status and progress ("28 of 32 scores entered"), return comments highlighted; Students needing attention card after publication |
| Score entry grid (CHANGED) | P1 | See Section 10.1 |
| Rating sheet (NEW) | P1 | See Section 10.14 |
| My class: broadsheet (NEW) | P1 | See Section 10.8 |
| My class: student entry (NEW) | P1 | See Section 10.8 |
| My class: report preview (NEW) | P2 | Report card with a "Preview, not published" band |
| Students needing attention (NEW) | P1 | Section 10.9, scoped to the teacher |
| Import scores | P2 | Same 4-step pattern as student import |

### 9.6 Parent/guardian

| Screen | Priority | Purpose |
|---|---|---|
| Home | P1 | Ward switcher (photo initials, name, class); latest result card with status; latest notices |
| Child results | P1 | Terms list with status |
| Report view (low bandwidth) | P1 | Simple, fast summary: subjects, totals, grades, average, position, comments; Download PDF; Verify; "Report a problem" |
| Skills report view (NEW) | P1 | Nursery or skill-rated pupil: learning areas with each skill's rating word, area comments, class teacher's and head teacher's comments; Download PDF; Verify; no scores |
| Correction request form and list | P1 | Subject/section, issue type, explanation, optional attachment; status timeline |

### 9.7 Student

| Screen | Priority | Purpose |
|---|---|---|
| Home and my results | P2 | Same pattern as parent, self only |

### 9.8 Shared

| Screen | Priority | Purpose |
|---|---|---|
| Notice board | P1 | Pinned first, unread marked, filter; notice detail |
| Notice bell dropdown | P1 | Latest 5, "View all" |
| Profile | P3 | Name, change password, theme preference |

---

## 10. Key components in detail

### 10.1 Score entry grid (most important teacher screen)
- Header: subject, class/arm, term, status badge, components and max scores taken from the level's assessment structure (for example JSS: CA1 /20, CA2 /20, Exam /60; SS: CA1 /10, CA2 /10, CA3 /10, Project /10, Exam /60).
- **CHANGED:** the number of component columns varies from 1 to 8. Design both a 3-column and a 5-column sheet. On phones each student is a card with one input per component, so extra components add rows, not width.
- **NEW:** a search field ("Search by name or admission number") that jumps to and highlights the student, and filter chips All, Missing, Errors with counts.
- Rows: students (admission number, name); columns: each component, Total, Grade (auto), Remark (auto).
- Desktop: spreadsheet feel; arrow keys and Enter move between cells; tabular numbers.
- Phone: one student per card or a sticky name column with horizontal scroll inside the grid; large number inputs.
- Inline validation: empty cell (amber outline, "Missing"), out of range (red, "Max is 20"), duplicate import row.
- Summary bar: "3 missing, 1 invalid". Submit is disabled until zero, with a "Show problems" link that jumps to each.
- Editing an already-saved score opens a small reason field.
- Sticky bottom bar on phone: Save draft, Submit.
- Returned sheets show the reviewer's comment pinned on the affected row.

### 10.2 Report card and template editor (print always light) (CHANGED)
Blocks: school header (logo, name, address, motto), student details, session/term, subject table (components, total, grade, remark, subject position, class average), summary (total, average, overall position, number in class), affective and psychomotor domains, attendance, form teacher and principal comments, signature lines, footer with report ID, revision, publication date and QR code.

**Report card types (NEW):** each enabled level has its own template. Levels on Scores use this Score report card; levels on Skill ratings use the Skills report card (Section 10.14). Template settings add **Head's title** (Head teacher, Principal, Head of school, Proprietor, Director, Custom) used on the comment and signature labels; defaults Head teacher for Nursery and Primary, Principal for Secondary. The template list groups templates by level.

**Styles:** Modern and Classic (designed), **Compact** (NEW: tighter rows and smaller type so 15 or more subjects fit on one A4 page), **Early Years** (NEW: larger type, rounded shapes and softer school-colour tints for Nursery and lower Primary; default for Skills report cards). After the core: Bold Banner (school-colour header band), Ink Saver (black and white, no fills), Cumulative (first, second, third term columns, annual average, promotion result).

**Block settings (NEW and CHANGED), all switches unless noted:**
- School header: Logo, Logo position (Left, Centre, Right), School motto, Address, Phone and email, Report title (text, default "Student Report Card"), Session and term line.
- Student details: Photo, Admission number, Gender, Age, Date of birth, Class and arm, House, Form teacher's name.
- Subject table: one switch per assessment column, CA and exam breakdown, Total, Grade, Remark, Position in each subject, Class average per subject, Highest in class, Lowest in class, Subject teacher's initials, Highlight scores below pass mark, Row shading.
- Summary: Total score, Total average, Overall class position (optional), Number in class, Class average, Number of subjects, Promotion result.
- Affective and psychomotor: Affective, Psychomotor, Rating key, Layout (Side by side, Stacked).
- Attendance: Times school opened, Times present, Times absent.
- Comments: Form teacher's comment, Principal's comment, Show names.
- Signatures: Form teacher signature line, Principal signature image (upload), School stamp image (upload), Date line.
- Footer, QR and report ID: QR position (Left, Right), Next term begins, School contact line, Custom footer note (text). Report ID, revision, publication date and QR code show as locked "Always shown" rows with a lock icon.

**Template settings (NEW):** Paper size (A4, Letter), Font (Inter, Merriweather, Nunito), Text size (Small, Medium, Large), Accent colour (school colour or custom, using the same colour picker as Create school), Borders (None, Lines, Boxed), Logo watermark, Grading key (Off, Below summary, In footer), Margins (Narrow, Normal).

With many settings, group the right-hand panel into collapsible sections and keep the live preview visible.

### 10.3 Pricing table editor (super admin) (CHANGED)
Editable table plus validation messages ("Standard must start at 500 because Basic ends at 499"), version history, "This will not change invoices already issued" note.
- **Remove** the Volume or Graduated choice. Add one line under the table: "Each school pays the price of the plan its student count falls into, for every student."
- **Cliff protection** switch (on): "A school never pays more than the smallest bill on a higher plan."
- **Price check** panel (warning style) listing cliff ranges, for the defaults: "Schools with 251 to 499 students would pay more than a school with 500 students." and "Schools with 601 to 1,000 students would pay more than a school with 1,001 students." With protection on, add "Cliff protection caps these bills."
- **Try it** calculator: enter students, see plan, price per student, amount and, when it applies, "Capped by cliff protection: ₦300,300 instead of ₦321,000".

### 10.4 Billing card (school admin)
Compact card on the dashboard and a full billing page: plan badge, "580 students × ₦500 = ₦290,000" (and a "Capped by cliff protection" line when it applies), due date, renewal date with a countdown ("Due in 12 days"), status, Pay now; overdue state in danger colour with grace period info.

### 10.5 Other components
Ward switcher; assignment chips; ward linker search; CSV import stepper; status badge; reason dialog; confirm dialog for irreversible actions (publish, revoke, void); audit timeline item; notice card; notice composer audience picker; credential slip; verification status panel; exception cards for the dashboard; empty states with a helpful next step; toast messages; skeleton loaders.

### 10.6 Create school form (super admin) (CHANGED)
Full page with numbered sections and a sticky summary or action bar:
1. **School details:** School name, School email, Phone number, Address, City, State (dropdown of the 36 states and FCT when Country is Nigeria; text field otherwise), Country (default Nigeria), School code (suggested from the initials, editable, uppercase, live check "GMC is available" or "GMC is taken"), **School type** (select: Nursery and Primary; Secondary only; Nursery, Primary and Secondary) with **Report cards** toggles underneath (Nursery report cards, Primary report cards, Secondary report cards) that the type sets automatically; changing a toggle by hand shows the type as "Custom"; at least one must stay on, School colour (**full colour picker** with hue/saturation area, hex field and recent colours, not a fixed swatch list; live preview of the sidebar header and a report card accent in light and dark; warning "Text on this colour may be hard to read. We'll use the SchoolFlow blue for buttons and text."), Logo (optional upload with preview).
2. **Features:** the six switches with descriptions (unchanged).
3. **Billing:** "Billing" switch on, or off for "Free pilot".
4. **Principal account:** Full name, Username (suggested, live availability check), Email.
- Button: "Create school and send invite". Success screen: "Greenfield Model College is ready. We've emailed Mrs. Ngozi Okeke an activation link and sent a set-up confirmation to info@greenfield.edu.ng." with the school code and school login link (copy button).
- On phones the sections stack; the action bar stays at the bottom.

### 10.7 Assessment structure editor (school admin) (NEW)
- Level tabs, showing only levels switched on for the school (Nursery, Primary, Junior Secondary, Senior Secondary).
- **Assessment mode** at the top of each tab: segmented control **Scores** or **Skill ratings**, with one line explaining each. Choosing Skill ratings replaces the component table with a link to Learning areas and skills. Locked per term like the structure.
- Rows: Name (for example "Continuous assessment 1"), Short label (CA1), Max score, reorder handles, remove. "Add component" up to 8.
- Running total chip: "Total 100" (success) or "Total 95. Add 5 more to reach 100." (warning); Save disabled until 100.
- Locked state: banner "Scores have been entered for First Term, so this structure is locked. Changes you save will apply from Second Term." with a lock badge.
- Preview strip showing how the score sheet columns will look.

### 10.8 My class (form teacher) (NEW)
Title uses "Class teacher" for Nursery and Primary and "Form teacher" for Secondary. Assistants see the same screens without Submit buttons. For Skill ratings classes, the broadsheet shows each learning area's rating sheet status instead of subject scores.
- **Broadsheet:** class header (JSS 1A, form teacher, number of students); subject status chips across the top (Draft, Submitted, Approved and so on); table of students against subjects with totals, sticky first column, horizontal scroll inside the table; missing cells marked; on phones, a list of students that opens a per-student subject list.
- **Class sections card:** progress ("Comments 28 of 32, Ratings 30 of 32, Attendance 32 of 32"), "Times school opened" field for the class, and "Submit class sections" (disabled until complete), with Returned state showing the admin's comment.
- **Student entry:** student name and photo initials, previous and next student buttons, class teacher's comment textarea with 2 or 3 suggestion chips from the remark bands and a character count (300), affective and psychomotor traits each rated 1 to 5 (segmented buttons with the rating key), times present (with "of 60" and calculated absent), Save and next.
- **Preview:** the report card with a "Preview, not published" band.

### 10.9 Students needing attention (NEW)
- Title "Students needing attention", subtitle "First Term 2026/2027 · Pass mark 40%".
- Tabs: **By subject** (rows: student, admission number, class, subject, score in danger colour, grade, subject teacher) and **By student** (rows: student, class, failed subjects count, overall average, "Average below pass mark" badge when it applies; expanding a row lists the failed subjects).
- Filters: session, term, class, arm, subject, teacher (school admins only). Export CSV and Print buttons.
- For levels on Skill ratings, a third tab **By learning area** lists pupil, class, learning area, skill and rating (at or below Needs improvement); By student shows the number of skills needing attention.
- Scope note for teachers: "Showing Mathematics in JSS 1A and JSS 1B, and all subjects for your class JSS 1A."
- Empty state: "No results below the pass mark for this selection." Before publication: "This list appears when results are published."
- Phones: each row becomes a card.

### 10.10 Login (CHANGED)
- Tabs **Staff and parents** and **Student** (replacing Email and Student).
- Staff and parents: Email or username, Password, Log in, "Forgot password?".
- Student: School code (uppercase, short field), Username or admission number, Password, Log in, and the text "Forgot your password? Ask your school admin for a new one." No forgot link on this tab.
- School login link variant: school logo and name above the card, Student tab selected, school code filled in.
- Error for every failure: "That login didn't work. Check your details and try again."

### 10.11 School admins tab and login support (super admin) (NEW)
- List: name, username, email, role badge (Principal, School admin), status (Active, Invited, Deactivated), last login.
- Row actions menu: Resend activation, Change email, Send reset link, Issue temporary password, Sign out of all devices, Make principal, Deactivate or Reactivate.
- Temporary password dialog: shown once with Copy and Print slip, warning "This password is shown only once."
- The same login support menu (without Make principal) is used by school admins on student, teacher, reviewer and parent detail pages.

### 10.12 Platform settings (super admin) (NEW)
Tabs: **General** (Platform name, Logo, Support email, Support phone), **Email** (Sender name, Reply-to address), **School defaults** (Grading bands, Assessment structure, Pass mark, Remark bands, Rating traits, Report template style), **Billing** (Grace period in days 14, Invoice due in days 14, Gateway fees paid by: Platform or School, Cliff protection on), **Security** (Additional school admins per school 2, Session length, Two-factor login for super admins *after the core*). Each tab has its own Save button and shows "Last changed by ... on ...".

### 10.13 Learning areas and skills (school admin) (NEW)
- Level tabs for levels on Skill ratings.
- Left: learning areas list (Number work, Letter work, Phonics, Rhymes and songs, Creative arts, Social habits, Health habits, Physical development), add, rename, reorder, assign to classes.
- Right: skills in the selected area, each with a short name and an optional description shown on the report card; add, edit, reorder, remove.
- **Rating scale** card: points with word, code and description (Excellent E, Very good VG, Good G, Fair F, Needs improvement NI), add or remove points, and "Flag in Students needing attention at or below" select (default Needs improvement).
- Note when reports exist: "Published reports keep the scale and skills they were published with."

### 10.14 Rating sheet and Skills report card (NEW)
- **Rating sheet (teacher, phone first):** header with learning area, class, term and status; filter chips All, Not rated; search by name. On phones, one card per pupil with each skill as a row of large rating buttons showing codes (E, VG, G, F, NI) with the word below on selection, and an optional area comment. On desktop, a grid of pupils against skills with a rating select per cell. "3 skills not rated" summary; Submit disabled until zero; Save draft. Assistants see Save draft only.
- **Skills report card (print, always light, Early Years style by default):** school header; pupil details (name, class, age, optional photo); skills table grouped by learning area with each skill and its rating (word, code, or both); area comments; rating key; attendance; class teacher's comment and head teacher's comment; signatures; footer with report ID, revision, date and QR. No totals, grades or positions. Also show it in Modern style.

### 10.15 Class teacher and assistants (school admin) (NEW)
- On a class page (for example Primary 4A): **Class teacher** select and a **Teaches all subjects** switch ("Gives this teacher every subject in Primary 4A, including subjects added later"). With it on, the subject list shows the class teacher on every row.
- **Class teacher assistants:** add up to 2 teachers, with the note "Assistants can enter scores, ratings and comments for this class. Only the class teacher can submit."
- Teacher detail shows "Class teacher of Primary 4A (all subjects)" or "Assistant in Primary 4A".


---

## 11. Prototype flows to make clickable

Build these as linked flows, phone and desktop where marked:

1. **Teacher score entry** (phone): login → my sheets → grid → validation errors → fix → submit → status "Submitted".
2. **Review and return** (desktop): reviewer queue → sheet → return with comment → teacher sees comment → corrects with reason → resubmits.
3. **Approve and publish** (desktop): principal dashboard → approvals → approve → publish class → confirmation → notices sent.
4. **Parent result** (phone, dark mode): login → home → result notice → report view → download PDF → verify (VALID).
5. **Correction** (phone + desktop): parent reports a problem → principal investigates → reopens → republishes → verification of old version shows SUPERSEDED.
6. **Account provisioning** (desktop + phone): principal adds teacher (activation email) → teacher activates; principal adds student with temporary password → credential slip → student logs in and must change password.
7. **Parent and wards** (desktop): principal adds parent and links two children → parent home shows ward switcher.
8. **Subscription** (desktop): super admin edits pricing → generates invoices → principal sees billing card → Pay now → confirming → Paid with receipt and notice.
9. **Sidebar and theme** (desktop + phone): collapse/expand sidebar, open mobile drawer, switch light/dark.
10. **Create school** (desktop, NEW): Schools → Create school → pick a custom colour (see the contrast warning) → check code → principal details → Create → success screen.
11. **Lost principal login** (desktop, NEW): School detail → School admins → Change email → Send reset link → confirmation.
12. **Student login** (phone, NEW): school login link with code filled in → admission number and password → forced password change. Also the "Ask your school admin" text.
13. **Teacher find and enter** (phone, NEW): Sheets grouped by class → filter JSS 1A → open Mathematics → search "Zainab" → fix score.
14. **Form teacher** (phone and desktop, NEW): My class → broadsheet → student entry (comment, ratings, attendance) → Save and next → preview → Submit class sections.
15. **Attention after publish** (desktop and phone, NEW): Publish with principal's comments → dashboard attention card → Students needing attention filtered to JSS 1A; teacher's scoped view.
16. **Assessment setup** (desktop, NEW): School setup → Assessment → Senior Secondary → add CA3 and Project → total reaches 100 → Save.
17. **Nursery and Primary school** (desktop, NEW): Create school → School type "Nursery and Primary" → toggles set → Create; School detail → Features → turn Nursery off (confirmation) → type shows Custom.
18. **Skill ratings setup** (desktop, NEW): School setup → Assessment → Nursery → Skill ratings → Learning areas and skills → edit a skill and the rating scale.
19. **Class teacher and assistant** (desktop and phone, NEW): Primary 4A class page → choose class teacher → Teaches all subjects → add assistant; assistant on phone opens a sheet, saves, and sees no Submit button.
20. **Nursery report** (phone, NEW): Nursery 2 class teacher rates skills in a rating sheet → Submit; parent opens the Skills report view and the Early Years PDF.

---

## 12. Sample data (all fictional)

Use this data in every mockup so screens look real and consistent.

**Schools**
- School A: *Greenfield Model College*, 14 Chime Avenue, Independence Layout, Enugu, Enugu State, Nigeria. Email info@greenfield.edu.ng, phone 0803 000 1122. School code **GMC**. Levels: Junior Secondary, Senior Secondary. Colour: deep green #1E6B45 (chosen from the picker). Plan: Standard. **580** billable students. Features: all on. Login link `/login/GMC`.
- School A is **Secondary only** (Junior and Senior Secondary).
- School B: *Bright Stars Academy*, 3 University Road, Nsukka, Enugu State. Code **BSA**. Colour: maroon #7A1F2B. School type **Nursery and Primary** (Nursery and Primary report cards on, Secondary off). Nursery on **Skill ratings**, Primary on **Scores** with A to F. Correction queue off. Free pilot. Head teacher: Mrs. Chiamaka Nwafor (username `chiamaka.nwafor`).
- School C: *Royal Crest Schools*, Trans-Ekulu, Enugu. Code **RCS**. Colour: navy #1D3A6E. School type **Nursery, Primary and Secondary**.

**Session:** 2026/2027, First Term (8 Sep 2026 to 11 Dec 2026). Next term starts 5 Jan 2027.

**People (School A)**
- Principal: Mrs. Ngozi Okeke (username `ngozi.okeke`)
- Vice principal (additional school admin): Mr. Chukwudi Eze (username `chukwudi.eze`)
- Reviewer/HOD Sciences: Mr. Emeka Nwosu
- Mathematics teacher (JSS 1A, JSS 1B), form teacher of JSS 1A: Mr. Tunde Adebayo (username `tunde.adebayo`)
- English teacher: Mrs. Grace Etim
- Parent: Mr. Ikenna Obi (wards: Chukwuemeka Obi, JSS 1A; Adaeze Obi, JSS 3A)

**People and classes (School B)**
- Primary 4A class teacher (teaches all subjects): Mrs. Ifeoma Chukwu; assistant: Miss Ngozi Ani.
- Nursery 2 class teacher: Mrs. Amaka Udeh.
- Nursery 2 pupils: Chidera Okeke, Tolu Bamidele, Ebube Eze, Hauwa Sani, Somto Nnaji, Ada Onuoha.
- Primary 4A pupils: Kamsi Okafor, Bisi Adeleke, Uche Mba, Fatima Lawal, David Ezeh, Joy Akpan.
- Primary 4 subjects: English Studies, Mathematics, Basic Science and Technology, Social Studies, Civic Education, Igbo Language, Cultural and Creative Arts, Physical and Health Education, Christian Religious Studies, Computer Studies.
- Primary grading (A to F): A 70 to 100 Excellent; B 60 to 69 Very good; C 50 to 59 Good; D 45 to 49 Fair; E 40 to 44 Pass; F 0 to 39 Fail. Example: Kamsi Okafor, Mathematics total 65, B, Very good.
- Nursery learning areas and sample skills: Number work (Counts 1 to 20; Recognises shapes), Letter work (Recognises letters A to Z; Writes own name), Phonics (Sounds letters correctly), Rhymes and songs (Recites rhymes), Creative arts (Colours within lines), Social habits (Shares with others; Greets politely), Health habits (Washes hands), Physical development (Hops on one foot).
- Rating scale: Excellent (E), Very good (VG), Good (G), Fair (F), Needs improvement (NI). Example: Chidera Okeke, Number work: Counts 1 to 20 VG, Recognises shapes E; Hauwa Sani, Counts 1 to 20 NI.
- Nursery class teacher's comment example: "Chidera is cheerful and eager to learn. She counts confidently and enjoys rhymes."

**JSS 1A students:** Chukwuemeka Obi (GMC/2026/014), Amina Bello, Tobi Adeyemi, Ifeoma Nwankwo, Musa Ibrahim, Zainab Yusuf, Chinedu Okafor, Blessing Eze, Daniel Okon, Halima Garba, Kelechi Uche, Funmilayo Ajayi.

**JSS 1 subjects:** English Language, Mathematics, Basic Science, Basic Technology, Social Studies, Civic Education, Igbo Language, Agricultural Science, Computer Studies, Christian Religious Studies, Business Studies, Cultural and Creative Arts, Physical and Health Education.

**Assessment structures:** Junior Secondary CA1 /20, CA2 /20, Exam /60 = 100. Senior Secondary CA1 /10, CA2 /10, CA3 /10, Project /10, Exam /60 = 100. Pass mark 40.

**Form teacher sample (JSS 1A):** times school opened 60; Chukwuemeka Obi present 57 (absent 3); class teacher's comment "A focused and respectful student. Keep it up in Mathematics."; ratings Punctuality 5, Neatness 4, Politeness 5, Handwriting 4, Sports 3.

**Students needing attention sample (JSS 1A, First Term):** Musa Ibrahim, Mathematics 38 (F9); Halima Garba, Basic Science 35 (F9), Mathematics 39 (F9), average 46.2; Daniel Okon, average 38.5 (Average below pass mark, 6 failed subjects). Principal dashboard total: 37 subject results below 40% across JSS 1.

**Grading bands (editable defaults):** A1 75 to 100 Excellent; B2 70 to 74 Very good; B3 65 to 69 Good; C4 60 to 64 Credit; C5 55 to 59 Credit; C6 50 to 54 Credit; D7 45 to 49 Pass; E8 40 to 44 Pass; F9 0 to 39 Fail.

**Example score row:** Chukwuemeka Obi, Mathematics: CA1 16, CA2 15, Exam 47, Total 78, A1, Excellent, Subject position 2nd. Overall average 71.4, position 3rd of 32.

**Validation examples:** Musa Ibrahim CA2 empty (missing); Zainab Yusuf Exam 72 (over max 60).

**Return comment:** "Please check Tobi Adeyemi's CA2. The paper shows 14, not 4."

**Pricing (defaults):** Basic 1 to 499 students at ₦1,000; Standard 500 to 1,000 at ₦500; Premium 1,001 and above at ₦300 (per student per term). Volume pricing, cliff protection on.

**Billing example (School A):** Second Term 2026/2027 invoice, 580 students × ₦500 = ₦290,000, due 5 Jan 2027, Unpaid. Previous invoice First Term, 571 students, ₦285,500, Paid 2 Sep 2026, ref PSK-8F3K2Q. Capped example for the calculator: 642 students would be ₦321,000, capped to ₦300,300.

**Notices:**
- "First Term results for JSS 1 are now available" (automatic, parents and students of JSS 1, teachers)
- "Inter-house sports holds on Friday, 14 November" (everyone, pinned)
- "Payment received for Second Term subscription" (principal only)

**Report verification:** Report ID GMC-2627-T1-JSS1A-014, revision 1 (Superseded), revision 2 (Valid).

---

## 13. Microcopy guidelines

- Plain, friendly, specific. Say what happened and what to do next.
- No em dashes. Short sentences.
- Examples:
  - Error: "Exam score can't be more than 60."
  - Missing: "3 students still need scores. Show me."
  - Publish confirmation: "Publish JSS 1A results? Parents and students will be notified and results become final. Any later change needs a correction with a reason."
  - Login error: "That login didn't work. Check your details and try again."
  - Empty state (teacher): "No score sheets yet. Your principal will assign your subjects."
  - Payment confirming: "Confirming your payment. This usually takes a few seconds."
  - Student tab: "Forgot your password? Ask your school admin for a new one."
  - Structure total: "Total 95. Add 5 more to reach 100."
  - Locked structure: "Scores have been entered for First Term, so this structure is locked. Changes you save will apply from Second Term."
  - Publish blocked: "Form teacher comments for JSS 1A are not submitted yet."
  - Attention empty: "No results below the pass mark for this selection."
  - Temporary password: "This password is shown only once. Print the slip or copy it now."
  - School paused: "Your school's access is paused. Contact your school admin."
  - Teaches all subjects: "Gives this teacher every subject in Primary 4A, including subjects added later."
  - Assistant note: "Assistants can enter scores, ratings and comments for this class. Only the class teacher can submit."
  - Rating sheet: "3 skills not rated yet. Show me."
  - Level toggle off: "Turning off Nursery report cards hides Nursery for this school. Its data and published reports are kept."
  - Level not on: "Secondary report cards are not switched on for this school. Contact SchoolFlow support."
- Never show internal codes or technical words to parents, students or teachers.

---

## 14. Prompts

The first-round prompts are done (the approved handoff). For the v0.4 changes, use `DESIGN_UPDATE_PROMPT.md`: one main prompt to paste first, then follow-up prompts one at a time.

---

## 15. Design acceptance checklist

- [ ] Every P1 screen exists for phone and desktop, in light and dark.
- [ ] Empty, loading, error and no-access states designed.
- [ ] Nothing scrolls sideways at 320px; tables scroll inside their container or become cards.
- [ ] Sidebar expanded, collapsed (with tooltips) and mobile drawer states exist.
- [ ] Every status uses icon + text, not colour alone.
- [ ] Text contrast meets WCAG AA in both themes, including school brand colours.
- [ ] Touch targets are at least 44 × 44px on phones.
- [ ] Focus states are visible for keyboard users.
- [ ] No register or sign-up button anywhere.
- [ ] Emails and notices never display scores.
- [ ] Verification page shows a masked name only, never scores.
- [ ] Report cards and print previews use the light print design.
- [ ] Naira amounts show as ₦321,000; dates as 5 Jan 2027.
- [ ] Only fictional data appears.
- [ ] Copy follows Section 13.
- [ ] Login has Staff and parents and Student tabs; the Student tab has a school code and no forgot link.
- [ ] No "Graduated" pricing option anywhere; cliff protection and price check are shown.
- [ ] Score grid works with 3 and 5 components on phone and desktop.
- [ ] Students needing attention is never reachable from parent or student screens.
- [ ] Report ID, revision, date and QR are shown as always on in the template editor.
- [ ] School colour picker is a full picker with a contrast warning, not a fixed swatch list.
- [ ] School type and report card toggles appear only to the super admin; school admins see levels but cannot change them.
- [ ] Skills report card and rating sheet show no totals, grades or positions; ratings always show a word or code, not colour alone.
- [ ] Assistants never see a Submit button.
- [ ] Head's title changes the comment and signature labels on report cards.
- [ ] `NAVIGATION_AND_SETTINGS.md` updated with every new label.

---

## 16. Out of scope for design now

Logging in as another user, form teachers posting notices, school fees collection from parents, attendance register, admissions, timetable, LMS, CBT, live classes, hostel, transport, payroll, SMS/WhatsApp settings, native apps and the free-form report designer. A "Coming soon" roadmap page is fine, but do not design these modules.
