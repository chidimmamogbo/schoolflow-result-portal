# ACCEPTANCE_TESTS.md: the demo flow as testable cases

Phase 6 of `docs/BUILD_PROMPT.md`. Each of the 38 demo steps in `docs/SPEC.md` section 16 becomes one or more **given / when / then** cases. In Phase 7 and 8 each case becomes an automated test (API tests with pytest, then Playwright end to end at phone, tablet and desktop sizes in light and dark). Started 2026-10-12.

## How to read this file

- **ID:** `AT-<demo step>.<n>`. A case with **(denied)** checks that something is refused; the build prompt requires at least one for anything touching security, tenants, accounts or data.
- **Covers:** the SPEC acceptance criteria (`AC..`) and decisions (`D-..`) the case proves.
- **Data:** all fictional, from design brief section 12. Session 2026/2027, First Term.
- **"Generic error":** the one login error text, the same for every failure (D-034).
- Unless a case says otherwise, "denied" means the API answers 403 (or 404 when the record belongs to another school, D-047) and nothing changes in the database or the audit log, except a denied-attempt audit entry where the spec asks for one.

### Fixtures (seeded for every end-to-end run)

| Name | What |
|---|---|
| Super admin | `platform.admin`, created by the seed command |
| School A | Greenfield Model College, code GMC, Secondary only, colour #1E6B45, all features on, Standard plan |
| School B | Bright Stars Academy, code BSA, Nursery and Primary, Correction queue off, free pilot |
| School C | Royal Crest Schools, code RCS, Nursery, Primary and Secondary |
| GMC departments | Sciences: Mathematics, Basic Science, Basic Technology, Agricultural Science, Computer Studies |
| GMC people | Principal Ngozi Okeke (`ngozi.okeke`); vice principal Chukwudi Eze (`chukwudi.eze`); reviewer Emeka Nwosu (Sciences); teacher Tunde Adebayo (`tunde.adebayo`, Mathematics JSS 1A and 1B, form teacher JSS 1A); parent Ikenna Obi (wards Chukwuemeka Obi JSS 1A, Adaeze Obi JSS 3A) |
| GMC students | JSS 1A list in design brief section 12; Chukwuemeka Obi is GMC/2026/014 |
| BSA people | Head teacher Chiamaka Nwafor; Primary 4A class teacher Ifeoma Chukwu, assistant Ngozi Ani; Nursery 2 class teacher Amaka Udeh |
| Shared admission number | One BSA pupil is also given admission number 2026/014, to prove the two schools never mix (AC02.6) |

---

## Part 1: schools, accounts and setup (demo steps 1 to 12)

### Step 1. Super admin creates School A (Secondary only)

**AT-01.1 Create school with the full form**
- Given the super admin is logged in
- When they submit Create school with name Greenfield Model College, school type Secondary only, code GMC, colour #1E6B45, all features on, billing on, and principal Ngozi Okeke (`ngozi.okeke`, email, login method activation email)
- Then the school exists with status Active, Junior and Senior Secondary report cards on and Nursery and Primary off; the principal's membership has `is_primary` true; the platform audit log records the creation
- And two emails are queued: the principal's activation email and the school's set-up confirmation. **Neither contains a password**; the activation link's token is stored only as a hash
- Covers: F01, F03 rule 1, F25, D-039, BUILD_PROMPT "Create school queues the principal's activation email and the set-up email"

**AT-01.2 (denied) Duplicate school code**
- Given GMC exists
- When the super admin creates another school with code GMC (or `gmc`)
- Then it is rejected with a field error on School code and nothing is created
- Covers: BUILD_PROMPT "Create school rejects a duplicate school code"

**AT-01.3 (denied) Only the super admin creates schools**
- Given Ngozi Okeke (school admin) is logged in
- When she calls the create-school endpoint directly
- Then it is denied
- Covers: F01, AC03.2 in spirit, D-047

**AT-01.4 Colour contrast warning**
- Given the Create school form
- When a colour with contrast below 4.5 against white is picked
- Then a contrast warning shows (the school can still be saved)
- Covers: design brief 10.6, UI_REVIEW checklist item 5

### Step 2. Super admin creates School B (Nursery and Primary)

**AT-02.1 School type preset**
- Given the super admin is logged in
- When they create Bright Stars Academy (BSA) with school type Nursery and Primary, Correction queue off, billing as free pilot
- Then Nursery and Primary report cards are on and Secondary is off; Nursery's assessment mode is Skill ratings and Primary's is Scores; Primary's grading defaults to A to F
- Covers: F25, F08 rule 0 and 5, AC25 (presets)

**AT-02.2 (denied) At least one level stays on**
- Given BSA with Nursery and Primary on
- When the super admin turns both off
- Then the second change is rejected with a clear message
- Covers: BUILD_PROMPT "at least one level must stay on"

**AT-02.3 (denied) Only the super admin switches levels**
- Given Chiamaka Nwafor (BSA head teacher) is logged in
- When she calls the endpoint to turn Secondary on
- Then it is denied and the toggle is read-only in her screens
- Covers: Non-negotiable rule "Only the super admin switches report card levels"

### Step 3. Super admin creates School C (all levels)

**AT-03.1**
- Given the super admin is logged in
- When they create Royal Crest Schools (RCS) with school type Nursery, Primary and Secondary
- Then all three levels are on with their default modes (Nursery Skill ratings, others Scores)
- Covers: F25

### Step 4. Disabled features and levels are rejected on the server

**AT-04.1 (denied) Correction queue off**
- Given BSA has Correction queue off and a BSA parent with a published result
- When the parent submits a correction request through the API
- Then it is rejected, and no Corrections menu item or "Report a problem" link shows
- Covers: Non-negotiable "A disabled feature's endpoints reject requests", F01

**AT-04.2 (denied) Level off rejects classes, templates and structures**
- Given BSA has Secondary off
- When the head teacher creates a JSS 1 class, a Junior Secondary template or a Junior Secondary assessment structure
- Then each is rejected
- Covers: AC04.2, BUILD_PROMPT "a level that is off rejects classes, templates and structures"

**AT-04.3 Turning a level off keeps old reports**
- Given RCS has a published Nursery 2 report
- When the super admin turns Nursery off (after the confirmation dialog)
- Then the report stays viewable to its parent and still verifies as VALID; the school type shows Custom
- Covers: BUILD_PROMPT "turning a level off keeps published reports viewable and verifiable", design flow 17

### Step 5. No registration anywhere

**AT-05.1 (denied) No register route**
- Given any visitor, signed in or not
- When they open `/register`, `/signup`, `/api/v1/auth/register` or `/api/v1/auth/signup`
- Then each answers 404 (not found), and no page shows a sign-up link
- Covers: AC02.1, F02 rule 10, Non-negotiable "No public registration"

### Step 6. Principal activates and adds a vice principal

**AT-06.1 Activation**
- Given Ngozi Okeke's activation email from AT-01.1
- When she opens the link within 72 hours and sets a password of at least 15 characters that is not on the common-password list
- Then the account is active, she is logged in, and the link no longer works
- Covers: F03, D-036, D-039

**AT-06.2 (denied) Used, expired or tampered link**
- Given an activation link that was used, is older than 72 hours, or has one character changed
- When it is opened
- Then the expired-link state shows ("Ask your school admin") and no password can be set
- Covers: AC02.3, BUILD_PROMPT "Activation links and reset links are single use and expire"

**AT-06.3 (denied) Weak password**
- Given the activation form
- When she enters a 14-character password, or a common one such as `password1234567`
- Then it is rejected with the rule shown; nothing is saved
- Covers: D-036

**AT-06.4 Add an additional school admin**
- Given Ngozi Okeke (principal) is logged in
- When she adds Chukwudi Eze as a school admin with the temporary-password method
- Then he is created in GMC only, with `must_change_password` true, and the "Staff login slip" shows the temporary password once
- Covers: F03 rule 2, D-040

**AT-06.5 (denied) Admin limit**
- Given GMC already has 2 additional school admins
- When the principal adds a third
- Then it is refused with "You can add up to 2 school admins."
- Covers: AC03.4

**AT-06.6 (denied) Additional admins cannot manage admins**
- Given Chukwudi Eze (additional admin) is logged in
- When he tries to add, remove or reset a school admin (including the principal), by screen or API
- Then it is denied; the School admins page shows "Only the principal can manage school admins."
- Covers: AC03.1, Non-negotiable "Additional school admins cannot add, remove or reset other admins"

**AT-06.7 (denied) Never create your own level or above**
- Given any school admin
- When they try to create a super admin, or a school admin in another school
- Then it is denied
- Covers: BUILD_PROMPT "A school admin cannot create a school admin or super admin", AC03.2, D-048

### Step 7. Assessment structures and pass mark

**AT-07.1 Senior Secondary five components**
- Given the principal opens Assessment structure for Senior Secondary
- When she sets CA1 10, CA2 10, CA3 10, Project 10, Exam 60 (total 100) and saves
- Then it is saved; the Senior Secondary score grid shows exactly those five columns in that order
- Covers: F08 rules 1 and 2, BUILD_PROMPT "the grid shows the level's columns"

**AT-07.2 Junior Secondary default kept**
- Given the default structure
- When the principal leaves Junior Secondary unchanged
- Then the JSS grid shows CA1 /20, CA2 /20, Exam /60

**AT-07.3 (denied) Total not 100**
- Given the Senior Secondary editor
- When the maximums add up to 95 or 105, or there are 0 or 9 components
- Then saving is rejected by the API (not only the screen) with the matching message
- Covers: F08 rule 1, BUILD_PROMPT "a structure that does not add up to 100 is rejected"

**AT-07.4 (denied) Locked once scores exist**
- Given one score exists for First Term at Junior Secondary
- When the principal edits the Junior Secondary structure
- Then the change is saved for Second Term only; First Term keeps its structure, and each result stores the structure it used
- Covers: AC08.3, F08 rule 3

**AT-07.5 Pass mark**
- Given the grading page
- When the principal sets the pass mark to 40
- Then it saves; 0, 100 or 40.5 are rejected with "Pass mark must be a whole number from 1 to 99."
- Covers: F08 rule 4, section 12 (whole number 1 to 99)

**AT-07.6 Default grading**
- Given a new school
- When the grading bands are opened
- Then Secondary shows A1 75 to 100 … F9 0 to 39 and Primary shows A to F; a Primary total of 65 grades **B, Very good**
- Covers: F08 rule 5, D-135, BUILD_PROMPT "Primary defaults to A to F grading (65 is B); Secondary defaults to A1 to F9"

### Step 8. Registering people

**AT-08.1 Teacher with assignments**
- Given the principal is logged in
- When she registers Tunde Adebayo (username suggested `tunde.adebayo`, availability checked) with Mathematics for JSS 1A and JSS 1B and form teacher of JSS 1A, login method activation email
- Then he is created in GMC with those assignments and an activation email is queued (no password in it)
- Covers: F06, F03 rule 4

**AT-08.2 (denied) Username taken**
- Given `tunde.adebayo` exists anywhere on the platform
- When another staff account uses it
- Then the availability check and the API both reject it
- Covers: SPEC section 4 usernames

**AT-08.3 Reviewer with scope**
- Given the principal is logged in
- When she registers Emeka Nwosu as reviewer for the Sciences department
- Then his scope is Sciences only

**AT-08.4 Students by CSV**
- Given a valid JSS 1A CSV of 12 students
- When the principal uploads, previews and commits it
- Then 12 students are enrolled in JSS 1A with the class's subjects
- Covers: F05

**AT-08.5 (denied) One bad row commits nothing**
- Given a CSV where one row repeats admission number GMC/2026/014
- When the principal commits
- Then nothing is saved; the preview shows the row error and the commit button stays off
- Covers: AC05.1, BUILD_PROMPT "A CSV import with one bad row commits nothing"

**AT-08.6 Subjects per student**
- Given Musa Ibrahim does not take Igbo Language
- When the Igbo Language sheet for JSS 1A is opened
- Then Musa is not listed
- Covers: AC05.2

**AT-08.7 Parent linked to two wards**
- Given the principal registers Ikenna Obi
- When she links Chukwuemeka Obi (JSS 1A) and Adaeze Obi (JSS 3A)
- Then his account shows both wards and nobody else
- Covers: F07

**AT-08.8 (denied) Cross-school creation**
- Given Ngozi Okeke (GMC)
- When she calls the API to create a student, teacher or parent with BSA's school ID
- Then it is denied and nothing is created in BSA
- Covers: AC03.2, BUILD_PROMPT "A school admin cannot create users in another school"

### Step 9. First logins

**AT-09.1 Teacher activates and logs in by username or email**
- Given Tunde Adebayo activated his account
- When he logs in on Staff and parents with `tunde.adebayo`, and again with his email
- Then both work
- Covers: AC02.5

**AT-09.2 Student logs in with school code and a temporary password**
- Given Chukwuemeka Obi has a temporary password from a printed slip
- When he logs in on the Student tab with school code GMC, admission number GMC/2026/014 and the temporary password
- Then he is sent to Change password and cannot open any other page until he sets a new one (at least 10 characters)
- Covers: AC02.2, D-036, D-040, BUILD_PROMPT "temporary passwords force a change at first login"

**AT-09.3 Two schools, same admission number**
- Given GMC and BSA each have a student with admission number 2026/014
- When a student logs in with school code GMC and 2026/014
- Then only GMC's student can be matched
- Covers: AC02.6

**AT-09.4 (denied) Generic error**
- Given the Student tab
- When the school code, the admission number or the password is wrong (three separate tries)
- Then the same generic error shows each time, in the same time range, and the response never says which part was wrong
- Covers: AC02.7, D-034

**AT-09.5 (denied) Throttling**
- Given repeated failed logins for one identifier
- When the limit is passed
- Then further attempts are delayed or refused for a while, even with the right password
- Covers: AC02.4, D-042

**AT-09.6 Login link**
- Given `/login/GMC`
- When it is opened
- Then the Student tab shows with GMC filled in and Greenfield's name and logo; an unknown code shows the plain login page without saying the code does not exist
- Covers: F02 rule 2

### Step 10. Teacher finds a student and enters marks

**AT-10.1 Only assigned sheets**
- Given Tunde Adebayo is logged in
- When he opens Result sheets
- Then he sees Mathematics JSS 1A and JSS 1B (plus his form class tools) and no other sheet
- Covers: BUILD_PROMPT "A teacher sees only sheets for their assigned subjects and classes"

**AT-10.2 (denied) Unassigned sheet by ID**
- Given the ID of the English JSS 1A sheet
- When Tunde opens it by URL or API
- Then it is denied
- Covers: F09, D-047

**AT-10.3 Search**
- Given the Mathematics JSS 1A sheet
- When he searches "Zainab" and then "GMC/2026/014"
- Then the grid shows Zainab Yusuf, then Chukwuemeka Obi
- Covers: BUILD_PROMPT "Teacher sheet search finds a student by name or admission number"

**AT-10.4 Enter marks**
- Given the sheet
- When he enters CA1 16, CA2 15, Exam 47 for Chukwuemeka Obi
- Then the total shows 78; the scores are saved as a draft with his name in the audit timeline
- Covers: F09, F11

### Step 11. Validation catches problems

**AT-11.1 (denied) Missing and out-of-range**
- Given Musa Ibrahim's CA2 is empty and Zainab Yusuf's Exam is 72 (maximum 60)
- When Tunde submits the sheet
- Then submission is blocked; the grid flags both cells; the Missing and Errors chips show 1 each; the API rejects a direct submit too
- Covers: F09, BUILD_PROMPT "Missing and out-of-range scores block submission"

**AT-11.2 (denied) Out-of-range through the API**
- Given the scores endpoint
- When a score of -1, 61 (Exam) or 15.5 where whole numbers are required is sent
- Then it is rejected and nothing is stored

### Step 12. Fix and submit

**AT-12.1 Submit**
- Given both problems are fixed
- When Tunde submits Mathematics JSS 1A
- Then the sheet status is Submitted, it is locked to him, it appears in Emeka Nwosu's review queue (the fixture puts Mathematics in the Sciences department), and the audit timeline records the submission
- Covers: F10

**AT-12.2 (denied) Edit after submit**
- Given the sheet is Submitted
- When Tunde changes a score through the API
- Then it is denied
- Covers: F10 rules ("submitted and approved sheets are locked to teachers")

---

## Part 2: review to publication (demo steps 13 to 24)

### Step 13. Reviewer returns a score

**AT-13.1 Return with a comment**
- Given Mathematics JSS 1A is Submitted and Emeka Nwosu (Sciences) is logged in
- When he opens it from his review queue and returns it with "Please check Tobi Adeyemi's CA2. The paper shows 14, not 4."
- Then the status is Returned for correction, Tunde sees the comment highlighted on his sheet card, and the audit timeline records the return
- Covers: F10, section 8 (SUBMITTED to RETURNED_FOR_CORRECTION)

**AT-13.2 (denied) Return without a comment**
- Given the same sheet
- When Emeka returns it with an empty comment
- Then the API rejects it
- Covers: section 8 ("comment required")

**AT-13.3 (denied) Reviewer cannot change scores**
- Given Emeka is reviewing the sheet
- When he sends a score change through the API
- Then it is denied and no score changes
- Covers: AC10.2, BUILD_PROMPT "a reviewer cannot silently change scores"

**AT-13.4 (denied) Out of scope**
- Given English JSS 1A is Submitted (not in Sciences)
- When Emeka opens or returns it by ID
- Then it is denied, and it never appears in his queue
- Covers: BUILD_PROMPT "a reviewer only their scope", D-049

### Step 14. Teacher corrects with a reason; reviewer marks reviewed

**AT-14.1 Changed scores need a reason**
- Given the sheet is Returned
- When Tunde changes Tobi Adeyemi's CA2 from 4 to 14 without a reason
- Then the change is rejected; with the reason "Corrected transcription error" it saves, and the audit timeline shows old 4, new 14, the reason and his name
- Covers: section 8 (changed scores need reasons), F11

**AT-14.2 Resubmit and mark reviewed**
- Given the correction is saved
- When Tunde resubmits and Emeka marks it reviewed
- Then the status goes Resubmitted, then Reviewed

**AT-14.3 (denied) Separation of duties**
- Given a school admin who also teaches submitted a sheet
- When the same person tries to review or approve that sheet
- Then it is denied
- Covers: AC10.1, D-052, BUILD_PROMPT "A teacher cannot approve their own sheet"

### Step 15. Form teacher completes My class

**AT-15.1 Broadsheet**
- Given Tunde is form teacher of JSS 1A
- When he opens My class
- Then the broadsheet lists every JSS 1A student against every JSS 1A subject with each sheet's status
- Covers: F22 rules 1 and 2

**AT-15.2 (denied) Not a form teacher, or another class**
- Given Grace Etim (not a form teacher), and separately Tunde asking for the JSS 1B broadsheet
- When each opens My class or requests that broadsheet
- Then My class is not available to Grace, and Tunde's JSS 1B request is denied
- Covers: AC22.1, AC22.2, BUILD_PROMPT "Only the form teacher of a class can open its My class area"

**AT-15.3 Student entries**
- Given Chukwuemeka Obi's entry
- When Tunde writes "A focused and respectful student. Keep it up in Mathematics.", rates Punctuality 5, Neatness 4, Politeness 5, Handwriting 4, Games and sports 3, and sets times school opened 60 and present 57
- Then it saves and the preview shows times absent 3
- Covers: F22 rules 3 to 5, AC22.3

**AT-15.4 (denied) Bad entries**
- Given the same form
- When times present is 61 (more than 60 opened), a rating is 6, or the comment is 301 characters
- Then the API rejects each one
- Covers: AC22.4, F22 rule 3, BUILD_PROMPT "times present cannot exceed times school opened"

**AT-15.5 Preview and submit**
- Given every student's entry is complete
- When Tunde previews a report card and submits the class sections
- Then the preview carries "Preview, not published"; the sections become Submitted and locked to him
- Covers: F22 rules 6 and 9

### Step 16. Principal approves and publishes

**AT-16.1 (denied) Publishing blocked until ready**
- Given one JSS 1A subject sheet is not Approved, or the class sections are not Submitted while the template shows comments
- When the principal publishes JSS 1A
- Then it is blocked with the reason (for example "Form teacher comments are not submitted")
- Covers: AC10.3, section 8 (publication of a class), BUILD_PROMPT "publishing is blocked until required class sections are submitted"

**AT-16.2 Approve, comment, publish**
- Given every sheet is Reviewed and the sections are Submitted
- When the principal approves each sheet, adds principal's comments (using "Apply to {n} students", which keeps comments already written) and publishes JSS 1A for First Term
- Then each student gets a report at revision 1, VALID, with a report ID such as GMC-2627-T1-JSS1A-014 and a verification code; the snapshot (scores, structure, grading bands, template version, calculation version) is frozen
- Covers: F10, F12 rule 5, F13, D-058

**AT-16.3 (denied) Published means immutable**
- Given a published report
- When the application's database role tries to update or delete its snapshot or a published score
- Then the database refuses it
- Covers: AC11.1, Non-negotiable "Published results are immutable"

**AT-16.4 Positions with ties**
- Given two students with the same Mathematics total
- When the class is published
- Then both show the same position and the next is skipped ("1st, 1st, 3rd")
- Covers: F08 rule 7

### Step 17. Notices and emails after publishing

**AT-17.1 Right audience only**
- Given JSS 1A is published
- When the boards are opened
- Then "First Term results for JSS 1 are now available" shows for JSS 1A students, their guardians (Ikenna Obi), and JSS 1A's teachers and reviewers, and not for a JSS 2 parent
- Covers: F17, AC17.1, BUILD_PROMPT "Publishing results creates notices for the right audience only"

**AT-17.2 Email with no scores**
- Given the same publication
- When the outbox is inspected
- Then each intended recipient with an email has exactly one queued message with a message and a login link, and no score, grade, position or password
- Covers: AC18.1, Non-negotiable "Emails never contain scores"

**AT-17.3 No email, still notified**
- Given a JSS 1A student without an email
- When they log in
- Then the notice is on their board with an unread badge
- Covers: F18, BUILD_PROMPT "Users without email still see the result notice"

**AT-17.4 (denied) Other schools never see it**
- Given any BSA user
- When they open their board or request the GMC notice by ID
- Then it is not shown, and the request is denied
- Covers: AC17.2, BUILD_PROMPT "Notices from School A never appear for School B users"

**AT-17.5 Daily cap**
- Given the outbox already sent 95 emails today
- When more are queued
- Then they stay Queued until the next day, account emails first; nothing is dropped
- Covers: F18, D-082

### Step 18. Students needing attention

**AT-18.1 Built from published results**
- Given the pass mark is 40 and Musa Ibrahim scored 38 in Mathematics
- When JSS 1A is published
- Then By subject lists Musa, Mathematics, 38, F9; By student lists Daniel Okon with "Average below pass mark"
- Covers: AC23.1, F23 rules 1 to 3

**AT-18.2 Scoped by role**
- Given the principal filters to JSS 1A; Tunde (Mathematics JSS 1A and 1B, form teacher JSS 1A) and Emeka (Sciences) open their lists
- Then the principal sees every JSS 1A subject; Tunde sees all JSS 1A subjects plus Mathematics JSS 1B; Emeka sees only Sciences subjects
- Covers: AC23.2, AC23.3, F23 rule 5

**AT-18.3 (denied) Parents and students**
- Given Ikenna Obi or Chukwuemeka Obi is logged in
- When they request the list or its CSV by URL or API
- Then it is denied, and no menu item shows
- Covers: AC23.4, BUILD_PROMPT "parents and students are denied"

**AT-18.4 (denied) Not before publication**
- Given JSS 1B sheets are approved but not published
- When the list is opened
- Then no JSS 1B results are included, and the "not published yet" message shows
- Covers: AC23.5

**AT-18.5 Export**
- Given the principal's filtered list
- When she exports CSV and opens the print view
- Then both contain exactly the filtered rows

### Step 19. The PDF

**AT-19.1 Branded PDF**
- Given Chukwuemeka Obi's published report and GMC's Modern template
- When the PDF is generated
- Then it uses the template version it was published with, in the light print design, with the school colour and logo, and shows the report ID, revision, publication date and QR code
- Covers: F12, D-058 (regenerated from the snapshot)

**AT-19.2 (denied) Report ID and QR cannot be hidden**
- Given the template editor
- When the principal tries to hide the report ID, revision, date or QR in any template, by screen or API
- Then the controls are locked and the API rejects it
- Covers: AC12.3, BUILD_PROMPT "Report ID, revision, date and QR cannot be hidden in any template"

**AT-19.3 Same PDF every time**
- Given the same report
- When it is generated twice
- Then the two files are identical
- Covers: D-067

**AT-19.4 Real formats reproduce**
- Given an Ogun-style JSS template (CA and exam, traits on a 5 to 1 grid with key, marks obtainable, position) and an FCT-style primary template (class average, highest, lowest, position, remarks, next term)
- When each is previewed with seeded data
- Then both layouts are reproduced using only block switches
- Covers: AC12.1, D-135

### Step 20. Parent on a phone, dark mode

**AT-20.1**
- Given Ikenna Obi on a 360px-wide phone in dark mode
- When he opens Chukwuemeka's report and downloads the PDF
- Then the online view is dark and readable with nothing scrolling sideways; the PDF is the light print card
- Covers: F14, F20, Non-negotiable "PDFs and print are always light"

**AT-20.2 (denied) Not before publication**
- Given a sheet that is Approved but not Published
- When the parent views results
- Then it is not shown
- Covers: AC14.1

### Step 21. Verification: VALID

**AT-21.1**
- Given the QR on Chukwuemeka's PDF
- When it is scanned (opening `/verify/{code}`)
- Then the page shows VALID, Greenfield Model College, "Chuk\*\*\* O.", 2026/2027, First Term, revision 1, publication date, and no scores; the response is not cached and not indexed
- Covers: F13, D-071 to D-073

**AT-21.2 (denied) Guessing codes**
- Given the verify endpoint
- When many random codes are tried quickly
- Then lookups are rate limited and an unknown code shows "not found" without detail
- Covers: F13 ("lookups are rate limited")

### Step 22. Parent submits a correction

**AT-22.1**
- Given GMC has Correction queue on
- When Ikenna reports a problem on Chukwuemeka's Basic Science result, with an issue type, an explanation and an image attachment
- Then a ticket is Open, the principal sees it in Corrections, and Ikenna sees its status timeline
- Covers: F15

**AT-22.2 (denied) Bad attachment, other child**
- Given the form
- When he attaches an SVG or a file over the size limit, or reports on a student who is not his ward
- Then each is rejected
- Covers: F15 (validated attachment), D-057

### Step 23. Reopen, new revision, republish

**AT-23.1**
- Given the ticket is Investigating
- When the principal reopens Basic Science JSS 1A with the reason "Exam script re-marked" and the ticket linked; the teacher fixes the score; it goes through review and approval again; JSS 1A is republished
- Then Chukwuemeka's report is revision 2, VALID; the ticket shows the linked revision; Students needing attention is rebuilt from revision 2
- Covers: F10, AC15.1, F23 rule 1

**AT-23.2 (denied) Reopen without a reason**
- When the principal reopens with an empty reason
- Then it is rejected

### Step 24. Old version shows SUPERSEDED

**AT-24.1**
- Given revision 1's QR code
- When it is verified
- Then the page shows SUPERSEDED with "A newer version exists"
- Covers: AC13.1, BUILD_PROMPT "verification shows the old one as SUPERSEDED"

**AT-24.2 Revoked**
- Given the principal revokes a report with a reason
- When its code is verified
- Then the page shows REVOKED
- Covers: section 8 (report document), BUILD_PROMPT "A revoked report shows REVOKED"

## Part 3: audit, security, nursery and primary, billing (demo steps 25 to 38)

### Step 25. The audit timeline explains everything

**AT-25.1**
- Given the steps above have run
- When the principal opens the school audit trail filtered to Chukwuemeka Obi
- Then it lists, in order, with actor, role, time, old and new value and reason: account creation, enrolment, every score entry and change (including Tobi's 4 to 14 with its reason, on Tobi's filter), the return, review, approval, the form teacher's entries, publication, the correction ticket, the reopen and revision 2
- Covers: F11, BUILD_PROMPT "Every score change, account creation and notice edit appears in the audit timeline"

**AT-25.2 Notice edits are audited**
- Given a pinned notice
- When the principal edits or archives it
- Then the audit trail records it

**AT-25.3 (denied) Audit is append-only**
- Given an audit event
- When the application's database role tries to update or delete it
- Then the database refuses it
- Covers: F11

### Step 26. Parent tries another child's result

**AT-26.1 (denied) ID swap**
- Given Ikenna Obi is linked to Chukwuemeka and Adaeze only
- When he changes the report or student ID in the URL or API to Tobi Adeyemi's
- Then it is denied (404) and nothing about Tobi is shown
- Covers: BUILD_PROMPT "A guardian sees only linked wards", D-047

**AT-26.2 Unlinking removes access at once**
- Given the principal unlinks Adaeze from Ikenna
- When Ikenna's next request for Adaeze's report arrives, in the same session
- Then it is denied
- Covers: BUILD_PROMPT "unlinking a ward removes access immediately"

**AT-26.3 (denied) Student sees only self**
- Given Chukwuemeka is logged in
- When he requests Tobi's report by ID, or his own unpublished result
- Then both are denied
- Covers: BUILD_PROMPT "A student sees only their own published results"

### Step 27. Another school's user tries a School A ID

**AT-27.1 (denied) Cross-school**
- Given Chiamaka Nwafor (BSA) is logged in
- When she requests a GMC student, sheet, report, notice, invoice or audit event by ID
- Then each answers 404, and row-level security returns no rows even if the application check were skipped (tested directly against the database with BSA's school context)
- Covers: D-047, D-051, Non-negotiable "every query is tenant-scoped; row-level security is on"

**AT-27.2 (denied) Disabled results feature**
- Given a school with the Results feature switched off and a valid login
- When its users call results endpoints
- Then every one is rejected
- Covers: BUILD_PROMPT "School B (results disabled) gets rejected by results endpoints even with a valid login"

### Step 28. Student forgot password

**AT-28.1 No self-service for students**
- Given the Student tab
- When it is shown
- Then there is no forgot password link, only "Forgot your password? Ask your school admin for a new one."
- Covers: F02 rule 8

**AT-28.2 (denied) Forgot password never sends for a student**
- Given the forgot password endpoint
- When it is called with a student's username or admission number
- Then no email is queued and the response is identical to any other request
- Covers: AC02.8

**AT-28.3 Admin issues a new temporary password**
- Given the principal opens Chukwuemeka's Login support
- When she issues a new temporary password
- Then a "Student login slip" shows it once, ready to print; his other sessions end; he must change it at next login; the audit trail records the action without the password
- Covers: F03 rule 6, D-040

### Step 29. The principal lost their login

**AT-29.1 Super admin login support**
- Given the super admin opens GMC > School admins
- When they change Ngozi Okeke's email and send a reset link (with "Also sign out of all devices" checked)
- Then her other sessions end, the reset email goes to the new address with a link valid for 1 hour, and the platform audit log records it; the super admin never sees a password
- Covers: AC03.5, D-041

**AT-29.2 (denied) Super admin cannot reset other roles**
- Given the super admin
- When they try to reset a teacher's, parent's or student's password
- Then it is denied
- Covers: AC03.6

**AT-29.3 (denied) No impersonation**
- Given the super admin
- When they look for any "log in as" action or endpoint
- Then none exists
- Covers: SPEC section 4

**AT-29.4 Reset link is single use and signs out other sessions**
- Given Ngozi uses the reset link
- When she sets a new password
- Then the link no longer works, every other session ends, and a "your password was changed" email is queued
- Covers: F02 rule 9, AC02.3

### Step 30. Bright Stars setup: Nursery on Skill ratings, Primary on Scores

**AT-30.1**
- Given Chiamaka Nwafor (BSA head teacher)
- When she keeps Nursery on Skill ratings with the default learning areas (including Pre-science and Handwriting) and the five-point scale, and Primary on Scores with A to F
- Then the Nursery rating sheets and Primary score sheets are created to match
- Covers: F26 rules 1 and 2, F08 rule 0, D-135

**AT-30.2 (denied) Mode locks per term**
- Given ratings exist for First Term at Nursery
- When she switches Nursery to Scores
- Then the change applies from Second Term only
- Covers: AC08.6, BUILD_PROMPT "the choice locks per term once entries exist"

### Step 31. Class teacher with Teaches all subjects, and an assistant

**AT-31.1 Teaches all subjects**
- Given Primary 4A
- When the head teacher makes Ifeoma Chukwu class teacher with Teaches all subjects, then adds a new subject to Primary 4A
- Then Ifeoma has every Primary 4A subject, including the new one
- Covers: F06, BUILD_PROMPT "Teaches all subjects gives a class teacher every subject of the arm, including subjects added later"

**AT-31.2 Assistant enters but cannot submit**
- Given Ngozi Ani is assistant for Primary 4A
- When she enters scores and saves
- Then they save with her name in the audit trail; no Submit button shows; a submit request through the API is denied
- Covers: AC06.3, Non-negotiable "Class teacher assistants can enter but never submit"

**AT-31.3 (denied) Third assistant**
- Given Primary 4A has 2 assistants
- When a third is added
- Then it is refused with "Primary 4A has 2 assistants. Remove one to add another."
- Covers: F06 rule 3

### Step 32. Nursery and Primary results are published

**AT-32.1 (denied) Unrated skill blocks submission**
- Given Hauwa Sani has no rating for "Counts 1 to 20"
- When Amaka Udeh submits the Number work sheet for Nursery 2
- Then it is blocked with the skill highlighted
- Covers: AC26.2

**AT-32.2 Both classes publish**
- Given every Nursery 2 skill is rated (Hauwa: Counts 1 to 20 Needs improvement) and Primary 4A is complete
- When the head teacher approves and publishes both
- Then Nursery 2 pupils get Skills report cards and Primary 4A pupils get Score report cards, each with its level's template and "Head teacher's comment"
- Covers: AC12.4

### Step 33. Parents open the two kinds of report card

**AT-33.1 Skills report card**
- Given a Nursery 2 parent
- When they open Chidera Okeke's report and PDF
- Then it shows learning areas, each skill's rating word, the rating key, comments and "Head teacher's comment", in the Early Years style, with **no totals, grades, averages or positions**
- Covers: AC26.3, BUILD_PROMPT "a Skills report card shows ratings and the key and never totals, grades or positions"

**AT-33.2 Primary Score report card**
- Given a Primary 4A parent
- When they open Kamsi Okafor's report
- Then Mathematics shows 65, B, Very good
- Covers: F08 rule 5

**AT-33.3 Old reports keep their scale**
- Given BSA renames "Fair" to "Satisfactory" after publication
- When Chidera's published report is opened
- Then it still shows "Fair"
- Covers: AC26.4

### Step 34. Students needing attention at Bright Stars

**AT-34.1**
- Given both classes are published and Primary's pass mark is 40
- When the head teacher opens the list
- Then By learning area shows Hauwa Sani, Nursery 2, Number work, Counts 1 to 20, Needs improvement; By subject shows Primary 4A scores below 40
- Covers: AC23.6, F23 rule 8, BUILD_PROMPT "shows skills at or below the attention rating"

### Step 35. Super admin edits pricing

**AT-35.1 New version, price check**
- Given the default plans (Basic 1 to 499 at ₦1,000; Standard 500 to 1,000 at ₦500; Premium 1,001 and above at ₦300) with cliff protection on
- When the super admin opens the pricing editor, edits a price and saves
- Then the price check lists 251 to 499 and 601 to 1,000 students; the save creates a new pricing version; the platform audit log records it
- Covers: AC19.4, F19, BUILD_PROMPT "The price check lists 251 to 499 and 601 to 1,000 students"

**AT-35.2 (denied) Overlaps and gaps**
- Given the editor
- When plans overlap (Basic to 520) or leave a gap (Standard from 510)
- Then the save is rejected
- Covers: AC19.1

**AT-35.3 (denied) Only the super admin**
- Given any school admin
- When they call the pricing endpoints
- Then it is denied
- Covers: Non-negotiable "Only the super admin changes pricing"

### Step 36. Invoices

**AT-36.1 Amounts with cliff protection off**
- Given cliff protection off
- When invoices are generated for 499, 500, 1,000 and 1,001 billable students
- Then the amounts are ₦499,000; ₦250,000; ₦500,000; ₦300,300
- Covers: AC19.2

**AT-36.2 Amounts with cliff protection on**
- Given cliff protection on
- When invoices are generated for 499, 580, 642, 1,000 and 1,001 billable students
- Then the amounts are ₦250,000 (capped); ₦290,000; ₦300,300 (capped); ₦300,300 (capped); ₦300,300, and each capped invoice records that the cap applied
- Covers: AC19.3

**AT-36.3 Issued invoices never change**
- Given GMC's Second Term invoice (580 × ₦500 = ₦290,000)
- When pricing changes
- Then the invoice amount stays ₦290,000
- Covers: AC19.5

**AT-36.4 School admin sees own billing only**
- Given Ngozi Okeke
- When she opens Billing
- Then she sees Standard, 580 billable students, ₦290,000 due 5 Jan 2027, renewal date and history; a request for BSA's invoice answers 404
- Covers: F19 rule 10, AC19.8

**AT-36.5 Billing off**
- Given billing is off for BSA (free pilot)
- When its head teacher opens the dashboard
- Then no invoices or payment prompts appear
- Covers: AC19.9

**AT-36.6 Money is integer kobo**
- Given any invoice
- When it is stored and shown
- Then the database holds kobo as an integer and the screen shows ₦290,000

### Step 37. Test payment

**AT-37.1 Paid only after a verified webhook**
- Given the principal clicks Pay now and pays with a Paystack test card
- When she returns to the callback page before the webhook arrives
- Then it shows "Confirming your payment" and the invoice is still UNPAID; when the signed webhook arrives and the server's transaction check confirms amount, currency and reference, the invoice becomes PAID, a numbered receipt is created, a notice is posted to the school admins and a receipt email is queued
- Covers: F19, D-093, D-094, BUILD_PROMPT "the browser redirect alone never marks an invoice paid"

**AT-37.2 (denied) Amount from the browser**
- Given the Pay now request
- When the browser sends a different amount
- Then it is ignored; the amount always comes from the server's invoice
- Covers: Non-negotiable "Payment amounts come from server-side invoices"

**AT-37.3 Same webhook twice**
- Given a valid webhook was processed
- When the same event arrives again
- Then there is still one payment and one receipt
- Covers: AC19.7

### Step 38. Forged webhook

**AT-38.1 (denied)**
- Given an UNPAID invoice
- When a webhook arrives with a bad signature, or a valid signature but a wrong amount or reference
- Then it is rejected, logged, and the invoice stays UNPAID
- Covers: AC19.6

### Across the whole flow

**AT-X.1 Sizes and themes**
- Given the full demo flow
- When it runs at 360px, 768px and 1440px, in light and dark
- Then every step passes, nothing scrolls sideways, and axe finds no WCAG 2.2 AA violations
- Covers: BUILD_PROMPT "The demo flow passes at phone, tablet and desktop sizes, in light and dark mode", D-103, D-104

**AT-X.2 Suspended school**
- Given the super admin suspends RCS with a reason
- When any RCS user logs in
- Then they see "Your school's access is paused"; RCS's published reports still verify
- Covers: BUILD_PROMPT "a suspended school's users see the paused message", D-072

## Part 4: BUILD_PROMPT "must include" coverage

Every item in BUILD_PROMPT Phase 6, with the cases that prove it.

| Must include | Cases |
|---|---|
| No register route; only login | AT-05.1 |
| Email or username login; school code login; same admission number never mixes | AT-09.1, AT-09.2, AT-09.3 |
| Same error for wrong code, username or password | AT-09.4 |
| Forgot password never sends for students; "Ask your school admin" | AT-28.1, AT-28.2 |
| Super admin resets school admins only | AT-29.1, AT-29.2, AT-29.4 |
| Additional admins up to the limit; they cannot add or reset admins | AT-06.4, AT-06.5, AT-06.6 |
| Structure must add up to 100; locked once scores exist; grid shows the level's columns | AT-07.1, AT-07.3, AT-07.4 |
| Sheet search by name or admission number | AT-10.3 |
| Only the form teacher opens My class; present cannot exceed opened; publish blocked until sections submitted | AT-15.2, AT-15.4, AT-16.1 |
| Students needing attention from published results only, scoped, parents and students denied | AT-18.1 to AT-18.4 |
| Duplicate school code rejected; activation and set-up emails without passwords; suspended school sees paused | AT-01.1, AT-01.2, AT-X.2 |
| Report ID, revision, date and QR cannot be hidden | AT-19.2 |
| Presets; only super admin toggles levels; level off rejects; old reports kept; one level stays on | AT-02.1, AT-02.2, AT-02.3, AT-04.2, AT-04.3 |
| Scores or Skill ratings per level, locked per term | AT-30.1, AT-30.2 |
| Primary A to F (65 is B); Secondary A1 to F9 | AT-07.6, AT-33.2 |
| Teaches all subjects incl. later subjects; assistants enter, not submit, entries show their name | AT-31.1, AT-31.2 |
| Unrated skill blocks submission; Skills card has no totals; old reports keep their scale | AT-32.1, AT-33.1, AT-33.3 |
| Attention list shows skills at or below the attention rating | AT-34.1 |
| School admin cannot create a school admin or super admin; super admin creates the school admin | AT-01.1, AT-06.7 |
| School admin cannot create users in another school | AT-08.8 |
| Activation and reset links single use and expiring; temporary passwords force a change | AT-06.2, AT-29.4, AT-09.2 |
| Teacher sees only assigned sheets; reviewer only scope | AT-10.1, AT-10.2, AT-13.4 |
| Guardian sees only linked wards; unlinking removes access at once | AT-26.1, AT-26.2 |
| Student sees only own published results | AT-26.3 |
| Results disabled: rejected even with a valid login | AT-27.2 |
| Teacher cannot approve own sheet; reviewer cannot silently change scores | AT-14.3, AT-13.3 |
| Missing and out-of-range scores block submission | AT-11.1, AT-11.2 |
| CSV import with one bad row commits nothing | AT-08.5 |
| Published results immutable; correction creates a revision; old shows SUPERSEDED | AT-16.3, AT-23.1, AT-24.1 |
| Revoked report shows REVOKED | AT-24.2 |
| Notices to the right audience; emails without scores | AT-17.1, AT-17.2 |
| Users without email still see the notice | AT-17.3 |
| School A notices never appear for School B | AT-17.4 |
| Score changes, account creation and notice edits in the audit timeline | AT-25.1, AT-25.2 |
| Only super admin edits pricing; overlaps and gaps rejected; edits create a version | AT-35.1, AT-35.2, AT-35.3 |
| Existing invoices keep their price | AT-36.3 |
| Invoice amount right at 499, 500, 580, 642, 1,000, 1,001, cliff on and off | AT-36.1, AT-36.2 |
| Price check lists 251 to 499 and 601 to 1,000 | AT-35.1 |
| School admin sees only own billing | AT-36.4 |
| Payment amount cannot be changed from the browser | AT-37.2 |
| Bad signature rejected; repeated webhook makes one payment; redirect never marks paid | AT-38.1, AT-37.3, AT-37.1 |
| Test payment marks PAID, receipt, notice, receipt email | AT-37.1 |
| Billing off: no invoices or prompts | AT-36.5 |
| Demo passes at phone, tablet and desktop, light and dark | AT-X.1 |

All 44 items are covered. Totals: 128 cases, 54 of them denied cases.
