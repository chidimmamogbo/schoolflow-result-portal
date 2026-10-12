# UI_REVIEW.md: Phase 5 review of the design handoff

Phase 5 of `docs/BUILD_PROMPT.md`. It checks the v0.5 design handoff in `design/` against every page the build needs (BUILD_PROMPT section 9.3, SPEC section 10.2, design brief section 9). Started 2026-10-12.

Sources: `design/README.md` (screen inventory and flows), `design/docs/DESIGN_BRIEF.md` section 9 (priorities P1, P2, P3), `design/docs/DESIGN_REVIEW_v0.5.md` (the designer's own check), `design/NAVIGATION_AND_SETTINGS.md` (labels).

## 1. Coverage: every page and its design

Key: **Designed** = a v0.5 board in both themes and on phone. **v0.3 only** = an approved older board, one theme only. **Partly** = some of the page is drawn. **None** = no board. P1/P2/P3 is the brief's priority (P1 is in the demo).

### Public

| Route | Design file | Status | P |
|---|---|---|---|
| `/` landing | | None | P2 |
| `/login` | `Login` | Designed | P1 |
| `/login/[schoolCode]` | `Login_Link` | Designed | P1 |
| `/school-paused` | `SchoolPaused` | Designed | P2 |
| `/activate` | | **None** | P1 |
| `/change-password` | `ChangePassword` | Designed (password rule text conflicts, see 2.1) | P1 |
| `/forgot-password`, `/reset-password` | | None | P2 |
| `/verify`, `/verify/[code]` | `Verify`, `VerifyAfter` | v0.3 only (code length differs, D-072) | P1 |
| `/privacy`, 404, no access | | None | P3 |

### Super admin

| Route | Design file | Status | P |
|---|---|---|---|
| `/platform` dashboard | `SuperDashboard` | v0.3 only | P2 |
| `/platform/schools` | `SchoolsV5` | Designed | P1 |
| `/platform/schools/new` | `CreateSchool` | Designed | P1 |
| `/platform/schools/[id]` | `SchoolDetailV5`, `SchoolDetailBSA` | Designed | P1 |
| `/platform/settings` | `PlatformSettings` | Designed | P1 |
| `/platform/pricing` | `PricingV5` | Designed | P1 |
| `/platform/billing` | `SuperBillingV5` | Designed | P1 |
| `/platform/billing/invoices/[id]` | `Payments` (detail, void) | Partly | P2 |
| `/platform/payments` | `Payments` | Designed | P2 |
| `/platform/audit` | `AuditLog` | Designed | P2 |
| `/platform/emails` | `EmailLog` | Designed | P3 |
| `/platform/announcements` (after the core) | | None | P3 |

### School admin / principal

| Route | Design file | Status | P |
|---|---|---|---|
| `/school/dashboard` | `DashboardV5` | Designed | P1 |
| `/school/settings` | | None | P2 |
| `/school/setup/sessions` | | None | P2 |
| `/school/setup/classes` | `ClassPage` (one class only) | Partly: no classes and arms list | P2 |
| `/school/setup/subjects`, `/departments` | | None | P2 |
| `/school/setup/grading` | `Grading`, `GradingBSA` | Designed | P2 |
| `/school/setup/assessment` | `Assessment`, `AssessmentBSA` | Designed | P1 |
| `/school/setup/skills` | `LearningAreas` | Designed | P1 |
| `/school/setup/rating-traits` | (`PlatformSettings` shows the default list) | Partly | P3 |
| `/school/admins` | `SchoolAdmins`, `SchoolAdminsBSA` | Designed | P2 |
| `/school/students` list | | **None** | P1 |
| `/school/students/new` | | **None** | P1 |
| `/school/students/import` | | **None** | P1 |
| `/school/students/[id]` | `StudentDetail` | Designed | P2 |
| `/school/teachers`, `/new`, `/[id]` | (`ClassPage` shows Teaches all subjects and assistants) | **None** (Partly) | P1 |
| `/school/reviewers`, `/new`, `/[id]` | | None | P2 |
| `/school/parents`, `/new`, `/[id]` | | **None** | P1 |
| `/school/approvals` | `Approvals` | v0.3 only | P1 |
| `/school/publish` | `PublishV5` | Designed | P1 |
| `/school/attention` | `Attention` | Designed | P1 |
| `/school/notices`, `/new`, `/[id]` | | **None** | P1 |
| `/school/emails` | (`EmailLog` pattern) | None | P3 |
| `/school/billing`, `/invoices/[id]`, `/callback` | `BillingV5` (includes confirming and receipt) | Designed | P1 |
| `/school/audit` | (`AuditLog` pattern) | **None** | P1 |
| `/school/report-templates`, `/[id]` | `TemplateEditorV5`, `TemplateEditorBSA` | Designed | P1 |
| `/school/corrections`, `/[id]` | `Corrections` | v0.3 only | P1 |

### Reviewer / HOD

| Route | Design file | Status | P |
|---|---|---|---|
| `/review` queue | | **None** | P1 |
| `/review/[sheetId]` | (read-only `ScoreGridV5`) | **None** | P1 |
| `/review/attention` | `AttentionReviewer` | Designed | P2 |

### Teacher

| Route | Design file | Status | P |
|---|---|---|---|
| `/teacher` dashboard, `/teacher/sheets` | `SheetsV5` | Designed | P1 |
| `/teacher/sheets/[sheetId]` | `ScoreGridV5`, `ScoreGridSS`, `RatingSheet`, `RatingSheetAssistant_Phone` | Designed | P1 |
| `/teacher/sheets/[sheetId]/import` | | None | P2 |
| `/teacher/attention` | `AttentionTeacher`, `AttentionTeacherBSA` | Designed | P1 |
| `/teacher/my-class` (+ students, preview) | `MyClass`, `MyClassPrimary` | Designed | P1 |

### Parent, student and shared

| Route | Design file | Status | P |
|---|---|---|---|
| `/parent` | `ParentHome` | v0.3 only | P1 |
| `/parent/children/[studentId]` | | **None** | P1 |
| `/parent/reports/[reportId]` | `ReportView`, `ParentSkills` | v0.3 only (`ParentSkills` designed) | P1 |
| `/parent/corrections`, `/new` | `ParentCorrection` | v0.3 only | P1 |
| `/student`, `/student/reports/[reportId]` | (parent pattern, self only) | None | P2 |
| `/notices` board, notice bell | | **None** | P1 |
| Profile | | None | P3 |
| Report card PDFs | `ReportCompactSS`, `ReportModernHighlights`, `ReportPrimary4A`, `ReportSkillsEY`, `ReportSkillsModern`, `ReportCard`, `ReportCardClassic` | Designed (always light) | P1 |

### Summary

- **P1 pages with no design: 13** (activate; students list, add, import; teachers; parents; school audit; notices list and composer; notice board; notice bell; review queue; review sheet; child results). Same list as the designer's own review (`DESIGN_REVIEW_v0.5.md` item 1).
- **P1 pages on v0.3 boards, one theme only: 6** (verify, approvals, corrections, parent home, report view, parent correction).
- **P2 and P3 pages with no design: 12**, mostly simple lists and forms.
- Everything else (about 30 pages) has a v0.5 board.

## 2. Problems found

### 2.1 Change password rules contradict D-036
`ChangePassword` and NAVIGATION section 5 show "At least 8 characters", "A letter and a number". D-036 (Chidimma, 2026-10-09) says at least **15 characters for staff and parents, 10 for students**, and **no composition rules** (no "letter and number" rule), plus a common-password block. Behaviour follows the decision, so the screen's rule text must change.

### 2.2 Labels still waiting for sign-off
NAVIGATION section 5 lists about 200 labels proposed during design. Until approved they are placeholders.

### 2.3 Known, already approved
- Verification code is 12 characters, not 8 (D-072).
- Collapsed sidebar and header theme toggle are drawn on only some boards; built once in the shared shell (`DESIGN_REVIEW_v0.5.md`).

## 3. Decisions

- **D-132:** pages with no design are built from existing v0.5 patterns; reviewed in the browser in Phase 8.
- **D-133:** v0.3 boards keep their layouts and get both themes from the tokens.
- **D-134:** Change password rule text follows D-036.
- **Section 5 labels:** reviewed group by group (section 4 below).

## 4. Section 5 labels: sign-off

| Group | Status |
|---|---|
| Shared | Approved 2026-10-12. Change password rules reworded for D-036: "At least 15 characters" (students: "At least 10 characters"), "Not a common password", "Different from your temporary password". Teacher menu "Sheets" renamed **"Result sheets"** (it holds score sheets and rating sheets; if it does not fit the phone bar at 320px, the phone bar keeps "Sheets") |
| Super admin | Approved 2026-10-12, as written |
| School admin / principal | Approved 2026-10-12 with fixes: "Below {pass mark}%"; "Showing {n} of {total} results across {class}."; "{class} has 2 assistants. Remove one to add another."; "Class teacher of {class}"; "{n} of {total} subjects in {class}"; "Pass mark must be a whole number from 1 to 99." (was 0 to 100; follows SPEC section 12, Chidimma 2026-10-12) |
| Teacher | Approved 2026-10-12 with fixes: page title "My result sheets" (was "My score sheets", section 2); cards tagged "Score sheet" or "Rating sheet"; "No result sheets yet."; "Back to my result sheets"; "Submit {learning area}, {class}?" |
| Print and parent | Approved 2026-10-12 with fixes: "Below pass mark ({pass mark})…" (the value the report was published with); "{name}'s {term} report is not ready yet"; "Head teacher's comment" follows the template's Head's title |

## 5. Role journeys

Numbered steps for each role, from first login to the main job, with the page for each step. Built from SPEC F02, F03, the 38-step demo (SPEC section 16) and design README flows. Sample schools: Greenfield Model College (GMC, Secondary only), Bright Stars Academy (BSA, Nursery and Primary). All fictional.

**First login, two routes (every role except super admin):**
- **Activation email:** open the link (`/activate`) > see the school name > set a password (D-036 rules) > logged in. A used or expired link shows the expired state with "Ask your school admin".
- **Temporary password** (printed slip): `/login` (or `/login/GMC` for students) > log in > forced `/change-password` (cannot be skipped) > home.

### 5.1 Super admin
1. Logs in on the Staff and parents tab (`/login`). The account is created by the seed command, never a form.
2. Lands on the platform dashboard (`/platform`): schools, subscriptions, term revenue.
3. Creates a school (`/platform/schools/new`): school type, report card levels, code check, colour, features, billing, principal's name, username, email, login method. Success shows "Open school".
4. Manages a school (`/platform/schools/[id]`): Features (turn a level off, with confirmation), School admins (change email, send reset link, temporary password slip, sign out of all devices), Subscription, Invoices, Activity.
5. Sets prices (`/platform/pricing`): edit plans, price check, Try it, save as new version.
6. Bills (`/platform/billing`): generate invoices for the term, record a manual payment; `/platform/payments` lists every payment.
7. Watches the platform: `/platform/audit`, `/platform/emails` (Retry failed), `/platform/settings`.

### 5.2 School admin / principal
1. Activates from the email (`/activate`) and logs in.
2. Dashboard (`/school/dashboard`): what is blocking release, Students needing attention card, billing card, latest notices.
3. Setup, once per session or term: sessions and terms, classes and arms, subjects, departments, grading and pass mark, assessment structure per level (Scores or Skill ratings), learning areas and skills, rating traits.
4. People: adds an additional school admin (principal only, `/school/admins`); students one by one or by CSV import; teachers with assignments, form teacher and Teaches all subjects; class teacher assistants on the class page; reviewers with scope; parents linked to wards. Each create form gives a username and a login method; temporary passwords print a slip.
5. Login support from a person's page: resend activation, send reset link, new temporary password and slip, deactivate.
6. Results week: Approvals (`/school/approvals`, approve sheets), then Publish results (`/school/publish`): checklist, principal's comments, preview, Publish.
7. After publishing: Students needing attention (`/school/attention`), corrections (`/school/corrections`: investigate, reopen with a reason, republish), audit trail (`/school/audit`).
8. Notices (`/school/notices/new`: audience, pin), email status (`/school/emails`), report templates (`/school/report-templates`).
9. Billing (`/school/billing`): plan, amount due, Pay now > Paystack test > `/school/billing/callback` "Confirming your payment" > receipt.

### 5.3 Reviewer / HOD
1. First login (activation or temporary password).
2. Review queue (`/review`): submitted sheets in scope, oldest first.
3. Opens a sheet (`/review/[sheetId]`): read-only grid with flags and change history. Return with a comment (required) or Mark reviewed.
4. Students needing attention for their scope (`/review/attention`); notices (`/notices`).

### 5.4 Teacher (subject teacher, form or class teacher, assistant)
1. First login (activation or temporary password). Username or email both work.
2. Result sheets (`/teacher/sheets`): grouped by class, chips Class, Subject, Status, search; each card tagged Score sheet or Rating sheet, with progress and any return comment.
3. Score sheet (`/teacher/sheets/[sheetId]`): find a student, enter CA and exam marks, fix flagged missing or out-of-range marks, Submit. Or import a CSV (`/import`). A returned sheet shows the reviewer's comment; changes need a reason.
4. Rating sheet (Nursery): rate every skill, area comments, Submit.
5. Form or class teacher: My class (`/teacher/my-class`): broadsheet, then each student's comment, ratings and attendance (Save and next), Preview, Submit class sections.
6. Assistant: same sheets and My class, saves but never sees Submit.
7. After publishing: Students needing attention for own subjects and own class (`/teacher/attention`); notices.

### 5.5 Parent / guardian
1. First login (activation or temporary password).
2. Home (`/parent`): ward switcher, latest result card, latest notices.
3. Child results (`/parent/children/[id]`): terms with status.
4. Report (`/parent/reports/[id]`): low-bandwidth summary or Skills report; Download PDF (always light); Verify.
5. Report a problem (`/parent/corrections/new`) > status timeline (`/parent/corrections`).
6. Notices (`/notices`) and the result-published email (never with scores).

### 5.6 Student
1. Gets a printed slip from the school admin. Opens `/login/GMC` (code filled in) or the Student tab, types username or admission number and the temporary password.
2. Forced Change password (10-character minimum).
3. Home (`/student`): own results only; report (`/student/reports/[id]`) with Download PDF and Verify; notices.
4. Forgot password: no link; the Student tab says "Forgot your password? Ask your school admin for a new one."

### 5.7 Anyone (public)
- Verify (`/verify`, or scan the QR to `/verify/[code]`): VALID, SUPERSEDED (a newer version exists) or REVOKED, masked name, never scores.

Role journeys approved by Chidimma on 2026-10-12.

## 6. BUILD_PROMPT Phase 5 checklist (items 2 to 9)

| # | Item | Result | Where it lives |
|---|---|---|---|
| 2 | Screen inventory (purpose, who, data, actions, states) | Pass | Purpose, data and actions per page: design brief section 9. Route map: section 1 above. States: every v0.5 board has Default, Empty, Loading, Error (and No access where it applies). Pages without a board: section 7 below |
| 3 | Dashboard shell | Pass, built once | Brief section 7 and `design-system/README.md` "Layout": sidebar 256px expanded, 72px collapsed with tooltips, remembered; drawer on phones; header with notice bell, theme toggle (light, dark, system) and profile menu. Collapsed sidebar is drawn only on `BsaMenus`; the theme toggle only on some headers. Both are built once in the shared shell (designer's review) |
| 4 | Breakpoints | Pass | Tokens `bp-phone-sm` 360, `bp-phone-lg` 414, `bp-tablet` 768, `bp-laptop` 1024, `bp-desktop` 1440. Tablet: sidebar starts collapsed. Boards are drawn at desktop and phone only; tablet and laptop follow the written rules. Tailwind's default `md` (768) and `lg` (1024) match the tablet and laptop tokens |
| 5 | Design system, both themes | Pass | `design-system/tokens.css`: light (`:root`, `[data-theme="light"]`) and dark (`[data-theme="dark"]`). Contrast measured by the designer: 4.56 or more in light, 5.09 or more in dark. School colours checked by the colour picker (warns below 4.5) |
| 6 | Key interactions | Pass, with D-132 | Designed: login tabs, score grid and filters, assessment editor with running total, My class, Students needing attention, Create school with colour picker, price check, publish with principal's comments, template block editor, credential slip, rating sheet. Built from patterns (D-132): registration forms, CSV import preview, notice composer and board, review actions, reason dialog on review |
| 7 | Print design | Pass | Seven A4 boards, always light, independent of the app theme |
| 8 | Two real-world report card formats | Partly done (D-135) | No real cards were given to the designer. Research on 2026-10-12 (`docs/REPORT_CARD_RESEARCH.md`) used the Ogun State CA report sheet and the FCT UBEB termly report as the two formats; the template gained the missing switches and defaults. Still useful: one or two real cards from schools Chidimma knows, with names covered |
| 9 | Accessibility | Pass | Labels on every field; 2px focus ring with offset; 44px touch targets on phones; status = icon + word; 14px minimum body on phones; `prefers-reduced-motion` in `sf.css`. Automated check with axe (WCAG 2.2 AA) in Phase 8 and 9 |

## 7. Content for the 13 demo pages without a board (D-132)

Taken from design brief section 9 and the SPEC. Every page also has Empty, Loading, Error and No access states, phone and desktop, light and dark.

| Page | Who | Shows | Actions | Pattern to reuse |
|---|---|---|---|---|
| Activate account | Any new user | School name and logo, welcome, password rules (D-036) | Set password, confirm; expired-link state | `ChangePassword` |
| Students list | School admins | Table: name, admission number, class, status | Search, filter by class and status, Add, Import, open | `SchoolsV5` table and filters |
| Add student | School admins | Name, admission number, username (suggested, availability), gender, date of birth, class and arm, house, subjects (from class), guardian link, login method | Save; temporary password shows the slip | `CreateSchool` form, `StudentDetail` slip |
| Import students | School admins | 4 steps: download template, upload, preview with row errors and count, commit (off while errors), summary | Upload, fix, commit | New; table from `SchoolsV5` |
| Teachers list, add, detail | School admins | Username, assignments as subject + class chips, Form teacher of, Teaches all subjects, Login tab | Add, assign, login support | `ClassPage`, `StudentDetail` |
| Parents list, add, detail | School admins | Name, contact, linked wards with relationship, login method | Add, link or unlink wards, login support | `StudentDetail` |
| Audit trail (school) | School admins | Timeline filtered by student, subject, class, person; before and after values, reason | Filter, Show details | `AuditLog` |
| Notices list and composer | School admins | Title, message, audience (everyone, roles, classes), pin, preview | Post, pin, unpin | `PlatformSettings` form |
| Notice board | All signed-in | Pinned first, unread marked, filter, detail | Open, mark read | `EmailLog` list |
| Notice bell | All signed-in | Latest 5, unread count | View all | Header (all v0.5 boards) |
| Review queue | Reviewer | Submitted sheets in scope, oldest first | Open | `SheetsV5` |
| Review sheet | Reviewer | Read-only grid with flags and change history | Return with comment (required), Mark reviewed | `ScoreGridV5` read-only, `Approvals` |
| Child results | Parent | Terms list with status for one ward | Open report | `ParentHome` |
