# v0.5 design review against the acceptance checklist (brief Section 15)

Reviewed on 7 October 2026. This covers every new and changed v0.5 screen, 110 screen files in `screens/`. How each item was checked:

- **Markup and copy:** a script checked tag balance and em dashes on every file.
- **States and devices:** every screen was run in every State, on Desktop and Phone, for both schools.
- **Links:** every rendered link was checked to point at a file that exists, with phone boards linking to phone boards.
- **Phone width:** the main phone screens were rendered at 320px and checked for anything sticking out sideways.
- **Status badges:** the main desktop screens were rendered and every badge checked for an icon.
- **Contrast:** the token and school colour pairs were measured.

Fixed means I changed it during this review.

| # | Checklist item | Result | Notes and fix |
|---|---|---|---|
| 1 | Every P1 screen exists for phone and desktop, in light and dark | **Partly fails** | Every v0.5 board has a desktop and a phone version and a Theme switch. Some P1 screens from brief Section 9 were not part of follow-ups 1 to 6, so they still have no design at all: Activate account, Students list, Add student, Import students (CSV), Teachers list and add teacher, Parents list and add parent, Audit trail (school), Notices list and composer, Notice board, Notice bell dropdown, Review queue, Review sheet, Child results. The approved v0.3 boards (Approvals, Corrections, Parent home, Report view, Verify) are still light only, or dark only for the parent boards. **Fix:** design these next, as a new follow-up, using the same shells. |
| 2 | Empty, loading, error and no-access states | Pass (fixed) | Every v0.5 screen has Empty, Loading and Error. No-access was missing. Added: School admins now has a "viewer" switch where a school admin who is not the principal sees "Only the principal can manage school admins." and the menu item is hidden. Students needing attention also has a "Before publication" state. |
| 3 | Nothing scrolls sideways at 320px | Pass | All 28 main phone screens rendered at 320px with nothing sticking out. Wide tables (the broadsheet) scroll inside their own card. Elsewhere tables turn into cards. |
| 4 | Sidebar expanded, collapsed (with tooltips) and mobile drawer | **Partly fails** | Every v0.5 shell has the expanded sidebar and the phone drawer. Only the Bright Stars menus board (`BsaMenus`) shows the collapsed sidebar, with a tooltip on each icon. **Fix:** in the build, the shared shell gets one collapse button. There's no need to redraw every board. |
| 5 | Every status uses icon and text | Pass (fixed) | The Subscription column on Schools, the "Needs attention" words on the Dashboard and the checklist words on Publish results were text only. They now have icons. The badges still without icons are not statuses: version tags, counts, role names and the score structure chips. |
| 6 | Contrast meets WCAG AA in both themes, including school colours | Pass | All text and badge pairs measure 4.56 or higher in light and 5.09 or higher in dark. White on the school colours: Greenfield 6.47, Bright Stars 10.2, Royal Crest 11.15. The colour picker warns below 4.5. |
| 7 | Touch targets at least 44 x 44px on phones | Pass (fixed) | Filter chips, small buttons, tabs, segmented buttons and text links were 36px on phones. `sf.css` now makes them 44px on phones, and switches get a 44px tap area. |
| 8 | Focus states visible | Pass | `sf.css` gives every focusable element a 2px `focus` ring. |
| 9 | No register or sign-up anywhere | Pass | Login says "There is no sign-up." |
| 10 | Emails and notices never show scores | Pass | The Email log shows recipient, type, school, status and time, never a message body. |
| 11 | Verification shows a masked name, never scores | Pass | Unchanged approved Verify boards. |
| 12 | Report cards and print previews use the light print design | Pass | All A4 boards and the template preview stay light in dark theme. |
| 13 | Naira as ₦321,000 and dates as 5 Jan 2027 | Pass | No other formats show on screen. Dates in the yyyy-mm-dd form appear only inside scripts, as filter values. |
| 14 | Only fictional data | Pass | Values that aren't in Section 12 are listed in the "Invented sample values" notes in the README. Unknown numbers show as [PLACEHOLDER]. |
| 15 | Copy follows Section 13 | Pass | No em dashes, no "Oops", "successfully" or "click here". Plain sentences. |
| 16 | Login tabs, student code, no forgot link on Student tab | Pass | Student tab shows "Forgot your password? Ask your school admin for a new one." The forced Change password screen is now designed too. |
| 17 | No "Graduated" pricing, and cliff protection and price check shown | Pass for v0.5 | `PricingV5` has no Graduated option and shows cliff protection and price check. The approved v0.3 `Pricing.dc.html` still shows Graduated. It is superseded, so don't build from it. |
| 18 | Score grid works with 3 and 5 components, phone and desktop | Pass | `ScoreGridV5` (CA1, CA2, Exam) and `ScoreGridSS` (CA1, CA2, CA3, Project, Exam). |
| 19 | Students needing attention never reachable from parent or student screens | Pass | No parent or student board links to it. |
| 20 | Report ID, revision, date and QR always on in the template editor | Pass | Locked "Always shown" rows with a lock icon. |
| 21 | Full colour picker with contrast warning | Pass | Create school and Template settings, Accent colour. |
| 22 | School type and report card toggles only for the super admin | Pass | Create school and School detail Features. School admins see levels read-only (`BsaMenus` section 4). |
| 23 | Skills report card and rating sheet: no totals, grades or positions, ratings as word or code | Pass | Checked on `RatingSheet`, `ReportSkillsEY`, `ReportSkillsModern` and `ParentSkills`. |
| 24 | Assistants never see a Submit button | Pass | Checked in the rendered page for Rating sheet (Assistant) and My class (Assistant, both variants, every tab). |
| 25 | Head's title changes the comment and signature labels | Pass | Template editor preview, and the Primary 4A card says "Head teacher's comment". |
| 26 | NAVIGATION_AND_SETTINGS.md updated with every new label | Pass, waiting on you | Screen files are filled in. Section 5 lists every proposed label for your sign-off. |

## Other gaps found

- **Header theme toggle:** the nav file asks for a theme toggle (Light, Dark, System) in every desktop header. Only some v0.5 headers draw it. **Fix:** in the build, it belongs to the shared header component.
- **Students menu item:** "Students" in the sidebar opens Student detail (Chukwuemeka Obi) because the Students list is not designed yet.
- **Shared Greenfield screens:** Dashboard, Publish results and Billing exist only for Greenfield. The Bright Stars shell links to the Greenfield versions.
- **Halima Garba's scores:** her Mathematics score was changed to 39 on Score entry, My class and Publish so they agree with Section 12. Her average stays 46.2.
