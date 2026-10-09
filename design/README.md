# SchoolFlow Result Portal: UI/UX handoff (v0.5)

This folder is the UI/UX for SchoolFlow Result Portal at spec v0.5 (product name in the spec: ResultChain). Use it as the visual and interaction reference when building the real app.

**Source of truth for behaviour:** `docs/SPEC.md` (v0.5). **Source of truth for look and feel:** `design-system/` and the screens in `screens/`. If a screen and the spec disagree on behaviour, the spec wins. **Labels:** `NAVIGATION_AND_SETTINGS.md`. Section 5 of that file lists labels proposed during design that still need sign-off.

## What is in here

| Folder | What it holds |
|---|---|
| `NAVIGATION_AND_SETTINGS.md` | The exact menu labels for every role, page titles, every setting with its default, button labels, and (section 5) proposed labels waiting for sign-off |
| `docs/SPEC.md` | Spec v0.5: features, roles, permissions, state machines, data model |
| `docs/DESIGN_BRIEF.md` | Design brief v0.5: users, principles, status system, shells, screen inventory, flows, microcopy, checklist |
| `docs/DESIGN_REVIEW_v0.5.md` | The v0.5 screens checked against the brief's acceptance checklist, with what fails and the fixes |
| `design-system/` | Tokens (JSON and CSS) and the brand book |
| `brand/logos/` | Logo lockups and marks. Use the files as they are |
| `screens/` | 110 prototype files plus `sf.css` (see below) |

## How to read the screen files

Each `screens/*.dc.html` file is one board from a design-canvas prototype. They need the canvas runtime's `support.js` to run, so read them as precise design specs:

- **Markup inside `<x-dc>`** is the real layout. The v0.5 screens use the classes in `screens/sf.css` (the app shell, cards, badges, tables that turn into cards on phones, dialogs, switches, chips). `sf.css` reads its colours from CSS variables that match `design-system/tokens.json`. Light and dark are set with `data-theme` on the `.sf` root, and phone or desktop with `data-device`.
- **`{{name}}`** is a value filled in by the script at the bottom. **`<sc-if>`** shows content when a flag is true, and **`<sc-for>`** repeats it.
- **`onClick` / `onChange`** handlers and all state, validation and calculations live in `class Component extends DCLogic`.
- **Tweaks:** the `data-props` JSON at the bottom lists the switches on each board: theme (Light, Dark), state (Default, Empty, Loading, Error) and device (Desktop, Phone), plus extras such as school, role, variant or locked.
- **Wrappers:** files ending `_Phone` (and a few named ones such as `AttentionBSA` or `ScoreGridSS`) only import the main screen with fixed tweak values through `<dc-import>`. Build one screen, not two.
- **Superseded files:** the approved v0.3 boards (`Main`, `TeacherSheets`, `ScoreGrid`, `Dashboard`, `Publish`, `Billing`, `Schools`, `SchoolDetail`, `Pricing`, `SuperBilling`, `TemplateEditor`) are kept for comparison. Build from the v0.5 versions. `Approvals`, `Corrections`, the parent boards, `Verify`, `VerifyAfter`, `SuperDashboard` and the two approved report cards are still current.

## Screen inventory (v0.5)

| File | Role | Device | What it shows | Spec |
|---|---|---|---|---|
| `Login` | All | Desktop + phone | Tabs Staff and parents / Student (school code), "Ask your school admin" text, error and loading | F02 |
| `Login_Link` | Student | Desktop + phone | School login link /login/GMC with the code filled in | F02 |
| `ChangePassword` | All | Desktop + phone | Forced password change after a temporary password | F02 |
| `SchoolPaused` | All | Desktop + phone | "Your school's access is paused" page | F01, F24 |
| `SchoolsV5` | Super admin | Desktop + phone | Schools list with search and filters | F01 |
| `CreateSchool` | Super admin | Desktop + phone | Full-page Create school: school type, report card switches, code check, colour picker with contrast warning, principal account, success | F01, F03, F25 |
| `SchoolDetailV5 / SchoolDetailBSA` | Super admin | Desktop + phone | Tabs Overview, Features (Report cards by level, turn-off confirmation), School admins (login support, reset and temporary password), Subscription, Invoices, Activity | F01, F03 |
| `PricingV5` | Super admin | Desktop + phone | Plans editor, cliff protection, price check, Try it calculator, versions | F19 |
| `SuperBillingV5` | Super admin | Desktop + phone | Invoices by school with cliff protection column, generate and record payment | F19 |
| `Payments` | Super admin | Desktop + phone | All payments, filters, payment detail | F19 |
| `AuditLog` | Super admin | Desktop + phone | Platform audit timeline with filters and before/after details | F11, F24 |
| `EmailLog` | Super admin | Desktop + phone | Email log by type and status, Retry for failed, never bodies | F18, F24 |
| `PlatformSettings` | Super admin | Desktop + phone | Tabs General, Email, School defaults, Billing, Security | F24 |
| `DashboardV5` | Principal | Desktop + phone | What is blocking release, form teacher sections, Students needing attention card, billing card | F16, F23 |
| `PublishV5` | Principal | Desktop + phone | Checklist with form teacher sections, Principal's comments step, publish | F10, F22 |
| `Attention (+ Teacher, Reviewer, BSA, TeacherBSA wrappers)` | Principal, teacher, reviewer | Desktop + phone | Students needing attention: By subject, By student, By learning area, filters, Before publication state | F23 |
| `Assessment / AssessmentBSA` | Principal | Desktop + phone | Assessment structure per level, Scores or Skill ratings, locked state, total warnings | F08, F26 |
| `Grading / GradingBSA` | Principal | Desktop + phone | Pass mark and grade bands per level, A to F for Primary | F08 |
| `SchoolAdmins / SchoolAdminsBSA` | Principal | Desktop + phone | School admins, limit message, login support, temporary password slip, principal-only state | F03 |
| `StudentDetail` | Principal | Desktop + phone | Student detail tabs, Login support menu, temporary password with Print slip | F03 |
| `LearningAreas` | Principal (Bright Stars) | Desktop + phone | Learning areas and skills, rating scale card | F26 |
| `ClassPage` | Principal (Bright Stars) | Desktop + phone | Primary 4A: class teacher, Teaches all subjects, assistants | F04, F06 |
| `BsaMenus` | Principal (Bright Stars) | Desktop + phone | How menus, tabs and filters look with only Nursery and Primary on | F25 |
| `TemplateEditorV5 / TemplateEditorBSA` | Principal | Desktop + phone | Templates by level, styles, collapsible settings, Template settings, Head's title, live preview | F12 |
| `BillingV5` | Principal | Desktop + phone | Invoice due 580 x ₦500 = ₦290,000, pay flow, history | F19 |
| `SheetsV5` | Teacher | Desktop + phone | My score sheets grouped by class, search and filter chips | F09 |
| `ScoreGridV5 / ScoreGridSS` | Teacher | Desktop + phone | Score entry with 3 or 5 components, search, All / Missing / Errors chips | F09, F10 |
| `RatingSheet / RatingSheetAssistant_Phone` | Teacher | Desktop + phone | Nursery 2 Number work rating sheet, assistant view without Submit | F26 |
| `MyClass / MyClassPrimary` | Form or class teacher | Desktop + phone | Broadsheet, Students (student entry), Preview, class sections card with Returned state | F22 |
| `ParentSkills` | Parent | Desktop + phone | Skills report view, light and dark | F14, F26 |
| `ReportCompactSS` | Print | A4 | Compact Score report card, SS 2A, 15 subjects, 5 components | F12 |
| `ReportModernHighlights` | Print | A4 | Modern card with Highest, Lowest and below pass mark highlight | F12 |
| `ReportPrimary4A` | Print | A4 | Primary 4A Score report card, A to F, Head teacher's comment | F12 |
| `ReportSkillsEY / ReportSkillsModern` | Print | A4 | Nursery 2 Skills report card, Early Years and Modern | F12, F26 |

Still current from v0.3: `Approvals`, `Corrections`, `ParentHome`, `ReportView`, `ParentCorrection`, `Verify`, `VerifyAfter`, `SuperDashboard`, `ReportCard`, `ReportCardClassic`.

## Flows (follow the links)

1. Teacher score entry (phone): `Login_Phone` > `SheetsV5_Phone` > `ScoreGridV5_Phone`, fix the two flagged scores, Submit.
2. Review and return: reviewer screens are not designed yet (see docs/DESIGN_REVIEW_v0.5.md).
3. Approve and publish: `DashboardV5` > `Approvals` > `PublishV5` > Go to dashboard.
4. Parent result (phone, dark): `ParentHome` > `ReportView` > `Verify`.
5. Correction: `ParentHome` Report a problem > `Corrections` > `VerifyAfter`.
6. Account provisioning: `StudentDetail` Login support > Issue temporary password > Print slip; student logs in at `Login_Link_Phone` > `ChangePassword_Phone`.
7. Parent and wards: `ParentHome` ward switcher (add parent screens not designed yet).
8. Subscription: `PricingV5` > `SuperBillingV5` Generate > `DashboardV5` billing card > `BillingV5` Pay now > Paid.
9. Sidebar and theme: Theme switch on every board, phone drawer on every phone board, collapsed sidebar on `BsaMenus`.
10. Create school: `SchoolsV5` > `CreateSchool` > custom colour (contrast warning) > code check > principal > Create > success.
11. Lost principal login: `SchoolDetailV5` > School admins > Change email > Send reset link.
12. Student login: `Login_Link_Phone` > Student tab > Log in > `ChangePassword_Phone`.
13. Teacher find and enter: `SheetsV5_Phone` > Class JSS 1A > Mathematics > search "Zainab" > fix score.
14. Form teacher: `MyClass` (and `MyClass_Phone`) > Broadsheet > Students > Save and next > Preview > Submit class sections.
15. Attention after publish: `PublishV5` > principal's comments > Publish > Go to dashboard > View list > `Attention` filtered to JSS 1A; teacher's scoped view `AttentionTeacher`.
16. Assessment setup: `Assessment` > Senior Secondary > add CA3 and Project > total 100 > Save.
17. Nursery and Primary school: `CreateSchool` > School type "Nursery and Primary" > Create > Open school > `SchoolDetailBSA` > Features > turn Nursery off > type shows Custom.
18. Skill ratings setup: `AssessmentBSA` > Nursery > Skill ratings > `LearningAreas` > edit a skill and the rating scale.
19. Class teacher and assistant: `ClassPage` > class teacher > Teaches all subjects > Add assistant; `RatingSheetAssistant_Phone` saves with no Submit.
20. Nursery report: `RatingSheet_Phone` > rate the missing skills > Submit; `ParentSkills_Phone` > Download PDF > `ReportSkillsEY`.

## Sample data notes

All names, scores and schools are fictional. Values not in brief Section 12 were invented to fill the boards. The main ones:

- **Classes:** JSS 1B students, SS 2A scores, Primary 4A and Nursery 2 ratings.
- **People:** extra teachers and the assistants.
- **Records:** audit and email events.
- **Contacts:** support contacts.

Anything still unknown shows as [PLACEHOLDER], for example Royal Crest's plan and student count, and Bright Stars' student count.

## Rules that must carry into the build

- Copy every visible label word for word: menu items, group headings, page titles, tab names, buttons, switch labels and their descriptions, messages. `NAVIGATION_AND_SETTINGS.md` is the master list. Don't rename, shorten or "improve" them.

- Every status shows an icon and a word, never colour alone (badge table in `design-system/README.md`).
- Light and dark themes for every screen. Report cards, PDFs and print are always light.
- In light mode, use `success-ink` and `warning-ink` for text, not `success` or `warning`.
- Body text never below 14px on phones; score cells at least 16px with tabular numbers; touch targets at least 44px.
- A visible 2px `focus` ring on every focusable element.
- Report card summary: Total score, Total average, and Overall class position. Class position is optional per school template, and when it is off, show Number in class instead.
- Phone touch targets at least 44px, nothing scrolls sideways at 320px.
- Money as `₦321,000`, dates as `5 Jan 2027`, plain English, no em dashes, no internal codes shown to parents, students or teachers.
- All names, scores and schools in the screens are fictional sample data.
