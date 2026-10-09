# Revised MVP: SchoolFlow Result Portal (School Results Trust Chain)

> **Update (October 2026):** this version adds school administration and account provisioning (student and teacher registration with class and subject assignment, admin-created accounts for every role, guardian-to-ward linking), a login-only access model with no public registration, a notice board with email notifications on result publication, and a responsive SaaS-style dashboard with a collapsible sidebar and dark/light mode. See sections 2, 3, 14 and 15.
>
> **Update 2:** this version also adds per-school subscription billing: a per-student, per-term pricing table that the super admin edits, termly invoices, online payment by the school admin/principal, and a billing panel showing the school's plan, next renewal date and paid invoices. See section 16.
>
> **Update 3 (7 October 2026):** the product is now called **SchoolFlow Result Portal** (planning name ResultChain). This version adds username login for everyone and a school code on the student login; password reset rules (no self-service for students, the super admin resets school admins); additional school admins such as a vice principal; assessment structures with any number of CAs per level; score sheet search and filters; form teacher tools; a Students needing attention list after publication; expanded super admin functions, platform settings and a full Create school form with a colour picker and set-up emails; more report template styles and block settings. Graduated pricing is removed: billing is volume pricing with optional cliff protection. See sections 2, 4, 5, 8, 16, 17, 18, 19 and 20.
>
> **Update 4 (7 October 2026):** nursery and primary report cards are now in the MVP. The super admin sets each school's type (Nursery and Primary, Secondary only, or Nursery, Primary and Secondary) and switches report cards on or off per level. Each school chooses Scores or Skill ratings for each level. Primary grading defaults to A to F. A class teacher can be given every subject of a class in one step, with up to 2 class teacher assistants. The pace is now flexible: no fixed 14 days, we work session by session. Items that were "if time allows" are now "build after the core"; nothing is dropped. See sections 1, 3, 4, 8, 17, 18, 19, 20, 21 and the delivery plan.

## Decision

**Yes, you can implement the tutor’s feedback while delivering more than a result-only page.** The correct compromise is a **results-first school platform shell**:

- The results workflow remains the product’s centre of gravity.
- A slim multi-tenant school platform surrounds it.
- The MVP includes useful teacher, reviewer, school-head, parent, and student experiences.
- The platform's own subscription billing (schools paying for SchoolFlow Result Portal) is part of the MVP.
- School fees collected from parents, attendance, LMS, CBT, transport, hostel, payroll, and live classes remain in the roadmap rather than being built now.

This gives you a broader product to demonstrate without turning the project into several unfinished products.

## The startup product

### Working positioning

> **A trusted results-release platform for Nigerian schools: enter scores once, catch errors before publication, obtain the right approvals, issue each school’s own report card, and give parents a verifiable record with a complete correction history.**

Product name: **SchoolFlow Result Portal**, the first module of the wider SchoolFlow school management platform. The promise should remain narrow and clear.

### The primary differentiator: Audit-ready Result Trust Chain

Do not claim that no result portal anywhere has ever implemented these ideas. That claim would be difficult to prove and is not necessary. The defensible claim is:

> **In the public materials reviewed for SAFSIMS, SchoolShell, Smart School Manager, SchoolHub, ExcelMind, Edves, SkoolDrive, SchoolsFocus, and Fedena, I did not find a clearly documented end-to-end combination of immutable published result snapshots, old/new score history, controlled reopen and reapproval, parent verification, and a correction ticket linked to the revised result.**

That is a strong and honest market position.

The product promise is that a school can answer all of these questions:

1. Who entered the score?
2. Who changed it?
3. What was the old value and the new value?
4. Why was it changed?
5. Who reviewed and approved the result?
6. Which version did the parent receive?
7. Was the result later corrected or revoked?
8. Is the PDF or screenshot the parent is holding genuine?

This solves a real problem. Nigerian research on result-processing systems has reported duplicated work, slow processing, calculation errors, possible tampering or fake results, late release, and inefficient retrieval [1]. WAEC’s own public processes also emphasise controlled marking, correct transcription, formal complaint routes, and result verification [2] [3]. Your product applies the same trust principles to ordinary school term results without pretending to be an official WAEC system.

## Full MVP scope

### 1. Slim multi-tenant school platform

Include the platform foundation required to make the product sellable to more than one school:

- Super-admin login
- Create and manage schools
- School branding and details: name, email, phone, address, city, state, country, school code, levels, logo and a freely chosen school colour (see section 19)
- One active academic session and term per demo school
- School-specific grading configuration
- School-specific report-card template configuration
- Feature flags for the modules that actually exist in the MVP
- School-level data isolation
- Seed data for at least two schools

Each school also has a **school type** and **report card toggles per level** (Nursery, Primary, Secondary), controlled only by the super admin (see section 21).

The MVP feature flags should include only:

- `results`
- `report_cards`
- `parent_portal`
- `correction_queue`
- `notice_board`
- `email_notifications`

The server must reject requests to disabled modules. Hiding a menu item is not sufficient.

### 2. Authentication, roles and account provisioning

#### Login only, no public registration

There is **no public sign-up or register route** anywhere in the product. Every role has a login screen only. Accounts are created top-down:

```text
Super admin
  -> creates schools
  -> creates the School Administrator/Principal account for each school

School Administrator/Principal
  -> creates Reviewer/HOD accounts
  -> creates Teacher accounts
  -> creates Student accounts
  -> creates Parent/Guardian accounts and links each one to their ward(s)
```

- Only the super admin can create a School Administrator/Principal. A school admin cannot create another school admin or a super admin.
- A school admin can only create users inside their own school.
- Super admin accounts are created by a secure seed/CLI command, never through the web UI.

#### Issuing login details safely

The school admin "assigns login details", but the system must never email or store plain-text passwords. Use one of these, per user:

- **Users with an email address (staff, most parents):** the system emails a one-time activation link. The user sets their own password, which also verifies their email address.
- **Users without an email address (younger students, some parents):** the admin generates a one-time temporary password, shown once on screen and on a printable credential slip. The account is flagged `must_change_password`, and the user must set a new password at first login.

The admin can resend an activation link, reset a user's password (generating a new one-time credential), deactivate an account, and reactivate it. Every one of these actions goes into the audit log.

#### Usernames and the login page

- Every account has a **username**, suggested from the person's name (for example `ngozi.okeke`) and editable. Staff, parent and super admin usernames are unique across the platform. Student usernames and admission numbers are unique within their school.
- The login page has two tabs:
  - **Staff and parents** (super admin, school admins, reviewers/HODs, teachers, parents): **Email or username**, then **Password**.
  - **Student**: **School code**, then **Username or admission number**, then **Password**. The school code tells the system which school the student belongs to, because two schools can use the same admission number.
- Each school also gets its own login link (for example `/login/GMC`) that opens the Student tab with the school code already filled in and shows the school's name and logo.
- Every failed login shows the same message, so nobody can find out whether a school code, username or account exists.

#### Password resets

- **Forgot password** (self-service by email) is available to everyone except students, as long as the account has a verified email address. Accounts without email are told to ask their school admin.
- **Students cannot reset their own password.** The Student tab shows "Forgot your password? Ask your school admin for a new one." The school admin issues a new temporary password and a printable slip.
- **School admins** reset logins for their reviewers, teachers, parents and students.
- **The super admin resets school admins only** (the principal and any additional admins), for example when a principal has lost their login. The super admin can change the admin's email, send a reset link, issue a temporary password with a printable slip, sign the admin out of all devices, and make another admin the principal. The super admin cannot reset teachers, parents or students.
- A reset signs the user out of every other device and sends a "your password was changed" email when the account has an email. Every reset is audited.
- Nobody, including the super admin, can log in as another user.

#### Additional school admins

- The principal (the school admin created by the super admin) can add **additional school admins**, such as a vice principal, up to a limit the super admin sets (default 2).
- Additional admins can do everything the principal can, except add, remove or reset other school admins.

#### Roles

Implement these roles:

| Role | MVP permissions |
|---|---|
| Super admin | Create schools, create and manage each school's administrator/principal account, reset school admin logins, manage platform settings, manage school settings and feature flags, manage the pricing table, enable or disable billing per school, generate invoices, record manual payments, view platform revenue |
| School administrator/principal | Add additional school admins; configure the school; register students, teachers, reviewers/HODs and parents/guardians and issue their login details; assign students to classes and subjects; assign teachers to classes and subjects; link guardians to wards; approve and publish results; post notices; manage corrections; view audit logs; view the school's plan, renewal date and invoices, and pay invoices online |
| Additional school admin (for example vice principal) | Everything the principal can do, except add, remove or reset other school admins |
| Reviewer or head of department | Review submitted results, return them with comments, mark them reviewed, see Students needing attention within their scope |
| Teacher | Enter scores for assigned subjects/classes (one sheet per subject per class, with search), submit drafts, respond to returned results, see Students needing attention for their own subjects. As **form teacher** of one class: class broadsheet, class teacher's comments, affective and psychomotor ratings, attendance numbers, report card preview, and Students needing attention for the whole class |
| Parent/guardian | View only linked children’s published results, download reports, submit correction requests |
| Student | View only their own published results, if student login is included |

The access rule must be enforced in the API. A teacher must not be able to approve their own results by changing a request parameter.

### 3. School administration: setup, registration and assignment

Build only the records needed for results, but make them fully manageable by the school admin/principal:

**School structure**
- Academic sessions and terms (one active session and term at a time, with a "next term begins" date)
- School levels (Nursery, Primary, Junior Secondary, Senior Secondary), limited to the levels the super admin has switched on for the school; each class belongs to a level
- Classes and arms (for example JSS 1A, JSS 1B, SS 2 Science)
- Subjects (with optional departments, so HODs can be scoped to their department)

**Student registration**
- Register a student one at a time (name, admission number, username, gender, date of birth, class/arm, optional house, optional photo).
- Bulk register students by CSV, reusing the same preview-then-commit import pattern as score import (validate every row, nothing is saved if any row fails).
- Assign each student to a class/arm for the active session (enrolment).
- Assign each student's subjects. Default: all subjects offered by their class. The admin can adjust per student (for example SS science vs arts electives).
- Promote or move a student between arms, with history kept.

**Teacher registration and assignment**
- Register a teacher (name, username, email, phone, staff ID).
- Assign the teacher one or more subject + class/arm pairs (for example Mathematics for JSS 1A and JSS 1B).
- Optionally make a teacher the form/class teacher of an arm (for class-teacher comments on the report card).
- **Class teacher in one step:** tick "Teaches all subjects" to give a teacher every subject (or learning area) of an arm and make them its class teacher. This is how most nursery and primary classes work.
- **Class teacher assistants:** add up to 2 assistants to an arm. They can enter scores, ratings, comments and attendance for that class, but only the class teacher can submit.
- A teacher only sees score sheets for their own assignments.

**Reviewer/HOD registration and assignment**
- Register a reviewer/HOD and scope them to a department or a list of subjects/classes.
- A reviewer only sees submitted sheets inside their scope.

**Parent/guardian registration and ward linking**
- Register a parent/guardian (name, username, phone, email if available, relationship).
- Link the guardian to one or more students (their wards) at creation time, and add or remove links later.
- One student can have more than one guardian.
- A guardian's dashboard shows only their linked wards' published results, notices and correction requests. This is enforced in the API, not just hidden in the UI.

Do not build admissions, school fee collection from parents, attendance, transport, hostel, payroll, timetable, or accounting in this MVP.

### 4. Nigeria-first result engine

The result engine should support:

- **Assessment mode per level:** each school chooses **Scores** or **Skill ratings** (section 21) for each of its levels. Defaults: Nursery uses Skill ratings, the other levels use Scores. Everything below applies to levels in Scores mode.

- **Assessment structure per level:** the school sets any number of components from 1 to 8 (for example CA1, CA2, CA3, CA4, Assignment, Project, Test, Practical, Exam), each with a name, a short column label and a maximum score. The maximums must add up to exactly 100.
- Different levels can use different structures (for example Primary: CA1, CA2, Exam; Senior Secondary: CA1, CA2, CA3, Project, Exam). New schools start from the platform default (CA1 20, CA2 20, Exam 60).
- Once any score exists for a term at a level, that structure is locked for the term; changes apply from the next term. The structure used is stored with each result.
- A school pass mark (default 40), used for the Students needing attention list
- School-editable grading bands
- Grading bands per level: A1 to F9 labels and descriptions as sensible defaults for Junior and Senior Secondary, and A to F for Primary (and Nursery when it uses Scores): A 70 to 100 Excellent, B 60 to 69 Very good, C 50 to 59 Good, D 45 to 49 Fair, E 40 to 44 Pass, F 0 to 39 Fail
- Raw score storage separate from derived total and grade
- Subject totals
- Subject averages
- Class averages
- Overall averages
- Subject positions
- Overall positions with tie handling
- Teacher remarks
- School-configurable remarks or comment bands
- Affective and psychomotor ratings on school-editable traits with a 1 to 5 scale
- Missing-score flags
- Out-of-range score validation
- Duplicate student/subject/term detection
- Calculation version stored with each result

Do not hard-code a supposedly official WAEC percentage mapping. The reviewed official WAEC pages confirm grading terminology and verification processes but did not provide a percentage-to-grade table in the pages reviewed. Store the school’s grading bands as configuration and label A1–F9 as defaults, not as an immutable WAEC rule [4].

### 5. Score entry and controlled spreadsheet import

The teacher experience should be phone-friendly and spreadsheet-friendly.

#### Manual entry

- Each teacher has one score sheet per subject per class/arm they are assigned (for example "Mathematics, JSS 1A" and "Mathematics, JSS 1B"). The My score sheets page groups sheets by class and filters by class, subject and status.
- Inside a sheet the teacher can search by name or admission number to jump to a student, and filter to All, Missing or Errors.
- Scores appear in a grid whose columns come from the level's assessment structure.
- The grid shows student names, admission numbers, each component, total, grade, and remark. On phones each student is a card.
- Invalid entries are highlighted immediately.
- Missing scores are visible before submission.
- Drafts can be saved.
- A teacher can submit only when required validation passes or an authorised exception is recorded.

#### CSV import

Provide a downloadable template and an import preview:

- Validate every row before writing data.
- Identify unknown students.
- Identify duplicate rows.
- Identify scores outside the allowed range.
- Identify missing required fields.
- Show row-level error messages.
- Allow the teacher to download the error list.
- Do not partially commit a failed import.
- The teacher can also export the sheet as CSV.

This addresses the data-quality problems documented in Nigerian education data collection, where Excel/Access capture and misspelled coded values required later cleaning [5].

### 6. Result approval workflow

Use this state machine:

```text
DRAFT
  -> SUBMITTED
  -> RETURNED_FOR_CORRECTION
  -> RESUBMITTED
  -> REVIEWED
  -> APPROVED
  -> PUBLISHED
```

Rules:

- Teachers can create and submit drafts.
- Reviewers can return results with a comment.
- Reviewers cannot alter scores silently.
- The principal or authorised administrator approves publication.
- Parents and students see only `PUBLISHED` results.
- Submitted and approved results are locked against ordinary teacher editing.
- Reopening requires a reason.
- Reopening creates a new revision; it does not overwrite the published snapshot.
- A revised result must pass through review and approval again.

### 7. Immutable audit history

Every score or result configuration change should record:

- School ID
- Entity and entity ID
- Student and subject where relevant
- Actor
- Role at the time of action
- Timestamp
- Old value
- New value
- Reason
- Revision ID
- IP/device metadata only if appropriate and privacy-reviewed

The administrator should see a readable timeline:

```text
12 Oct 2026, 10:14 - Teacher A entered Mathematics exam score: 62
12 Oct 2026, 10:18 - Teacher A changed Mathematics exam score: 62 → 72
Reason: corrected from marked script
12 Oct 2026, 13:05 - Reviewer B returned result
Comment: verify Mathematics exam score
13 Oct 2026, 09:30 - Principal C approved revision 2
13 Oct 2026, 09:31 - Result published
```

The published version must be read-only. A correction must create a new version.

### 8. Report-card designer

Keep the tutor’s constrained block-editor recommendation, but make it useful:

- School logo and name
- Student details
- Class, arm, session, and term
- Subject table
- CA/exam/component breakdown
- Total, grade, and remark
- Overall average and position
- Class average
- Attendance placeholder for future integration
- Affective and psychomotor domains
- Teacher comment
- Principal/head signature block
- Footer and school contact details
- QR code/report ID

**Report card types.** Levels in Scores mode use the **Score report card** described here. Levels in Skill ratings mode use the **Skills report card** (section 21). Each level has its own template, and a **Head's title** setting (Head teacher by default for Nursery and Primary, Principal for Secondary) labels the head's comment and signature.

**Styles.** Each style is a preset over the same blocks, so adding styles is cheap:
- In the core build: **Modern** (default), **Classic**, **Compact** (fits 15 or more subjects on one page) and **Early Years** (larger type and a friendly layout for Nursery and lower Primary, the default for Skills report cards).
- After the core: **Bold Banner**, **Ink Saver** (black and white, for cheap printers) and **Cumulative** (third term, with first, second and third term columns, annual average and promotion result).

**Block settings** (switches and simple choices per block):
- School header: logo, logo position, motto, address, phone and email, report title, session and term line.
- Student details: photo, admission number, gender, age, date of birth, class and arm, house, form teacher's name.
- Subject table: a switch for each assessment column, total, grade, remark, position in each subject, class average, highest in class, lowest in class, subject teacher's initials, highlight scores below pass mark, row shading.
- Summary: total score, total average, overall class position (optional), number in class, class average, number of subjects, promotion result.
- Affective and psychomotor: each domain, rating key, side-by-side or stacked layout.
- Attendance: times school opened, times present, times absent.
- Comments: form teacher's comment, principal's comment, show names.
- Signatures: form teacher signature line, principal signature image, school stamp image, date line.
- Footer: QR position, next term begins, school contact line, custom note. The report ID, revision, publication date and QR code are always shown.

**Template settings:** paper size, font, text size, accent colour, borders, logo watermark, grading key and margins.

The template should save as versioned JSON. Do not build unrestricted drag-and-drop or pixel-level layout in the MVP.

### 9. PDF generation and authenticity verification

Each published report card should contain:

- A human-readable report ID
- Student-specific report reference
- Term and academic session
- QR code or short verification code
- School branding
- Publication date
- Revision number

The verification page should show:

- School name
- Student name or masked student name
- Session and term
- Report status: valid, revoked, or superseded
- Published revision
- Publication date
- Verification warning if the PDF is no longer the latest version

Use a signed token or server-side lookup. Do not put sensitive student data directly inside the QR code. A QR code proves that the reference resolves to a server record; it does not by itself prove that every score is correct.

### 10. Parent and student portal

The portal makes the product more than a results-entry system:

- Guardian linked to one or more children
- Parent sees only linked children
- Published results only
- Download PDF
- View report online in a low-bandwidth layout
- See report status and revision
- Verify the report ID or QR code
- Submit a correction request
- See correction-request status
- Receive an email and a notice-board notification when a report is published (see section 14)

Do not require a native mobile app. Use responsive web screens and design the parent page to work well on low-cost phones.

### 11. Correction and dispute queue

This is the second major product feature after the trust chain.

A parent, teacher, or reviewer can create a correction request containing:

- Student
- Term/session
- Subject or report section
- Issue type
- Explanation
- Optional evidence or attachment
- Requester
- Date submitted
- Status
- Administrator response
- Resolution date

Statuses:

```text
OPEN -> INVESTIGATING -> RESOLVED
                    -> REJECTED
                    -> NEEDS_MORE_INFORMATION
```

If the administrator reopens a published result because of the ticket, the resulting new revision must link back to that ticket. This turns informal WhatsApp complaints into a traceable school process without allowing parents to edit grades.

### 12. Results-week exception dashboard

Keep analytics practical rather than predictive:

- Results awaiting teacher submission
- Results awaiting review
- Results awaiting principal approval
- Missing-score count
- Invalid-score count
- Subject averages
- Class averages
- Pass rate
- Term-over-term average trend
- Students with unusual score changes
- Correction requests still open
- Form teacher class sections still open
- A Students needing attention card after publication (see section 18)

This helps the school head focus on exceptions before publication. Do not build AI predictions or automated promotion decisions in the MVP.

### 13. Privacy-by-design basics

The NDPC’s 2025 guidance is directly relevant because educational services process pupil/student records and children require additional safeguards. The guidance identifies DPIA-sensitive education processing and expects access, correction, privacy notices, and breach-readiness controls [6].

Include:

- Plain-language privacy notice
- Guardian relationship field
- Consent/approval status field where required by the school’s legal basis
- Least-privilege roles
- School isolation tests
- Audit logs
- No student data in QR payloads
- No real student data in Claude prompts or development screenshots
- Data export/delete design notes
- Retention policy placeholder
- Report revocation capability
- Attachment file-type and size restrictions

This is an MVP implementation of privacy-by-design, not a claim that the product is legally compliant without professional review.

### 14. Notice board and email notifications

#### Notice board (in-app)

- Every logged-in user has a notice board on their dashboard, with an unread count badge in the header.
- The school admin/principal can post notices with a title, message, optional pin, and an audience: everyone in the school, or selected roles (teachers, reviewers, parents, students), optionally narrowed to specific classes.
- Users see only notices addressed to them, within their own school.
- Notices can be marked as read. The admin can edit or archive a notice; edits are recorded in the audit log.
- When results are published, the system **automatically posts a notice** (for example: "First Term 2026/2027 results for JSS 1 are now available") to the affected students, their guardians, and the relevant teachers and reviewers.

#### Email notifications

- When results are published, the system sends an email to everyone affected: each linked guardian, each student who has an email address, and the staff involved.
- Emails never contain scores or report cards. They say the result is ready and link to the login page.
- Emails are queued in an outbox table and sent in the background, so publishing a class is not slowed down and a failed email can be retried. Each email's status (queued, sent, failed) is visible to the admin.
- School set-up, account activation (with the username, and the school code for school admins), password reset, password changed and notice emails use the same email service. No email ever contains a password.
- Users without an email address still see the notice on their dashboard.
- Note for scale: free email tiers have daily sending limits. The demo uses a small seeded school; real schools will need a paid plan or batched sending, and this is noted in the roadmap.

### 15. Dashboard experience, responsiveness and themes

- **SaaS-style dashboard layout** for every role: a sidebar with icons and labels, a top header (school name/logo, notice bell with unread count, theme toggle, profile menu), and a main content area.
- **Collapsible sidebar:** an expand/collapse toggle icon shrinks the sidebar to icons only (with tooltips) and expands it again. The choice is remembered on that device. On phones, the sidebar becomes a slide-out drawer opened from a menu icon.
- Each role sees only the menu items for features that are enabled for their school and permitted for their role.
- **100% responsive** across phones (from 320px wide), tablets, laptops and large desktops. Wide tables (score grid, student lists) scroll inside their own container or switch to a card layout on small screens, so the page never scrolls sideways.
- **Dark and light mode toggle**, plus a "follow system setting" option. Every screen, chart, table, status badge, form state and the parent report view is designed and tested in both modes, with readable contrast in each.
- School branding (logo and primary colour) works in both modes.
- **Printed and PDF report cards always use the light, print-friendly design**, regardless of the user's theme.

### 16. School subscriptions and billing

SchoolFlow Result Portal charges each school per registered student, per term. The super admin controls everything about pricing. The school admin/principal sees their plan, their next renewal, and pays online.

#### Pricing table (super admin)

- The super admin creates and edits pricing tiers from the dashboard. Each tier has a name, a minimum and maximum number of students, and a price per student per term in Naira.
- Starting defaults (all editable):

| Plan | Students | Price per student per term |
|---|---|---|
| Basic | 1 to 499 | NGN 1,000 |
| Standard | 500 to 1,000 | NGN 500 |
| Premium | 1,001 and above | NGN 300 |

- Tier boundaries must not overlap or leave gaps. The system validates this before saving. (In the original example, "500 to 1000" and "1000+" both include 1,000, so the defaults above make 1,000 belong to Standard. The super admin can change this.)
- Pricing changes are **versioned**. Editing the table creates a new version that applies to invoices generated after the change. Invoices already issued keep the price they were issued with.
- Every pricing change is recorded in the audit log.
- **Pricing model: volume.** The school's number of billable students decides its plan, and every student is charged that plan's price. The school collects from its students however it likes and pays the platform. Graduated pricing is not used.
- **Cliff protection** (on by default, the super admin can switch it off): volume pricing can make a smaller school pay more than a bigger one. With the defaults, a school with 499 students would pay NGN 499,000 while a school with 500 pays NGN 250,000. With cliff protection, a school never pays more than the smallest possible bill on a higher plan, so the 499-student school pays NGN 250,000. The invoice shows when the cap applied.
- **Price check:** the pricing editor warns about student ranges where a bigger school would pay less. With the default prices it flags 251 to 499 students and 601 to 1,000 students (for example 642 students would pay NGN 321,000, more than the NGN 300,300 a 1,001-student school pays), so the super admin can adjust the prices.

#### Subscriptions per school (super admin)

- The super admin can switch billing on or off for each school, for example to give a pilot school a free term.
- Each school has a subscription status: `FREE_PILOT`, `ACTIVE`, `DUE`, `OVERDUE`, `SUSPENDED`.
- The super admin sets a grace period after the due date. When a school becomes overdue, the school admin sees a clear warning. Suspending a school is a manual super admin decision, never automatic in the MVP, and suspension never deletes data.

#### Invoices

- One invoice per school per term. The super admin generates invoices for one school or for all billable schools at once, usually just before the term starts.
- Each invoice stores a snapshot: term, billable student count, plan and tier, price per student, pricing version, amount, due date and status (`UNPAID`, `PAID`, `VOID`).
- Billable students are the active students enrolled in the school for that term at the time the invoice is generated. Students added later in the term are not billed automatically in the MVP. The super admin can issue an adjustment invoice if needed.
- All money is stored as whole kobo (integers), never as decimals.

#### School admin/principal billing panel

- A billing card on the dashboard shows: current plan, number of billable students, price per student, amount due, due date, next renewal date (the start of the next term) and subscription status.
- A projected cost for the next term, based on the current number of active students and the current pricing table, so the principal can see if they will move to a different plan.
- A **Pay now** button for unpaid invoices.
- Invoice history with each invoice marked **PAID** (with payment date and reference) or **UNPAID**, and a downloadable receipt for paid invoices.
- When a payment succeeds, a notice appears on the school admin's notice board and a receipt email is sent.

#### Online payment

- Payments go through a Nigerian payment gateway (Paystack is the likely choice; confirm during the stack discussion). The MVP runs in **test mode only**. Going live requires the gateway's business compliance review and is a post-MVP step.
- Each invoice is a one-time payment, because the amount changes every term with the student count. The gateway's fixed-amount subscription plans are not a good fit.
- The amount is always taken from the invoice on the server, never from the browser.
- An invoice is marked paid **only** after the server confirms the payment through a signature-verified webhook and a server-side transaction check. The browser redirect after payment is never trusted on its own.
- Webhook handling is idempotent: the same event received twice cannot mark an invoice paid twice or create duplicate receipts.
- The super admin can also record a manual payment (for example a bank transfer) with a reference and note. This is audited.

#### Super admin billing dashboard

- List of schools with plan, student count, subscription status, current invoice and amount.
- Totals for the term: invoiced, paid, outstanding.
- Payment history across all schools.

### 17. Form teacher tools

A teacher who is form teacher of a class arm (called class teacher in Nursery and Primary) gets a **My class** area. Class teacher assistants see it too and can enter, but not submit:

- **Class broadsheet** (read-only): every student against every subject, with each subject sheet's status, so missing results are visible early.
- **Class teacher's comment** per student, with suggested comments from the remark bands (editable, up to 300 characters).
- **Affective and psychomotor ratings** per student on the school's traits and 1 to 5 scale.
- **Attendance numbers** for the report card: times school opened (once for the class) and times present per student; times absent is calculated. This is not an attendance register.
- **Report card preview** for any student in the class, marked "Preview, not published".
- **Submit class sections:** locks them for the form teacher. School admins can return them with a comment. Publishing a class is blocked until the sections shown on the school's template are submitted.
- The principal's comment for each student is entered by a school admin on the publish screen.

### 18. Students needing attention

- Generated automatically when a class's results are published, and updated when a corrected revision is republished. Only published results count.
- The school sets a pass mark (default 40).
- **By subject:** every subject score below the pass mark, with student, admission number, class/arm, subject, score, grade and subject teacher.
- **By student:** each student with failed subjects or an overall average below the pass mark, showing the number of failed subjects, the overall average and an "Average below pass mark" flag.
- Filters: session, term, class, arm, subject and (school admins only) teacher. Export to CSV and print.
- Who sees what:
  - Principal and school admins: every class.
  - Reviewer/HOD: their department or scope.
  - Subject teacher: only their subjects in the classes they teach.
  - Form teacher: every subject for their form class, plus their own subjects elsewhere.
- Dashboard cards for the principal and teachers link to the list.
- Parents and students never see it.
- For levels using Skill ratings, the list shows skills rated at or below the school's attention rating (default "Needs improvement") instead of scores below the pass mark, with a **By learning area** view.

### 19. Super admin: platform administration and settings

**Create school form**
- School details: school name, school email, phone number, address, city, state (a dropdown of the 36 states and FCT when the country is Nigeria), country (default Nigeria), school code (suggested from the school's initials, unique, 3 to 10 letters or numbers), school type and report card toggles (section 21), school colour (a full colour picker with a hex field, not a fixed list, with a live preview in light and dark and a warning if text on it would be hard to read), and an optional logo.
- Features: the six feature switches.
- Billing: billing on, or free pilot.
- Principal account: full name, username and email.
- When the school is created, the principal receives a welcome email with an activation link, their username and the school code, and the school email receives a set-up confirmation with the school code, the school's login link and support contacts. No password is sent by email.

**Schools**
- Search and filter schools; edit school details; see usage (students, staff, parents, results published, last activity).
- Change the school code, with a warning that students must use the new code.
- Suspend or reactivate a school with a reason. Users of a suspended school see "Your school's access is paused. Contact your school admin." Data is kept.
- Resend the set-up email.
- School admins tab: the principal and additional admins, with resend activation, change email, send reset link, issue temporary password, sign out of all devices, deactivate or reactivate, and make another admin the principal.

**Platform settings**
- General: platform name, logo, support email and phone.
- Email: sender name and reply-to address.
- School defaults: grading bands, assessment structure, pass mark, remark bands, rating traits and report template style for new schools.
- Billing: default grace period, invoice due days, who pays gateway fees, cliff protection.
- Security: maximum additional admins per school, session length, two-factor login for super admins (after the core).

**Oversight**
- Payments across all schools, a platform-wide audit log, and an email log showing delivery status only.

### 20. Build after the core

These are agreed and will be built. They simply come after everything else works, with their own tests:
- Report template styles Bold Banner, Ink Saver and Cumulative.
- Platform announcements from the super admin to all school admins.
- Two-factor login for super admin accounts.

### 21. Nursery and primary report cards

**School type and report card toggles (super admin only)**
- When creating a school (and later in School detail > Features), the super admin picks a school type:
  1. **Nursery and Primary**
  2. **Secondary only**
  3. **Nursery, Primary and Secondary**
- The school type switches on the matching toggles: **Nursery report cards**, **Primary report cards** and **Secondary report cards** (Secondary covers JSS and SSS). The super admin can change any toggle on its own, for example a primary-only school with Nursery off; the type then shows "Custom". At least one toggle must stay on.
- School admins can see which levels are on but cannot change them. A level that is off disappears from that school's menus, classes, settings and templates, and the server rejects requests for it. Turning a level off keeps its data and published reports.
- Billing still counts every active student, whatever the level.

**Each school chooses how each level is assessed**
- For every level that is on, the school admin chooses **Scores** (CAs and exam out of 100, totals, grades, positions, as in section 4) or **Skill ratings**. Defaults: Nursery on Skill ratings, Primary and Secondary on Scores. The choice is locked for a term once entries exist.

**What goes with Skill ratings**
- **Learning areas and skills:** for example Number work ("Counts 1 to 20", "Adds numbers within 10"), Letter work, Phonics, Rhymes and songs, Creative arts, Social habits, Health habits, Physical development. Defaults are provided; the school edits them and assigns areas to classes like subjects.
- **Rating scale:** default Excellent (E), Very good (VG), Good (G), Fair (F), Needs improvement (NI), each with a description; the school can edit it. The attention rating (default Needs improvement) feeds Students needing attention.
- **Rating sheets:** one per learning area per class, usually all assigned to the class teacher. Each pupil gets a rating for every skill and an optional comment per area. Submission needs every skill rated.
- Rating sheets use the same review, approval, publication, revisions, audit, corrections and QR verification as score sheets.
- No totals, averages, grades, positions or pass mark.
- **Skills report card:** school header, pupil details, skills table grouped by area, rating key, attendance, class teacher's and head's comments, signatures, and the footer with QR and report ID. Default style: Early Years.

**What goes with Scores in Nursery and Primary**
- The same score engine as Secondary, with A to F grading bands by default and the Head teacher title on the report card.

## What should not be built in the MVP

Keep these in the README roadmap:

- School fee collection from parents (fee items, part payments, bursar tools)
- Live (production) payment processing; the MVP's subscription billing runs in gateway test mode
- A second payment gateway such as Flutterwave
- Attendance
- Admissions
- Timetables
- LMS courses and assignments
- CBT
- Google Meet, Zoom, Agora, and Jitsi integrations
- Hostel management
- Transport and GPS
- Payroll
- Library and inventory
- Full SMS/WhatsApp production integrations
- True offline sync with conflict resolution
- Predictive analytics
- AI-generated rankings or promotion decisions
- Native iOS/Android apps
- Full free-form report-card design
- Form teachers posting notices to their class's parents
- Logging in as another user (impersonation)
- WAEC/NECO API integration

You can create interfaces such as `NotificationProvider`, `PaymentProvider`, and `LiveClassProvider` in the architecture document, but do not spend the capstone window implementing them.

## Delivery plan

**Pace:** there is no fixed deadline. The target is about two weeks, but it can take fewer or more days. Each day we do as much as we can, until we are tired or the session limit is reached, and every session ends cleanly with tests run, work committed and `LOG.md` updated with the exact next step. The day ranges below are a rough guide, not rules.

### Days 1–2: research and design gate

- Collect two redacted report cards from different schools.
- Interview one teacher and one principal/school administrator.
- Record the date, role, questions, answers, surprises, and one checkable artefact from each conversation.
- Review two competitor pricing pages and two product demos where possible.
- Finalise the ERD, API endpoints, workflow diagram, screens, and acceptance tests.
- Create `RESEARCH.md` before feature code.
- Create `CLAUDE.md` with architecture and security rules.

### Days 3–5: backend and hard part

- PostgreSQL schema and migrations
- Seed two schools
- Authentication (login only) with username or email, student login with school code, invite/activation and temporary-password flows, password reset rules, sign out of all devices
- Additional school admins and super admin login support for school admins
- Role checks and account provisioning rules (super admin creates school admins; school admins create everyone else)
- Student, teacher, reviewer and guardian registration services, class/subject assignment, ward linking
- Tenant-scoped queries
- Grading configuration per level (A1 to F9 and A to F defaults), assessment modes and structures per level, pass mark, rating traits
- School type and report card toggles; learning areas, skills, rating scale and rating sheets
- Class teacher "teaches all subjects" assignments and class teacher assistants
- Score engine
- Score validation
- Approval state machine
- Audit trail
- Pricing engine (plan lookup, volume calculation, cliff protection, price check, versioning) and invoice generation
- Unit and API tests

### Days 6–8: user interfaces

- Dashboard shell: collapsible sidebar, header, mobile drawer, dark/light mode
- Super-admin Create school form, school detail tabs, platform settings, audit and email logs
- School-admin registration screens: students (single and CSV), teachers, reviewers, parents with ward linking, class and subject assignment
- Teacher score sheets with search and filters, and the score-entry grid built from the assessment structure
- Form teacher My class: broadsheet, comments, ratings, attendance, preview
- CSV import preview and error download
- Reviewer queue
- Principal approval screen
- Audit timeline
- Results exception dashboard

### Days 9–10: parent-facing product

- Report-card styles (Modern, Classic, Compact, Early Years), block settings, head's title, and the Skills report card
- PDF rendering
- QR/report-ID verification page
- Parent/guardian child linking
- Published result portal
- Students needing attention list and dashboard cards
- Correction request form and status page
- Notice board (manual notices and automatic result-published notices)
- Email outbox and result-published emails
- Billing: super admin pricing table editor, subscriptions and invoices; school admin billing card, Pay now with the gateway in test mode, invoice history and receipts

### Days 11–12: safety and quality

- Tenant-isolation tests
- Permission-bypass tests
- Approval-bypass tests
- Published-result immutability tests
- Correction-to-new-revision tests
- QR invalid/revoked/superseded tests
- Privacy notice
- Error logging
- Backup/restore test
- Responsive testing on phone, tablet and desktop sizes
- Dark and light mode review of every screen
- Account-provisioning bypass tests (no public register route, additional admins cannot add admins, super admin cannot reset teachers or students)
- Login tests: same error for wrong school code, username or password; student forgot password does nothing
- Scoping tests for My class and Students needing attention
- Payment tests: forged webhook rejected, duplicate webhook ignored, browser cannot change the amount, school cannot see another school's invoices, only super admin can edit pricing

### Days 13–14: deployment and demonstration

- Deploy the web app and API
- Seed realistic Nigerian demo data
- Reproduce two different report-card formats
- Run the five-minute results-week demonstration
- Write README, `RESEARCH.md`, `LOG.md`, and limitations
- Ask one real teacher to try the deployed workflow if possible
- Record feedback and list post-MVP priorities

## Demonstration flow

Your final demo should show this sequence:

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

## Suggested database tables

Keep the schema small but explicit:

- `schools` (including email, phone, address, city, state, country, unique code, colour, status)
- `school_features`
- `school_levels` (enabled per level by the super admin, assessment mode, head's title)
- `platform_settings`
- `users` (including `username`, `must_change_password`, `is_active`, `email_verified_at`)
- `school_memberships` (including `is_primary` for the principal)
- `user_sessions` (for sign out of all devices)
- `account_tokens` (activation and password reset, stored hashed, single use, expiring)
- `roles`
- `permissions`
- `role_permissions`
- `academic_sessions`
- `terms`
- `classes`
- `subjects`
- `students`
- `guardians`
- `guardian_students`
- `departments`
- `teacher_assignments`
- `reviewer_scopes`
- `enrolments`
- `student_subjects`
- `grading_scales`
- `assessment_structures` (per level and term, locked once scores exist)
- `assessment_components`
- `remark_bands`
- `rating_traits`
- `learning_areas`, `skills`, `rating_scales`, `rating_scale_points`, `skill_ratings`, `area_comments`
- `class_assistants`
- `class_report_sections` (form teacher sections and their status)
- `student_term_entries` (comments, ratings, attendance numbers)
- `attention_entries` (generated on publication, staff only)
- `result_sheets`
- `scores`
- `result_revisions`
- `approval_actions`
- `report_templates`
- `report_documents`
- `verification_tokens`
- `correction_requests`
- `audit_events`
- `notices`
- `notice_reads`
- `email_outbox`
- `pricing_versions`
- `pricing_tiers`
- `school_subscriptions`
- `invoices`
- `payments`
- `payment_events` (raw webhook log, for idempotency and troubleshooting)

Every school-owned table should include `school_id`. Every result-related write should run through a service that checks school membership, role permission, module flag, and workflow state.

## How Claude should be used

Claude Code can help you ship this session by session, but give it bounded work. Use prompts such as:

- “Read `CLAUDE.md` and implement only the score validation service. Add unit tests for missing, duplicate, out-of-range, and valid scores.”
- “Implement the result state machine. Do not allow a teacher to approve their own submission. Add tests for every allowed and denied transition.”
- “Review these PostgreSQL queries for cross-tenant leakage. Write tests that attempt to access School B using School A credentials.”
- “Implement immutable revisions. Never update a published result in place. Add a test that proves the old version remains readable as superseded.”
- “Generate the report PDF from the versioned template JSON. Use seeded data and add a rendering test.”
- “Review this QR verification endpoint for exposure of unnecessary student data.”

A good `CLAUDE.md` should state:

- Every school-owned table has `school_id`.
- API authorization is mandatory even when the UI hides a feature.
- Published results are immutable.
- Score corrections require a reason and new revision.
- Parents see only linked children’s published records.
- There is no public registration. Super admin creates school admins; school admins create every other account.
- Passwords are never emailed or stored in plain text.
- Login errors are the same whether the school code, username or password is wrong.
- Students never get self-service password reset. The super admin resets school admins only. Nobody can log in as another user.
- Students needing attention and form teacher data are staff-only and scoped by role.
- Only the super admin switches report card levels on or off; requests for a level that is off are rejected.
- Class teacher assistants can enter but never submit.
- Payment amounts come from server-side invoices; invoices are marked paid only after a verified webhook and server-side check.
- No child’s real data goes into external AI prompts.
- Every security-sensitive change requires tests.

## Startup pricing hypothesis

Do not pretend the price is validated before interviewing schools. Use a testable initial model:

- Free pilot for one school and one term (billing switched off for that school)
- Per-student, per-term pricing in tiers that get cheaper per student as schools grow (Basic, Standard, Premium), fully editable by the super admin
- Test the default prices in school conversations, using the price check to avoid cliffs
- Optional paid add-ons later: branded report-card setup, migration from Excel, SMS/WhatsApp notifications, additional modules, and support

The key commercial value is not “another place to enter marks.” It is:

> **Less results-week stress, fewer disputes, faster publication, and a trustworthy record when someone asks who changed a score.**

Your first selling conversation should ask:

1. How are scores collected today?
2. What usually delays publication?
3. How often do parents challenge results?
4. How are corrections approved?
5. Can you identify who changed a score?
6. How much time is spent formatting report cards?
7. Would a school pay per term for a verified, branded, audit-ready report process?

## Final recommendation

Do not accept the tutor’s wording as “build only a result system.” Build a **results operations product** with a slim school-platform foundation. That gives you:

- A broader MVP
- A complete teacher-to-parent journey
- A real startup problem
- A meaningful differentiator
- A manageable build, worked on session by session
- Strong evidence for your viva
- Working subscription billing, so the product can charge schools from day one
- A clear roadmap into school fees, attendance, LMS, CBT, notifications, and live classes

The best defensible differentiation is the **Audit-ready Result Trust Chain**, supported by:

1. Nigerian-first score integrity and spreadsheet validation
2. Verified no-app parent report handoff
3. Linked correction/dispute queue
4. Results-week exception dashboard
5. Custom school report cards

The first four make the product more than a result portal without exceeding the MVP boundary. The report-card designer and multi-tenant shell make it more than a single-school script. The audit-ready trust chain makes it sellable as a focused school SaaS product.

## References

[1]: https://www.researchpublish.com/upload/book/A%20Prototype%20Interactive-8552.pdf "A Prototype Interactive Web-Based Result Processing System"
[2]: https://www.waecnigeria.org/faq "WAEC Nigeria Frequently Asked Questions"
[3]: https://verify.waeconline.org.ng/Home/faq "WAEC Verify Frequently Asked Questions"
[4]: https://www.nuffic.nl/en/education-systems/nigeria/grades-and-study-results "Nigeria grades and study results - Nuffic"
[5]: https://ubec.gov.ng/wp-content/uploads/2024/04/NALABE-National-report.pdf "UBEC NALABE National Report"
[6]: https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf "Nigeria Data Protection Act General Application and Implementation Directive"
[7]: https://safsims.com/student-result-management-system/ "SAFSIMS Student Result Management System"
[8]: https://schoolshell.com/school-management-portal-in-nigeria/ "SchoolShell School Management Portal in Nigeria"
[9]: https://schoolhub.top/seo/school-report-card-management-system "SchoolHub Report Card Management System"
[10]: https://www.edves.com/solutions/assessment/ "Edves Assessment"
[11]: https://excelmind.org/teachers "ExcelMind Teachers"
[12]: https://skooldrive.com/student-result-management-system "SkoolDrive Student Result Management System"
[13]: https://fedena.com/feature-tour/exam-management-system "Fedena Exam Management System"
[14]: https://schoolsfocus.net/ "SchoolsFocus"
