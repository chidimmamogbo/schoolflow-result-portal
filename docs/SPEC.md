# SchoolFlow Result Portal: Specification

| | |
|---|---|
| Version | 0.5 |
| Date | 2026-10-07 |
| Status | Agreed for build |
| Owner | Chidimma Merit Mogbo |
| Product name | SchoolFlow Result Portal (planning name: ResultChain) |
| Source documents | School_Management_Platform_Capstone_Proposal.md (vision), Revised_Two_Week_Results_Trust_Chain_MVP.md (MVP), schoolflow-ui-handoff (approved UI) |
| Pace | Flexible. Target about two weeks, but there is no fixed deadline. We work session by session, doing as much as we can each day until we are tired or the session limit is reached, and stop cleanly each time (see BUILD_PROMPT.md, Working rules). Done means working, tested, secured, deployed and demoed |

> **Updates:**
> - v0.1: results trust chain MVP (results, approvals, audit, report cards, verification, parent portal, corrections, dashboard).
> - v0.2: account provisioning by school admins, login-only model, student and teacher registration with assignments, guardian ward linking, notice board, email notifications, SaaS dashboard shell, full responsiveness, dark/light mode.
> - v0.3: per-school subscription billing with an editable per-student, per-term pricing table and online payment in test mode.
> - v0.4: product renamed SchoolFlow Result Portal; username login for everyone; student login with school code; password reset rules (no self-service for students, super admin resets school admins); additional school admins; configurable assessment structures per level (any number of CAs); teacher sheet search and filters; form teacher tools (broadsheet, comments, ratings, attendance, preview); Students needing attention list; expanded super admin functions and platform settings; full Create school form with colour picker and set-up emails; more report template styles and block settings; graduated pricing removed, volume pricing with optional cliff protection.
> - v0.5: nursery and primary report cards; school type (Nursery and Primary, Secondary only, or all) with report card toggles per level controlled by the super admin; each school chooses Scores or Skill ratings per level; Primary A to F grading default; one-step class teacher (teaches all subjects) with class teacher assistants; Skills report card with an Early Years style; head's title per level; flexible session-by-session pace instead of a fixed 14 days; "if time allows" items renamed "build after the core" (nothing dropped).

## 1. Summary

SchoolFlow Result Portal is a results-first, multi-school platform for Nigerian nursery, primary and secondary schools. Teachers enter scores (or skill ratings for younger pupils) once, the system catches errors before publication, the right people approve, each school issues its own branded report card, and parents receive a verifiable record with a full correction history. Schools pay per registered student per term. The wider SchoolFlow school management system and LMS in the capstone proposal is the long-term vision; this spec covers the MVP.

## 2. Problem and evidence

- Results week in Nigerian schools involves duplicated score entry, calculation errors, slow approval, late release, and disputes about who changed a score.
- Published research on Nigerian result-processing systems reports duplicated work, slow processing, calculation errors, possible tampering and fake results, and inefficient retrieval.
- Spreadsheet-based data collection in Nigerian education has documented data-quality problems that needed later cleaning.
- In the public materials reviewed for nine existing products, no clearly documented end-to-end combination was found of immutable published snapshots, old/new score history, controlled reopen and reapproval, parent verification, and correction tickets linked to revised results.
- Schools differ in how many continuous assessments they run, so a fixed CA1, CA2, Exam structure does not fit every school.
- Many schools are nursery and primary only, many are secondary only, and many run all three. Nursery report cards usually rate skills instead of giving scores, but some schools score nursery pupils too.
- **To validate:** interviews with at least one teacher and one principal, two redacted real report cards, and willingness to pay per student per term.

## 3. Goals, non-goals and success measures

**MVP goals**
1. A school can go from score entry to a published, verified, branded report card with a complete audit trail.
2. Every account is provisioned by an authorised admin; every user sees only what their role and links allow.
3. Parents get results through a phone-friendly portal, a notice and an email, and can raise a traceable correction.
4. Principals and teachers see, straight after publication, which students scored below the pass mark.
5. The platform owner can create and support schools, price, invoice and collect payment from each school.
6. The product looks and feels like a modern SaaS on any device, in light or dark mode.
7. A school with nursery, primary, secondary or any mix of them gets report cards that fit each level, assessed the way that school chooses.

**Non-goals (MVP)**
- School fee collection from parents, attendance module (beyond the attendance numbers typed for the report card), admissions, timetables, LMS, CBT, live classes, hostel, transport, payroll, library, inventory, SMS/WhatsApp, offline sync, predictive analytics, native apps, free-form report designer, WAEC/NECO integration, live payment processing, logging in as another user.

**Success measures**
- The 38-step demo script passes end to end on the deployed system at phone, tablet and desktop sizes in both themes.
- The security gate has every row PASS.
- At least one real teacher tries the deployed workflow and their feedback is recorded.

## 4. Users, roles and account model

| Role | Who they are | Created by | How they log in | Password reset |
|---|---|---|---|---|
| Super admin | Platform owner | Seed/CLI command only | Email or username + password | Forgot password by email; CLI fallback |
| Principal (primary school admin) | Head of a school | Super admin | Email or username + password | Forgot password by email; super admin can reset |
| Additional school admin | Vice principal or school administrator | Principal | Email or username + password | Forgot password by email; super admin or principal can reset |
| Reviewer/HOD | Head of department or reviewer | School admin | Email or username + password | Forgot password by email if they have one; otherwise school admin resets |
| Teacher (subject teacher, optionally form teacher; called class teacher in Nursery and Primary) | Teacher | School admin | Email or username + password | Same as reviewer |
| Class teacher assistant | Teacher who helps a class teacher | School admin (assigned per class) | Email or username + password | Same as reviewer |
| Parent/guardian | Guardian of one or more students | School admin | Email or username + password | Same as reviewer |
| Student | Enrolled learner | School admin | School code + username or admission number + password | No self-service. School admin issues a new temporary password |

- **Registration model:** provisioned only. There is no public sign-up or register route for any role.
- **Tenancy:** many schools on one platform. No school can see another school's data.
- **Usernames:** every account has a username. Staff, parent and super admin usernames are unique across the platform. Student usernames and admission numbers are unique within their school. Usernames are 3 to 30 characters (lowercase letters, numbers, dot, underscore, hyphen), cannot contain "@", and are suggested from the person's name (for example `ngozi.okeke`) but editable.
- **Login details:** passwords are never emailed or stored in plain text. Activation and reset links are single use and expiring. Temporary passwords are shown once (printable credential slip) and force a change at first login.
- **No impersonation:** nobody, including the super admin, can log in as another user.

## 5. Permission matrix

| Capability | Super admin | Principal | Additional admin | Reviewer/HOD | Teacher | Parent | Student |
|---|---|---|---|---|---|---|---|
| schools.manage (create, edit, suspend) | Yes | No | No | No | No | No | No |
| features.toggle | Yes | No | No | No | No | No | No |
| report_card_levels.toggle (Nursery, Primary, Secondary) | Yes | No | No | No | No | No | No |
| platform.settings | Yes | No | No | No | No | No | No |
| platform.audit / email log / payments log | Yes | No | No | No | No | No | No |
| school_admins.reset_login / sign_out_all | Yes | Additional admins only | No | No | No | No | No |
| school_admins.create / remove | No (creates the principal only) | Yes (own school, up to the limit) | No | No | No | No | No |
| pricing.manage | Yes | No | No | No | No | No | No |
| invoices.generate / payments.record_manual | Yes | No | No | No | No | No | No |
| school.settings | No | Yes | Yes | No | No | No | No |
| users.create (reviewer, teacher, parent, student) | No | Yes | Yes | No | No | No | No |
| users.reset_login (reviewer, teacher, parent, student) | No | Yes | Yes | No | No | No | No |
| assignments.manage / guardian_links.manage | No | Yes | Yes | No | No | No | No |
| grading.configure / assessment.configure / pass_mark.configure / assessment_mode.configure / skills.configure | No | Yes | Yes | No | No | No | No |
| scores.enter / ratings.enter | No | No | No | No | Assigned sheets only (assistants: their class's sheets) | No | No |
| sheets.submit | No | No | No | No | Assigned sheets only (assistants cannot submit) | No | No |
| sheets.review / return | No | No | No | Scope only | No | No | No |
| form_class.report_entries (comment, ratings, attendance) | No | View, return | View, return | No | Own form class only (assistants can enter, not submit) | No | No |
| sheets.approve / results.publish / principal_comments | No | Yes | Yes | No | No | No | No |
| results.reopen / revoke | No | Yes | Yes | No | No | No | No |
| attention.view (Students needing attention) | No | All classes | All classes | Scope only | Own subjects in assigned classes, plus all subjects of own form class | No | No |
| audit.view | Platform log | School timeline | School timeline | No | No | No | No |
| report_templates.manage | No | Yes | Yes | No | No | No | No |
| reports.view | No | Yes | Yes | Scope only | Assigned classes and own form class | Linked wards, published only | Self, published only |
| corrections.create | No | Yes | Yes | Yes | Yes | Linked wards | No |
| corrections.manage | No | Yes | Yes | No | No | No | No |
| notices.post | Platform announcements (after the core) | Yes | Yes | No | No | No | No |
| notices.read | Platform | Yes | Yes | Addressed only | Addressed only | Addressed only | Addressed only |
| billing.view / invoices.pay | Platform view | Own school | Own school | No | No | No | No |

**Ownership rules:** "Assigned" means a teacher_assignment for that subject and class/arm. A class teacher who "teaches all subjects" is assigned every subject of that arm. A class teacher assistant can enter scores, ratings, comments and attendance for the class they assist, but cannot submit anything. "Own form class" means the arm where the teacher is the form teacher. "Scope" means the reviewer's department or listed subjects/classes. "Linked wards" means guardian_students links. Separation of duties: whoever submitted a sheet cannot review or approve it.

## 6. Scope

### In the MVP
F01 to F26 below.

### Build after the core (nothing is dropped; these come once F01 to F26 work, never at the expense of tests or security)
- Report template styles Bold Banner, Ink Saver and Cumulative (third term).
- Platform announcements from the super admin to school admins.
- Two-factor login for super admin accounts.

### Out of the MVP (roadmap)
- School fee collection from parents: separate module with bursar roles.
- Live payment processing: needs gateway compliance approval.
- Attendance module, admissions, timetables, LMS, CBT: proposal phases 2 and 4.
- Live classes (Google Meet, Zoom, Agora, self-hosted): proposal phase 5.
- Hostel, transport, staff and payroll: proposal phase 6.
- SMS/WhatsApp, offline sync, analytics: proposal phase 7.
- Form teachers posting notices to their class's parents.
- Free-form report designer, native apps, WAEC/NECO integration.

## 7. Features

### F01. Multi-tenant platform and feature flags
- **Purpose:** host many schools with isolated data and per-school modules.
- **Users:** super admin.
- **Feature flags:** `results`, `report_cards`, `parent_portal`, `correction_queue`, `notice_board`, `email_notifications`. Billing is a platform setting per school, not a school-controlled flag.
- **Rules:** every school-owned record carries the school ID; the current school comes from the authenticated membership; database row-level security enforces isolation; disabled features are rejected by the server and hidden from menus. Seed data covers two schools.
- **Acceptance:**
  - AC01.1 Given School B has `results` off, when a School B admin calls a results endpoint, then it is rejected.
  - AC01.2 Given a School A session, when it requests a School B student ID, then the response is not found.
- **Edge cases:** a flag switched off mid-term hides the module but keeps data.

### F02. Authentication (login only)
- **Users:** all.
- **Rules:**
  1. Login page with two tabs: **Staff and parents** (Email or username, Password) and **Student** (School code, Username or admission number, Password).
  2. Opening a school's own login link (for example `/login/GMC`) opens the Student tab with the school code filled in and shows the school's name and logo.
  3. Generic error message for every failure; the response never reveals whether an account, username or school code exists.
  4. Rate limiting per identifier and per IP; temporary lockout after repeated failures.
  5. Session tokens in httpOnly, Secure cookies; refresh and logout; "sign out of all devices" support.
  6. Forced password change after any temporary password.
  7. **Forgot password** is offered on the Staff and parents tab only. It sends a reset link to the account's verified email and always shows the same confirmation. Accounts without an email are told to ask their school admin.
  8. The Student tab shows no forgot password link. It shows: "Forgot your password? Ask your school admin for a new one."
  9. A successful password reset signs the user out of every other session and sends a "your password was changed" email when the account has an email.
  10. No register route.
- **Acceptance:**
  - AC02.1 Given any role, when visiting a register URL, then it is not found.
  - AC02.2 Given a temporary password, when the user logs in, then they must set a new password before anything else.
  - AC02.3 Given a used or expired activation or reset link, when opened, then it is rejected.
  - AC02.4 Given repeated failed logins, when the limit is exceeded, then further attempts are throttled.
  - AC02.5 Given a teacher, when they log in with their username or with their email, then both work.
  - AC02.6 Given two schools that both have admission number 2026/014, when a student logs in with school code GMC, then only Greenfield's student is matched.
  - AC02.7 Given a wrong school code, a wrong username or a wrong password, when logging in, then the same generic error is shown.
  - AC02.8 Given the forgot password endpoint, when called for a student account, then no reset email is sent and the response is the same as for any other request.

### F03. Account provisioning, school admins and password resets
- **Users:** super admin, school admins.
- **Rules:**
  1. Super admin creates schools and each school's principal (the primary school admin).
  2. The principal can add **additional school admins** (for example a vice principal), up to the platform limit (default 2). Additional admins have the same school permissions as the principal, except that they cannot add, remove or reset other school admins.
  3. School admins create reviewers, teachers, parents and students in their own school only. Nobody creates a role above their own.
  4. Every create form asks for a username (suggested from the name, checked for availability) and a login method: activation email or temporary password.
  5. **Super admin login support for school admins:** change the admin's email, send a reset link, issue a temporary password with a printable slip, resend activation, sign out of all devices, deactivate or reactivate, and make another school admin the principal. The super admin cannot reset teachers, reviewers, parents or students; their school admins do that.
  6. **School admin login support for their people:** resend activation, send a reset link (if the person has an email), issue a temporary password with a printable slip, deactivate or reactivate.
  7. Every provisioning and reset action is audited and never reveals the user's password.
- **Acceptance:**
  - AC03.1 Given an additional school admin, when trying to add another school admin, then it is denied.
  - AC03.2 Given a school admin of School A, when creating a user in School B, then it is denied.
  - AC03.3 Given a deactivated user, when they try to log in or use a session, then access is refused immediately.
  - AC03.4 Given the school has reached the additional admin limit, when the principal adds another, then it is refused with a clear message.
  - AC03.5 Given the super admin resets a principal's login, when it completes, then the principal's existing sessions end, the reset is in the platform audit log, and the super admin never sees a password other than a one-time temporary one.
  - AC03.6 Given the super admin, when trying to reset a teacher's password, then it is denied.

### F04. School structure
- **Users:** school admins.
- **Rules:** academic sessions and terms (one active pair, with start and end dates used for billing renewal and "next term begins" on report cards), school levels (Nursery, Primary, Junior Secondary, Senior Secondary, limited to the levels switched on for the school in F25), classes and arms linked to a level, departments, subjects; branding (logo, colour, address, contacts).
- **Acceptance:**
  - AC04.1 Given an active term, when another term is activated, then the previous one is deactivated.
  - AC04.2 Given Secondary report cards are off for a school, when its admin creates a JSS 1 class, then it is rejected.

### F05. Student registration, enrolment and subjects
- **Users:** school admins.
- **Rules:** create one student or bulk import by CSV (preview, row errors, all-or-nothing); admission number and username unique per school; optional house; enrol into a class/arm for the active session; subjects default to the class's subjects and can be adjusted per student; moving arms keeps history.
- **Acceptance:**
  - AC05.1 Given a CSV with one duplicate admission number, when committing, then nothing is saved and the row error is shown.
  - AC05.2 Given a student without a subject, when a teacher opens that subject's sheet, then the student is not listed.

### F06. Teacher and reviewer registration and assignment
- **Users:** school admins.
- **Rules:**
  1. Teachers get subject + class/arm assignments and optionally become form teacher of one arm. Reviewers/HODs get a department or subject/class scope. Teachers and reviewers see only their assignments or scope.
  2. **Class teacher in one step:** when assigning a teacher to an arm, the admin can tick "Teaches all subjects". The teacher is then assigned every subject (or learning area) of that arm, now and when subjects are added later, and becomes its class teacher. This is the usual set-up in Nursery and Primary, and it works at any level.
  3. **Class teacher assistants:** the admin can add up to 2 assistants to an arm. An assistant sees the class's sheets and My class, and can enter scores, ratings, comments and attendance, but cannot submit sheets or class sections; the class teacher submits. Every entry records who made it.
- **Acceptance:**
  - AC06.1 Given a teacher assigned Mathematics JSS 1A only, when requesting the JSS 1B Mathematics sheet, then it is denied.
  - AC06.2 Given a teacher assigned to Primary 4A with "Teaches all subjects", when a new subject is added to Primary 4A, then that teacher gets its sheet automatically.
  - AC06.3 Given an assistant for Primary 4A, when they try to submit a sheet or the class sections, then it is denied; their saved scores show their name in the audit timeline.

### F07. Guardian registration and ward linking
- **Users:** school admins, parent.
- **Rules:** create a guardian with relationship and contact details, linked to one or more students at creation; links editable later; a student can have several guardians; access follows links immediately.
- **Acceptance:**
  - AC07.1 Given a parent linked to one child, when they request another child's report, then it is not found.
  - AC07.2 Given a link is removed, when the parent refreshes, then the ward is gone from their dashboard.

### F08. Assessment structure, grading and result engine
- **Users:** school admins (configuration), system.
- **Rules:**
  0. **Assessment mode per level.** For each level switched on (F25), the school chooses **Scores** or **Skill ratings** (F26). Defaults: Nursery uses Skill ratings; Primary, Junior Secondary and Senior Secondary use Scores. A school can choose Scores for Nursery or Skill ratings for Primary. The mode is locked for a term once any entry exists at that level. Everything below in this feature applies to levels in Scores mode.
  1. **Assessment structure per level.** School admins set the components for each level: any number from 1 to 8 (for example CA1, CA2, CA3, CA4, Assignment, Project, Test, Practical, Exam). Each has a name, a short label for columns, a maximum score and an order. The maximums must add up to exactly 100.
  2. Different levels can use different structures (for example Primary: CA1, CA2, Exam; Senior Secondary: CA1, CA2, CA3, Project, Exam). New schools start from the platform default (CA1 20, CA2 20, Exam 60).
  3. Once any score exists for a term at a level, that level's structure is locked for the term. Changes apply from the next term. The structure used is stored with each result.
  4. Pass mark per school (default 40), used for the Students needing attention list and the "below pass mark" highlight.
  5. Editable grading bands per level. Defaults: Junior and Senior Secondary use A1 to F9 (not presented as official WAEC mappings); Nursery (in Scores mode) and Primary use A to F: A 70 to 100 Excellent, B 60 to 69 Very good, C 50 to 59 Good, D 45 to 49 Fair, E 40 to 44 Pass, F 0 to 39 Fail. Remark bands per level.
  6. Rating traits for affective and psychomotor domains, editable per school with defaults, and a rating scale of 1 to 5 with a key.
  7. Raw scores stored separately from derived totals; subject and class averages; subject and overall positions with ties ("1st, 1st, 3rd"); calculation version stored with each computed result.
- **Acceptance:**
  - AC08.1 Given two students tie on total, when positions are computed, then both share the position and the next is skipped.
  - AC08.2 Given components whose maximums add up to 95, when saving the structure, then it is rejected with the difference shown.
  - AC08.3 Given scores exist for this term at Junior Secondary, when an admin edits the Junior Secondary structure, then the change is saved for next term only.
  - AC08.4 Given Senior Secondary uses five components, when a teacher opens an SS sheet, then the grid shows those five columns.
  - AC08.5 Given a Primary 4 total of 65, when graded with the default Primary bands, then the grade is B.
  - AC08.6 Given ratings exist for First Term at Nursery, when the admin tries to switch Nursery to Scores, then the change is saved for next term only.

### F09. Score entry and CSV import
- **Users:** teacher.
- **Rules:**
  1. One score sheet per subject per class/arm assigned to the teacher. The teacher's sheets page groups sheets by class, shows status and progress, and filters by class, subject and status.
  2. Inside a sheet: search by name or admission number to jump to a student; filter All, Missing, Errors.
  3. Columns come from the level's assessment structure.
  4. Phone-friendly grid (one card per student on phones) with immediate validation (missing, over the maximum, duplicate); save draft; changing a saved score needs a reason; submit only when validation passes.
  5. CSV template built from the structure, preview, row errors with download, all-or-nothing commit; export the sheet as CSV.
  6. Levels in Skill ratings mode use rating sheets instead (F26), with the same sheets page, search, filters and workflow.
- **Acceptance:**
  - AC09.1 Given a missing or out-of-range score, when submitting, then submission is blocked with the problem highlighted.
  - AC09.2 Given an import with one invalid row, when committing, then no scores are written.
  - AC09.3 Given a sheet of 40 students, when the teacher searches "Zainab", then the grid jumps to Zainab Yusuf's row.

### F10. Approval workflow
- **State machine:** see section 8.
- **Rules:** teachers submit; reviewers return (comment required) or mark reviewed; school admins approve; publishing a class + term requires all subject sheets (or rating sheets) approved and the form teacher's class sections submitted (only the sections shown on the active template); the principal's comments are entered on the publish screen; submitted and approved sheets are locked to teachers; reopening needs a reason and creates a new revision that goes through review and approval again.
- **Acceptance:**
  - AC10.1 Given a teacher submitted a sheet, when the same user tries to approve it, then it is denied.
  - AC10.2 Given a reviewer, when trying to edit a score, then it is denied (they can only return with a comment).
  - AC10.3 Given the form teacher has not submitted comments for JSS 1A and the template shows comments, when publishing JSS 1A, then publishing is blocked with "Form teacher comments are not submitted".

### F11. Audit history and immutable revisions
- **Rules:** every score change, configuration change (including assessment structures and pass mark), account action (including resets and sign-outs), form teacher entry, notice edit, pricing change and payment record logs actor, role at the time, timestamp, old value, new value, reason and revision; audit events are append-only at the database level; published snapshots cannot be updated or deleted; school admins see a readable school timeline; the super admin sees a platform audit log.
- **Acceptance:** AC11.1 Given a published report, when the app's database role attempts an update, then the database refuses it.

### F12. Report templates and PDF
- **Users:** school admins.
- **Rules:**
  0. **Report card types and levels.** Each level that is switched on has its own template. Levels in Scores mode use the **Score report card** (the blocks below). Levels in Skill ratings mode use the **Skills report card** (F26). Template settings include **Head's title** (Principal, Head teacher, Head of school, Proprietor, Director, or custom), defaulting to Head teacher for Nursery and Primary and Principal for Secondary; it labels the head's comment and signature.
  1. **Styles** (presets over the same block engine): Modern (default), Classic, Compact (fits 15 or more subjects on one page) and **Early Years** (larger type, softer colours, friendly layout, made for Nursery and lower Primary, and the default for Skills report cards) in the core build. Bold Banner, Ink Saver (black and white) and Cumulative (third term, with first, second and third term columns, annual average and promotion result) after the core.
  2. **Blocks**, in default order: School header, Student details, Subject table, Summary, Affective and psychomotor, Attendance, Comments, Signatures, Footer with QR and report ID. Each block can be shown or hidden and moved up or down, except the footer, which is always shown and always last.
  3. **Block settings:**
     - School header: Logo, Logo position (Left, Centre, Right), School motto, Address, Phone and email, Report title (editable, default "Student Report Card"), Session and term line.
     - Student details: Photo, Admission number, Gender, Age, Date of birth, Class and arm, House, Form teacher's name.
     - Subject table: a switch per assessment component column, Total, Grade, Remark, Position in each subject, Class average per subject, Highest in class, Lowest in class, Subject teacher's initials, Highlight scores below pass mark, Row shading.
     - Summary: Total score, Total average, Overall class position (optional), Number in class, Class average, Number of subjects, Promotion result. When Overall class position is off, the summary shows Number in class.
     - Affective and psychomotor: Affective, Psychomotor, Rating key, Layout (Side by side, Stacked).
     - Attendance: Times school opened, Times present, Times absent.
     - Comments: Form teacher's comment, Principal's comment, Show names.
     - Signatures: Form teacher signature line, Principal signature image (upload), School stamp image (upload), Date line.
     - Footer: QR position (Left, Right), Next term begins, School contact line, Custom footer note. Report ID, revision, publication date and the QR code are always on and cannot be hidden.
  4. **Template settings:** Paper size (A4, Letter), Font (Inter, Merriweather, Nunito), Text size (Small, Medium, Large), Accent colour (school colour by default, or any colour), Borders (None, Lines, Boxed), Logo watermark, Grading key (Off, Below summary, In footer), Margins (Narrow, Normal).
  5. Templates save as versioned JSON, one per level if needed. PDFs render from the published snapshot and template version, always in the light print design.
- **Acceptance:**
  - AC12.1 Given two different real-format templates, when previewing with seeded data, then both reproduce their layouts.
  - AC12.2 Given a template with Highest in class switched on, when a report is published, then each subject row shows the class's highest score for that subject.
  - AC12.3 Given any template, when an admin tries to hide the report ID or QR code, then the control is not available and the API rejects it.
  - AC12.4 Given a school with Nursery in Skill ratings mode and Primary in Scores mode, when reports are published, then Nursery pupils get a Skills report card and Primary pupils get a Score report card, each using its level's template and head's title.

### F13. Report verification
- **Users:** public.
- **Rules:** each published report has a human-readable report ID and an opaque, non-guessable verification code; the QR holds only a URL with the code; the public page shows school, masked student name, session, term, status (VALID, SUPERSEDED, REVOKED), revision and publication date; lookups are rate limited.
- **Acceptance:** AC13.1 Given a report was corrected and republished, when the old code is verified, then it shows SUPERSEDED.

### F14. Parent and student portal
- **Rules:** parents see linked wards (ward switcher), students see themselves; published results only; low-bandwidth online view; PDF download; report status and revision; correction requests (parents). Nursery pupils usually have no login of their own; their parents see their reports. Students never see the Students needing attention list or other students' results.
- **Acceptance:** AC14.1 Given a sheet is APPROVED but not PUBLISHED, when a parent views results, then it is not shown.

### F15. Correction and dispute queue
- **Users:** parent, teacher, reviewer create; school admins manage.
- **Rules:** fields: student, term/session, subject or section, issue type, explanation, optional attachment (validated), requester, dates, status, admin response. Statuses: OPEN, INVESTIGATING, RESOLVED, REJECTED, NEEDS_MORE_INFORMATION. A reopen caused by a ticket links the new revision to the ticket.
- **Acceptance:** AC15.1 Given a ticket leads to a reopen, when the new revision is published, then the ticket shows the linked revision.

### F16. Results-week dashboard
- **Users:** school admins.
- **Rules:** counts awaiting submission, review and approval; form teacher sections still open; missing and invalid scores; subject and class averages; pass rate; term trend; unusual score changes; open corrections; a Students needing attention card after publication. No predictions.

### F17. Notice board
- **Users:** all roles read; school admins post. Form teachers do not post in the MVP.
- **Rules:** audience: everyone, selected roles, optionally selected classes; pin, edit, archive (audited); unread badge and read state; automatic notice on result publication to affected students, their guardians, and relevant teachers and reviewers; automatic notice to school admins when an invoice is paid; school-scoped.
- **Acceptance:**
  - AC17.1 Given a notice for JSS 1 parents, when a JSS 2 parent opens the board, then it is not shown.
  - AC17.2 Given a School A notice, when any School B user opens the board, then it is not shown.

### F18. Email notifications
- **Rules:** emails for school set-up (school email), activation (with username and, for school admins, the school code), password reset, password changed, result publication, payment receipts; result emails go to every affected guardian, students with email, and involved staff; no scores or personal results in emails, only a message and a login link; no passwords in any email; outbox with queued/sent/failed status and retries; background sending; free-tier daily limits respected by leaving messages queued; users without email still get the notice.
- **Acceptance:** AC18.1 Given results are published, when the outbox is inspected, then each intended recipient has exactly one queued message and none contains scores.

### F19. School subscription billing
- **Users:** super admin, school admins.
- **Rules:**
  1. **Pricing model: volume.** The school's number of billable students picks the plan, and every student is charged that plan's price per term. (Graduated pricing is not used.)
  2. Pricing table edited by the super admin: plans with name, minimum students, maximum students (blank for open-ended) and price per student per term in Naira. Defaults: Basic 1 to 499 at ₦1,000; Standard 500 to 1,000 at ₦500; Premium 1,001 and above at ₦300.
  3. Plans must be inclusive, non-overlapping and gap-free; validated before saving.
  4. **Cliff protection** (platform setting, on by default): a school never pays more than the smallest possible bill on any higher plan (that plan's minimum students times its price). The invoice records when the cap applied.
  5. **Price check:** the pricing editor lists any student ranges where a bigger school would pay less than a smaller one, so the super admin can adjust prices.
  6. Saving creates a new pricing version; issued invoices keep their version and price.
  7. Billing on/off per school (free pilot). Subscription statuses: FREE_PILOT, ACTIVE, DUE, OVERDUE, SUSPENDED. Grace period set by the super admin. Suspension is manual and never deletes data.
  8. One invoice per school per term, generated by the super admin for one or all billable schools. Snapshot: term, billable student count (active enrolled students at generation), plan, rate, pricing version, whether cliff protection applied, amount, due date, status (UNPAID, PAID, VOID). Adjustment invoices for later additions.
  9. Money stored as integer kobo.
  10. School admin billing card: plan, billable students, price per student, amount due, due date, next renewal date (start of next term), status, projected next-term cost; Pay now; invoice history marked PAID (date, reference) or UNPAID; receipts.
  11. Payment through a Nigerian gateway in test mode; one-time payment per invoice; amount from the server invoice; invoice marked PAID only after a signature-verified webhook and a server-side transaction check; idempotent; mismatched amount or currency rejected.
  12. Super admin can record a manual payment with reference and note (audited) and void invoices.
- **Acceptance:**
  - AC19.1 Given plans that overlap, when saving, then the save is rejected.
  - AC19.2 Given cliff protection off, when invoices are generated for 499, 500, 1,000 and 1,001 billable students, then the amounts are ₦499,000; ₦250,000; ₦500,000; ₦300,300.
  - AC19.3 Given cliff protection on, when invoices are generated for 499, 580, 642, 1,000 and 1,001 billable students, then the amounts are ₦250,000 (capped); ₦290,000; ₦300,300 (capped); ₦300,300 (capped); ₦300,300.
  - AC19.4 Given the default prices, when the super admin opens the pricing editor, then the price check reports that schools with 251 to 499 students and schools with 601 to 1,000 students would pay more than a larger school.
  - AC19.5 Given an issued invoice, when the pricing table changes, then the invoice amount does not change.
  - AC19.6 Given a forged webhook, when received, then it is rejected and the invoice stays UNPAID.
  - AC19.7 Given the same valid webhook twice, when processed, then only one payment and one receipt exist.
  - AC19.8 Given a school admin of School A, when requesting School B's invoice, then it is not found.
  - AC19.9 Given billing is off for a school, when its admin opens the dashboard, then no invoices or payment prompts appear.

### F20. Dashboard shell, responsiveness and themes
- **Rules:** SaaS layout for every role: sidebar with icons and labels, expand/collapse toggle icon, icon-only mode with tooltips, remembered state, mobile slide-out drawer; header with school logo/name, notice bell with unread count, theme toggle (light, dark, system) and profile menu; role- and flag-aware menus; works from 320px to large desktops; wide tables scroll in their own container or become cards; every screen designed and tested in both themes with AA contrast; no flash of the wrong theme; PDFs and print always light.
- **Acceptance:** AC20.1 Given the demo flow, when run at 360px, 768px and 1440px in light and dark mode, then every step passes with no horizontal page scrolling.

### F21. Privacy basics
- **Rules:** plain-language privacy notice; guardian relationship and consent fields; least privilege; no student data in QR payloads; no real student data in prompts, seeds or screenshots; export/delete design notes; retention placeholder; report revocation; attachment type and size limits; the Students needing attention list is staff-only. This is privacy-by-design, not a legal compliance claim.

### F22. Form teacher tools
- **Users:** a teacher who is form teacher of an arm (shown as "class teacher" in Nursery and Primary); class teacher assistants (enter, not submit); school admins (view and return).
- **Rules:**
  1. **My class** area, visible only to form teachers.
  2. **Class broadsheet** (read-only): every student against every subject, with each subject sheet's status, so the form teacher can see what is missing before results week ends.
  3. **Class teacher's comment** per student, with suggested comments from the remark bands that the teacher can edit (maximum 300 characters).
  4. **Affective and psychomotor ratings** per student on the school's traits and 1 to 5 scale.
  5. **Attendance numbers** for the report card: times school opened (once for the class) and times present per student; times absent is calculated. This is not an attendance register.
  6. **Report card preview** for any student in the class, marked "Preview, not published".
  7. In Skill ratings levels, the broadsheet shows each learning area's rating sheet status instead of subject scores.
  8. Assistants can enter comments, ratings and attendance; only the form or class teacher submits.
  9. Submitting the class sections locks them for the form teacher. School admins can return them with a comment. After publication, changes go through the correction and revision flow.
  10. The form teacher also sees the Students needing attention list for their class across all subjects (F23).
- **Acceptance:**
  - AC22.1 Given a teacher who is not a form teacher, when opening My class, then it is not available.
  - AC22.2 Given the form teacher of JSS 1A, when requesting the JSS 1B broadsheet, then it is denied.
  - AC22.3 Given times school opened is 60 and a student was present 55 times, when previewing the report, then times absent shows 5.
  - AC22.4 Given times present is greater than times school opened, when saving, then it is rejected.

### F23. Students needing attention
- **Users:** school admins, reviewers/HODs (scope), teachers (scoped as below).
- **Rules:**
  1. Generated automatically when a class's results are published, from the published snapshot, and regenerated when a corrected revision is republished.
  2. **By subject view:** every subject score below the school's pass mark: student, admission number, class/arm, subject, score, grade, subject teacher.
  3. **By student view:** each student with one or more failed subjects or an overall average below the pass mark: number of failed subjects, overall average, and a flag "Average below pass mark".
  4. Filters: session, term, class, arm, subject, and (school admins only) teacher. Export to CSV and print.
  5. Who sees what: school admins see every class; reviewers/HODs see their scope; a subject teacher sees only their subjects in their assigned classes; a form teacher also sees every subject for their form class.
  6. Dashboard cards: principal ("37 subject results below 40% in First Term"), teacher (their own count), each linking to the list.
  7. Parents and students never see this list. Only published results are included.
  8. **Skill ratings levels:** instead of scores below the pass mark, the list shows skills rated at or below the school's attention rating (default "Needs improvement"). By subject becomes **By learning area** (pupil, class, learning area, skill, rating); By student shows the number of skills needing attention.
- **Acceptance:**
  - AC23.1 Given the pass mark is 40 and a student scored 38 in Mathematics, when JSS 1A results are published, then that result appears in the By subject view.
  - AC23.2 Given the Mathematics teacher of JSS 1A and 1B who is not a form teacher, when opening the list, then only Mathematics results for JSS 1A and 1B appear.
  - AC23.3 Given the form teacher of JSS 1A, when opening the list, then all subjects for JSS 1A appear, plus their own subjects in other classes.
  - AC23.4 Given a parent or student session, when requesting the list, then it is denied.
  - AC23.5 Given results are approved but not published, when opening the list, then they are not included.
  - AC23.6 Given Nursery 2 in Skill ratings mode and a pupil rated "Needs improvement" in Counting 1 to 20, when Nursery 2 is published, then that skill appears in the By learning area view.

### F24. Platform administration and settings (super admin)
- **Users:** super admin.
- **Rules:**
  1. **Create school form:**
     - School details: School name, School email, Phone number, Address, City, State (dropdown of the 36 states and FCT when the country is Nigeria, free text otherwise), Country (default Nigeria), School code (suggested from the initials, 3 to 10 uppercase letters or numbers, unique, checked as you type), School type and report cards (F25), School colour (full colour picker with hex field, live preview in light and dark, warning when text on it would be hard to read), Logo (optional).
     - Features: the six switches.
     - Billing: Billing on, or Free pilot.
     - Principal account: Full name, Username (suggested, checked as you type), Email.
     - On "Create school and send invite": the principal gets a welcome email with an activation link, their username and the school code; the school email gets a set-up confirmation with the school code, the school's login link and support contacts. No password is sent. Both emails show in the email log.
  2. **Schools:** list with search and filters; school detail tabs Overview (details, usage: students, staff, parents, results published, last activity), Features, School admins, Subscription, Invoices, Activity (the school's platform-level audit events); edit details; change school code (warns that students must use the new code and the old code stops working); suspend or reactivate with a reason (users of a suspended school see "Your school's access is paused. Contact your school admin."; data is kept); resend the set-up email.
  3. **School admins tab:** the principal and additional admins with the login support actions from F03.
  4. **Platform settings** (tabs): General (platform name, logo, support email, support phone); Email (sender name, reply-to address); School defaults (grading bands, assessment structure, pass mark, remark bands, rating traits and report template style for new schools); Billing (default grace period, invoice due days, who pays gateway fees, cliff protection); Security (maximum additional admins per school, session length, two-factor login for super admins after the core).
  5. **Oversight:** Payments (all payments and webhook events), Audit log (platform-wide, filter by school, person and action), Email log (status only, filter by school and type).
  6. **Announcements** to all school admins (notice board and email), after the core.
  7. No "log in as" feature.
- **Acceptance:**
  - AC24.1 Given a school code that already exists, when creating a school, then the form shows it is taken and will not submit.
  - AC24.2 Given a valid Create school form, when submitted, then the school, its principal account and two queued emails exist, and neither email contains a password.
  - AC24.3 Given a suspended school, when any of its users logs in, then they see the paused message and no school data.
  - AC24.4 Given the school code changes from GMC to GMCE, when a student logs in with GMC, then the login fails with the generic error.
  - AC24.5 Given a colour with poor contrast, when chosen, then the form shows a readability warning and the app falls back to the platform primary for text and buttons.

### F25. School type and report card levels
- **Users:** super admin (controls); school admins (see the result).
- **Rules:**
  1. On Create school and in School detail > Features, the super admin picks a **School type**: **Nursery and Primary**, **Secondary only**, or **Nursery, Primary and Secondary**.
  2. The school type switches on the matching **report card toggles**: **Nursery report cards**, **Primary report cards**, **Secondary report cards** (Secondary covers Junior and Senior Secondary). The super admin can change each toggle on its own (for example a primary-only school with Nursery off); the school type then shows **Custom**. At least one must be on.
  3. Only the super admin can change these toggles. School admins see which levels are on but cannot change them.
  4. A level that is off disappears from menus, class creation, assessment settings, templates and dashboards for that school, and the server rejects requests for it.
  5. Turning a level off keeps its data and published reports (parents can still view and verify them); turning it back on restores it. Turning a level off with unpublished results in the active term needs a confirmation that names the affected classes.
  6. Billing is unchanged: every active enrolled student counts, whatever the level.
- **Acceptance:**
  - AC25.1 Given school type "Nursery and Primary", when the school is created, then Nursery and Primary report cards are on and Secondary is off.
  - AC25.2 Given a school admin, when they try to change a report card toggle, then it is denied.
  - AC25.3 Given Secondary report cards are off, when a request creates a JSS class, a Secondary template or a Secondary assessment structure, then it is rejected.
  - AC25.4 Given the super admin turns Nursery off for a school with published Nursery reports, when a parent opens an old Nursery report, then it still shows and verifies.
  - AC25.5 Given all three toggles are off, when saving, then the save is rejected.

### F26. Skill ratings and the Skills report card
- **Users:** school admins (configure), class teachers and assistants (enter), reviewers, parents.
- **Rules:**
  1. For a level in Skill ratings mode, school admins set up **learning areas** (for example Number work, Letter work, Phonics, Rhymes and songs, Creative arts, Social habits, Health habits, Physical development) and the **skills** under each (for example "Counts 1 to 20", "Recognises letters A to Z"). Default areas and skills are provided and editable. Areas can be assigned to classes like subjects.
  2. **Rating scale** per school, editable: name, short code and description per point. Default five points: Excellent (E), Very good (VG), Good (G), Fair (F), Needs improvement (NI). The **attention rating** (default Needs improvement) feeds F23.
  3. **Rating sheets:** one per learning area per class/arm, assigned like subjects (usually to the class teacher). Each pupil gets a rating per skill and an optional short comment per area. Missing ratings are flagged; submission needs every skill rated.
  4. Rating sheets use the same workflow, review, approval, revisions, audit, corrections and verification as score sheets.
  5. No totals, averages, grades, positions or pass mark in Skill ratings mode.
  6. **Skills report card blocks:** School header, Pupil details, Skills table (areas with their skills and ratings), Rating key, Attendance, Comments (class teacher, head's comment), Signatures, Footer with QR and report ID (always shown). Block settings include: Show area comments, Show skill descriptions, Rating display (Words, Codes, Words and codes), Group by area, Photo, Age, Next term begins. Default style: Early Years.
  7. The parent's online view of a Skills report card is low-bandwidth and lists each area with its ratings.
- **Acceptance:**
  - AC26.1 Given Nursery 2 in Skill ratings mode, when the class teacher opens the Number work sheet, then each pupil shows one rating control per skill and no score columns.
  - AC26.2 Given one skill is not rated, when submitting, then submission is blocked with the skill highlighted.
  - AC26.3 Given a published Nursery 2 Skills report card, when it is rendered, then it shows ratings and the rating key and no totals, grades or positions.
  - AC26.4 Given a school edits its rating scale after reports are published, when an old report is opened, then it shows the scale it was published with.

## 8. Workflows and state machines

**Result sheet**
```text
DRAFT -> SUBMITTED (assigned teacher; validation passes)
SUBMITTED -> RETURNED_FOR_CORRECTION (reviewer in scope; comment required)
RETURNED_FOR_CORRECTION -> RESUBMITTED (teacher; changed scores need reasons)
SUBMITTED or RESUBMITTED -> REVIEWED (reviewer in scope, not the submitter)
REVIEWED -> APPROVED (school admin, not the submitter)
APPROVED -> PUBLISHED (school admin, via class + term publication)
PUBLISHED -> reopened as a new revision in DRAFT (school admin; reason; optional correction ticket)
```
Teachers cannot edit in SUBMITTED, REVIEWED, APPROVED or PUBLISHED. Rating sheets (F26) follow the same state machine.

**Form teacher class sections:** OPEN -> SUBMITTED (form teacher) -> RETURNED (school admin; comment) -> SUBMITTED. Locked once the class is published; later changes use the correction and revision flow.

**Publication of a class:** allowed only when every subject sheet is APPROVED and the class sections required by the template are SUBMITTED.

**Report document:** VALID -> SUPERSEDED (new revision published) or REVOKED (school admin; reason).

**Correction request:** OPEN -> INVESTIGATING -> RESOLVED or REJECTED or NEEDS_MORE_INFORMATION (-> INVESTIGATING when the requester replies).

**Assessment structure and assessment mode (per level and term):** EDITABLE -> LOCKED (first score or rating saved for that level and term).

**Report card level toggle (per school):** ON -> OFF (super admin; data kept) -> ON.

**School:** ACTIVE -> SUSPENDED (super admin; reason) -> ACTIVE.

**Subscription:** FREE_PILOT or ACTIVE -> DUE (invoice issued) -> ACTIVE (paid) or OVERDUE (past due date + grace) -> SUSPENDED (super admin, manual) -> ACTIVE (paid and reactivated).

**Invoice:** UNPAID -> PAID (verified payment or manual record) or VOID (super admin).

**Email:** QUEUED -> SENT or FAILED (-> QUEUED on retry).

## 9. Data model

| Entity | Key fields | Tenant key | Notes |
|---|---|---|---|
| schools, school_features, school_levels | name, email, phone, address, city, state, country, code (unique), colour, logo, status, school_type; per level: enabled (super admin only), assessment_mode, head_title | own ID | code used in student login |
| users, school_memberships, roles, permissions, role_permissions | username, email, must_change_password, is_active, email_verified_at, is_primary (membership) | membership | staff/parent usernames unique platform-wide; student usernames unique per school |
| user_sessions | hashed refresh token, device, expires_at, revoked_at | user | supports sign out of all devices |
| account_tokens | type (activation, reset), hash, expires_at, used_at | school | single use |
| platform_settings | key, value, updated_by | platform | audited |
| academic_sessions, terms | dates, active, next_term_begins | school | term dates drive renewal |
| classes (arms), departments, subjects | level | school | |
| students, guardians, guardian_students, enrolments, student_subjects | admission_number, username, house | school | children's data |
| teacher_assignments (form_teacher flag, teaches_all_subjects flag), class_assistants, reviewer_scopes | | school | at most 2 assistants per arm |
| assessment_structures, assessment_components | level, term, locked_at; name, label, max_score, order | school | maximums add up to 100 |
| grading_scales (per level), remark_bands, pass_mark, rating_traits | | school | versioned with results |
| learning_areas, skills, rating_scales, rating_scale_points, skill_ratings, area_comments | level, order; name, code, description; attention point | school | versioned with results |
| result_sheets, scores, result_revisions, approval_actions | state, calculation_version, structure_id | school | |
| class_report_sections, student_term_entries | status; form teacher comment, principal comment, ratings, times opened, times present | school | locked on publish |
| attention_entries | student, subject, score, grade, pass_mark, revision | school | generated on publish, staff only |
| report_templates, report_documents, verification_tokens | style, block settings, template version, snapshot, hash, status | school | snapshots immutable |
| correction_requests, correction_attachments | | school | |
| notices, notice_reads, email_outbox | audience, status, type | school or platform | |
| pricing_versions, pricing_tiers | min, max, price_kobo | platform | versioned |
| school_subscriptions, invoices, payments, payment_events | status, amount_kobo, cliff_cap_applied, reference, event_id | school | event IDs unique |
| audit_events | actor, role, action, old, new, reason | school or platform | append-only |

## 10. Interfaces

### 10.1 API surface
Auth (login with identifier or school code + identifier, school lookup for login links, refresh, logout, logout all, me, activate, change password, forgot/reset for non-students; no register); platform (schools with create form, school type and report card toggles, code check, suspend/reactivate, usage, features, school admins and login support, settings, pricing with price check, subscriptions, invoices, payments, billing summary, audit log, email log, announcements after the core); school administration (settings, structure, levels, assessment modes, assessment structures, learning areas and skills, rating scale, grading, pass mark, rating traits, students incl. import, teachers, reviewers, parents and links, additional admins, login support); result sheets, scores, rating sheets and ratings, search/export, import, workflow actions, form teacher sections, principal comments, publications, reopen, revoke; Students needing attention; audit; templates and PDFs; public verification; portal; corrections; notices; email outbox; school billing and payment; payment webhook; dashboards.

### 10.2 Screens
Public: landing, login (Staff and parents, Student), school login link, activate, change password, forgot/reset password, verify, privacy, school paused. Super admin: dashboard, schools, create school (with school type and report card toggles), school detail (Overview, Features with report card levels, School admins, Subscription, Invoices, Activity), pricing, invoices, payments, audit log, email log, settings, announcements (after the core). School admin: dashboard, settings, setup (sessions and terms, levels and classes, subjects, departments, grading and pass mark, assessment mode and structure, learning areas and skills, rating scale, rating traits), class teachers and assistants, students, teachers, reviewers, parents, school admins (principal only), approvals, publish (with principal's comments), Students needing attention, notices, emails, audit, report templates, corrections, billing. Reviewer: queue, sheet, Students needing attention. Teacher: sheets, sheet grid, rating sheet, import, Students needing attention, My class (broadsheet, student entries, preview). Parent: dashboard, child, report, corrections. Student: dashboard, report. All roles: notices, profile.

## 11. Non-functional requirements

- **Security:** section 14 and the security gate.
- **Privacy:** F21; children's data handled with extra care; Nigeria Data Protection Act guidance considered, legal review flagged for after the MVP.
- **Accessibility:** WCAG 2.2 AA targets for contrast, labels, keyboard use and focus.
- **Responsiveness:** 320px minimum; tested at 360, 768 and 1440px.
- **Theming:** light, dark, system; print always light.
- **Performance:** parent report page usable on a low-cost phone on a slow mobile connection; sheet search responds instantly for 60 students.
- **Reliability:** email retries; idempotent webhooks; backup and restore test before demo.
- **Observability:** structured logs with redaction; audit timelines; email and payment event logs.
- **Localisation:** English; Naira with kobo; dates displayed in West Africa Time.

## 12. Business rules and configuration

| Setting | Who | Default | Rules |
|---|---|---|---|
| School type and report card toggles | Super admin only | Set at Create school | At least one level on; data kept when a level is turned off |
| Assessment mode per level | School admins | Nursery: Skill ratings; others: Scores | Locked per term once entries exist |
| Learning areas, skills, rating scale | School admins | Default nursery areas and skills; five-point scale; attention rating Needs improvement | Versioned with reports |
| Class teacher assistants | School admins | None | Up to 2 per arm |
| Head's title | School admins (template setting) | Head teacher (Nursery, Primary); Principal (Secondary) | |
| Assessment structure per level | School admins | CA1 20, CA2 20, Exam 60 | 1 to 8 components, maximums add up to 100, locked per term once scores exist |
| Pass mark | School admins | 40 | Whole number 1 to 99 |
| Grading bands, remark bands (per level) | School admins | Secondary A1 to F9; Nursery and Primary A to F | No overlaps or gaps |
| Rating traits and scale | School admins | Default affective and psychomotor traits, 1 to 5 | |
| Report templates | School admins | Modern | Versioned; report ID, QR, revision and date always shown |
| Additional school admins | Super admin (limit) | 2 | Principal adds them |
| Pricing table | Super admin | Basic, Standard, Premium | Volume model, versioned, no overlaps or gaps |
| Cliff protection | Super admin | On | Invoice records when the cap applied |
| Grace period | Super admin | 14 days | |
| Invoice due days | Super admin | 14 days | |
| Who pays gateway fees | Super admin | Platform | |

## 13. External services and integrations

| Service type | Needed for MVP? | Purpose | Mode |
|---|---|---|---|
| Database hosting | Yes | PostgreSQL-class database with row-level security | |
| Frontend and backend hosting | Yes | Staging and production | |
| Email provider + sending domain | Yes | Set-up, activation, reset, result and receipt emails | Free tier |
| Payment gateway (one) | Yes | School subscription payments | Test mode |
| Object storage | Decide in build (logos, signatures, stamps, attachments, PDFs) | | |
| Error monitoring | Optional | | |
| Authenticator app support (two-factor) | After the core | Super admin login | No external service needed |
| Second gateway, SMS, WhatsApp, video providers | No | Roadmap | Do not register yet |

## 14. Security requirements

- No public registration; provisioning and reset rules as in F02 and F03.
- Generic login errors that never reveal whether a school code, username or account exists.
- Server-side authorization for every request; hidden menus are not security.
- Tenant isolation in the application and the database.
- Ownership rules from section 5 proven by ID-swap tests, including form class and Students needing attention scoping.
- Published results and audit events immutable at the database level.
- No plain-text passwords anywhere; no passwords in emails; tokens out of insecure browser storage; password resets end other sessions.
- No impersonation.
- Uploaded images (logos, signatures, stamps) validated and stored privately.
- Payment amounts from server invoices; verified, idempotent webhooks.
- No sensitive data in QR codes, emails or logs.
- Full security gate (BUILD_PROMPT.md section 13) passes before production.

## 15. Delivery plan

**Pace:** there is no fixed deadline. The target is roughly two weeks, but we can finish in fewer or more days. Each day we do as much as we can, until we are tired or the session limit is reached, and every session ends cleanly: tests run, work committed, and `LOG.md` updated with the exact next step. Nothing in scope is dropped to save time; the "build after the core" items simply come last.

| Order | Milestone | Done when |
|---|---|---|
| 1 | Research, stack decisions, services | DECISIONS.md approved |
| 2 | Scaffold, staging skeleton, design updates | Health check live on staging |
| 3 | UI/UX updates, acceptance tests | Updated screens in both themes and all breakpoints; ACCEPTANCE_TESTS.md |
| 4 | Backend modules F01 to F26 | API tests green, including denials |
| 5 | Frontend shell and all screens | Component tests green; screens checked at breakpoints and themes |
| 6 | End-to-end demo flow | 38 steps pass on staging |
| 7 | Security gate | Every row PASS |
| 8 | Production deploy, docs, demo | Demo passes on production |
| 9 | Build after the core | Section 6 items, each with tests, then re-run the security gate |

## 16. Demo script

1. Super admin creates School A (Greenfield Model College) with the full Create school form: school type **Secondary only**, school code GMC, a custom colour from the picker, features, billing, and the principal's full name, username and email. The principal gets an activation email and the school email gets a set-up confirmation.
2. Super admin creates School B (Bright Stars Academy, code BSA) with school type **Nursery and Primary** (Nursery and Primary report cards on, Secondary off), Correction queue off, and a free pilot.
3. Super admin creates School C (Royal Crest Schools, code RCS) with school type **Nursery, Primary and Secondary**.
4. A School B correction request is rejected because Correction queue is off, and creating a JSS class in School B is rejected because Secondary report cards are off.
5. A register page returns not found; every role only has a login page.
6. The principal of School A activates the account and adds a vice principal as an additional school admin.
7. The principal sets the Senior Secondary assessment structure to CA1, CA2, CA3, Project and Exam (total 100), keeps CA1, CA2 and Exam for Junior Secondary, and sets the pass mark to 40.
8. The principal registers a teacher (Mathematics for JSS 1A and JSS 1B, form teacher of JSS 1A), a reviewer/HOD for Sciences, bulk-registers JSS 1A students by CSV, assigns subjects, and registers a parent linked to two children.
9. The teacher activates from the email link and logs in with their username. A student logs in on the Student tab with school code GMC, their admission number and a temporary password, and must set a new password.
10. The teacher opens the Mathematics JSS 1A sheet, searches for a student by name and enters CA and exam marks.
11. The system catches a missing and an out-of-range mark.
12. The teacher fixes them and submits.
13. The reviewer returns one score with a comment.
14. The teacher corrects the score with a reason and resubmits; the reviewer marks it reviewed.
15. As form teacher of JSS 1A, the teacher checks the class broadsheet, enters class teacher's comments, ratings and attendance numbers, previews a report card and submits the class sections.
16. The principal approves, adds the principal's comments and publishes JSS 1A.
17. A result notice appears for the parent, student and teacher; the parent receives an email.
18. Students needing attention appears: the principal filters to JSS 1A; the teacher sees only their own subjects plus all JSS 1A subjects as form teacher.
19. The branded PDF is generated in the school's chosen style and block settings.
20. The parent opens the report on a phone in dark mode and downloads the light print card.
21. The parent scans the QR code: VALID.
22. The parent submits a correction request.
23. The principal reopens, creates a new revision and republishes; Students needing attention updates.
24. Verification shows the previous version SUPERSEDED.
25. The audit timeline explains the whole history, including account creation and form teacher entries.
26. The parent tries another student's result by changing an ID: denied.
27. A School B user tries a School A student ID: denied.
28. A student opens the Student tab and sees "Ask your school admin" instead of a forgot password link; the principal issues a new temporary password and prints the slip.
29. The principal has lost their login: the super admin changes the principal's email and sends a reset link; the principal's other sessions end and the platform audit log records it.
30. School B's head teacher keeps Nursery on **Skill ratings** (default learning areas and skills, five-point scale) and Primary on **Scores** with the A to F grading bands.
31. The head teacher assigns a Primary 4A class teacher with **Teaches all subjects** and adds a **class teacher assistant**; the assistant enters some scores, but only the class teacher can submit.
32. The Nursery 2 class teacher rates each pupil's skills, writes comments and submits; the Primary 4A class teacher finishes and submits; the head teacher approves and publishes both classes.
33. A Nursery 2 parent opens the **Skills report card** (Early Years style, ratings and key, no scores or positions, "Head teacher's comment"); a Primary 4A parent opens a Score report card with A to F grades.
34. Students needing attention for School B shows Nursery 2 skills rated Needs improvement and Primary 4A scores below the pass mark.
35. The super admin edits the pricing table; the price check shows the cliff ranges; cliff protection is on; the change is in the audit log.
36. The super admin generates next-term invoices; School A's principal sees plan, billable students, amount due and renewal date.
37. The principal pays with a gateway test card; the verified webhook marks the invoice PAID, a receipt appears, and a payment notice is posted.
38. A forged webhook is rejected; the invoice status does not change.

## 17. Traceability

| Feature | Acceptance criteria | Demo steps |
|---|---|---|
| F01 | AC01.1 to AC01.2 | 1 to 4, 27 |
| F02 | AC02.1 to AC02.8 | 5, 9, 28 |
| F03 | AC03.1 to AC03.6 | 6, 8, 9, 28, 29 |
| F04 to F07 | AC04.1 to AC04.2, AC05.1 to AC05.2, AC06.1 to AC06.3, AC07.1 to AC07.2 | 4, 8, 26, 31 |
| F08 | AC08.1 to AC08.6 | 7, 10, 30 |
| F09 to F10 | AC09.1 to AC09.3, AC10.1 to AC10.3 | 10 to 16, 31, 32 |
| F11 | AC11.1 | 23 to 25, 29 |
| F12 to F14 | AC12.1 to AC12.4, AC13.1, AC14.1 | 19 to 21, 24, 33 |
| F15 | AC15.1 | 22 to 23 |
| F16 | (dashboard checks in acceptance tests) | 16, 18 |
| F17 to F18 | AC17.1 to AC17.2, AC18.1 | 1, 17, 37 |
| F19 | AC19.1 to AC19.9 | 35 to 38 |
| F20 | AC20.1 | 20 and the full flow at each size and theme |
| F21 | Security gate privacy row | 18, 21 |
| F22 | AC22.1 to AC22.4 | 15, 31, 32 |
| F23 | AC23.1 to AC23.6 | 18, 23, 34 |
| F24 | AC24.1 to AC24.5 | 1 to 3, 29 |
| F25 | AC25.1 to AC25.5 | 1 to 4 |
| F26 | AC26.1 to AC26.4 | 30, 32 to 34 |

## 18. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The build takes longer than planned | High | Medium | No fixed deadline; work session by session, end every session cleanly with tests, a commit and a LOG.md next step; build-after-the-core items come last; never cut tests or security |
| Two report card types and per-level modes add complexity | Medium | Medium | One block engine for both card types; one workflow for score and rating sheets; tests per mode |
| Free-tier email limit hit when emailing a whole school | Medium | Medium | Outbox stays queued and retries; small demo school; paid plan noted for pilots |
| Free hosting sleeps or pauses during the demo | Medium | High | Demo-day warm-up checklist |
| PDF rendering heavy on free hosting | Medium | Medium | Decide approach in the PDF decision round; test bulk generation early |
| Default prices create cliffs (251 to 499 students, 601 to 1,000 students) | High | Medium | Cliff protection on by default; price check in the editor; validate prices in school interviews |
| Changing a school code breaks students' saved login links | Medium | Low | Warning before saving; audited; school admins told by notice |
| Children's data exposure | Low | High | Isolation, ownership tests, privacy basics, staff-only attention list, no real data |

## 19. Open questions and decisions

| Question | Decision | Status |
|---|---|---|
| Volume or graduated pricing? | Volume only, with cliff protection on by default | Decided |
| Which plan owns exactly 1,000 students? | Standard (500 to 1,000); Premium from 1,001 | Decided |
| Who absorbs gateway fees? | Platform (setting) | Defaulted |
| Students added mid-term: bill now or next term? | Next term, with optional adjustment invoice | Defaulted |
| How do students identify their school at login? | School code field on the Student tab, pre-filled from the school's login link | Decided |
| Can the super admin reset everyone's password? | No, school admins only | Decided |
| Below-pass list contents | Failed subjects and an overall-average flag | Decided |
| Can form teachers post notices? | Not in the MVP | Decided |
| More than one admin per school? | Yes, principal adds up to the platform limit (default 2) | Decided |
| Nursery report cards | In the MVP: each school chooses Scores or Skill ratings per level | Decided |
| Who switches levels on and off? | Super admin only, through school type and report card toggles | Decided |
| Primary default grading | A to F | Decided |
| One teacher for every subject in a class? | Yes, "Teaches all subjects", plus up to 2 class teacher assistants | Decided |
| Deadline | Flexible, session by session, roughly two weeks | Decided |
| Store PDFs or regenerate from snapshots? | Decide in the file storage round | Open |

## 20. Glossary

- **Arm:** a parallel stream of a class (JSS 1A, JSS 1B).
- **CA:** continuous assessment.
- **Assessment structure:** the list of score components (CAs, projects, exam) and their maximum scores for a level.
- **Broadsheet:** a table of every student against every subject for one class.
- **Form teacher / class teacher:** the teacher responsible for one class arm, who writes the class teacher's comment. Called class teacher in Nursery and Primary.
- **Class teacher assistant:** a teacher who helps a class teacher enter scores, ratings and comments, but cannot submit.
- **Learning area:** a nursery-style subject such as Number work or Phonics, made up of skills.
- **Skill rating:** a rating (for example Excellent or Needs improvement) given to a pupil for one skill, used instead of scores.
- **School type:** Nursery and Primary, Secondary only, or Nursery, Primary and Secondary; sets which report cards a school gets.
- **HOD:** head of department.
- **Affective and psychomotor domains:** behaviour and skills ratings on Nigerian report cards.
- **Pass mark:** the score below which a subject result counts as failed (default 40).
- **School code:** a short unique code for each school that students type when they log in.
- **Kobo:** one hundredth of a Naira.
- **Term:** one of three school terms in a Nigerian academic session.
- **Volume pricing:** every student is charged at the price of the plan the school's total student count falls into.
- **Cliff protection:** a cap so a school never pays more than the smallest possible bill on a higher plan.
