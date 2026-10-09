# Navigation and settings: exact labels

**Use every label in this file exactly as written: same words, same capitalisation, same order.** Don't rename, shorten, merge or reorder anything. If a screen file and this file ever disagree, this file wins. If something you need isn't listed here, ask before inventing a label.

Items marked *(not designed yet)* have no screen in `screens/`. Files ending `_Phone` are the phone versions of the same screen. Build them with the same shell and components, and keep the label. Items marked **(v0.4)** were added or changed on 7 October 2026 (SPEC v0.4). Items marked **(v0.5)** add nursery and primary report cards, school types, skill ratings, class teachers and assistants (SPEC v0.5).

## 1. Menus by role

Menus only show features that are switched on for the school and allowed for the role (SPEC F01, F20).

### School admin / principal: desktop sidebar

| Group heading | Item | Screen |
|---|---|---|
| (none) | Dashboard | `DashboardV5.dc.html` (approved v0.3: `Dashboard.dc.html`) |
| RESULTS | Approvals | `Approvals.dc.html` |
| | Publish results | `PublishV5.dc.html` (approved v0.3: `Publish.dc.html`) |
| | Students needing attention **(v0.4)** | `Attention.dc.html` (role and school tweaks), `AttentionTeacher.dc.html`, `AttentionReviewer.dc.html`, `AttentionBSA.dc.html`, `AttentionTeacherBSA.dc.html` |
| | Report templates | `TemplateEditorV5.dc.html`, `TemplateEditorBSA.dc.html` (approved v0.3: `TemplateEditor.dc.html`) |
| | Audit trail | *(not designed yet)* |
| PEOPLE | Students | Student list *(not designed yet)*. Student detail: `StudentDetail.dc.html` |
| | Teachers | *(not designed yet)* |
| | Reviewers | *(not designed yet)* |
| | Parents | *(not designed yet)* |
| | School admins **(v0.4, principal only)** | `SchoolAdmins.dc.html` (viewer tweak shows the principal-only state), `SchoolAdminsBSA.dc.html` |
| SCHOOL | School setup | Assessment: `Assessment.dc.html`, `AssessmentBSA.dc.html`. Grading: `Grading.dc.html`, `GradingBSA.dc.html`. Learning areas and skills: `LearningAreas.dc.html`. Classes (class page): `ClassPage.dc.html`. Other tabs *(not designed yet)* (tabs: Sessions and terms, Classes, Subjects, Departments, Grading, Assessment **(v0.4)**, Learning areas and skills **(v0.5)**, Rating traits **(v0.4)**) |
| | Notices | *(not designed yet)* |
| | Corrections | `Corrections.dc.html` |
| | Emails | *(not designed yet)* |
| | Billing | `BillingV5.dc.html` (approved v0.3: `Billing.dc.html`) |
| | School settings | *(not designed yet)* |

Additional school admins see the same sidebar without "School admins". **(v0.5)** Only levels switched on for the school appear in any menu, tab or filter.
Badges: Approvals shows the number of sheets awaiting approval (filled `primary` badge). Corrections shows the number of open requests.
Sidebar top: school logo, school name, town. Sidebar bottom: the SchoolFlow mark with "Powered by SchoolFlow".

### Super admin: desktop sidebar **(v0.4)**

| Group heading | Item | Screen |
|---|---|---|
| (none) | Dashboard | `SuperDashboard.dc.html` |
| (none) | Schools | `SchoolsV5.dc.html`, `CreateSchool.dc.html`, `SchoolDetailV5.dc.html`, `SchoolDetailBSA.dc.html` (approved v0.3: `Schools.dc.html`, `SchoolDetail.dc.html`) |
| (none) | Pricing | `PricingV5.dc.html` (approved v0.3: `Pricing.dc.html`) |
| BILLING | Invoices | `SuperBillingV5.dc.html` (approved v0.3: `SuperBilling.dc.html`) |
| | Payments | `Payments.dc.html` |
| PLATFORM | Announcements (after the core) | *(not designed yet)* |
| | Audit log | `AuditLog.dc.html` |
| | Email log | `EmailLog.dc.html` |
| | Settings | `PlatformSettings.dc.html` |

Sidebar top: the full SchoolFlow Result Portal logo.

### Teacher: phone bottom navigation **(v0.4)**
Home · Sheets · My class · Notices. "My class" shows only for form teachers, class teachers and class teacher assistants **(v0.5)**. The slide-out menu (header menu icon) holds Students needing attention and Profile. Screens: `SheetsV5.dc.html` is "Sheets", titled "My score sheets" (approved v0.3: `TeacherSheets.dc.html`). Score entry: `ScoreGridV5.dc.html`, `ScoreGridSS.dc.html`. My class: `MyClass.dc.html`, `MyClassPrimary.dc.html`. Rating sheet: `RatingSheet.dc.html`, `RatingSheetAssistant_Phone.dc.html`. On desktop the same items sit in a sidebar: Home, Sheets, My class, Notices, Students needing attention, Profile.

### Parent / guardian: phone bottom navigation
Home · Results · Notices · Profile (screens: `ParentHome.dc.html`, `ReportView.dc.html`, Skills report: `ParentSkills.dc.html`). Corrections lives in the slide-out menu, opened from the header menu icon, and in the "Report a problem" link on a result.

### Reviewer / HOD **(v0.4)** (only Students needing attention is designed: `AttentionReviewer.dc.html`)
Dashboard · Review queue · Students needing attention · Notices · Profile

### Student *(not designed yet)*
Home · My results · Notices · Profile

### Header (every signed-in desktop screen)
Breadcrumb on the left. On the right: notice bell with unread count, theme toggle (Light, Dark, System), profile menu (name, role, Change password, Log out).

## 2. Page titles (h1)

| Screen | Title |
|---|---|
| Dashboard | What is blocking release? |
| Approvals | Approvals |
| Publish results | Publish results |
| Students needing attention **(v0.4)** | Students needing attention |
| Corrections | Corrections |
| Billing (principal) | Billing |
| Report templates | the template name, for example "Greenfield Junior Secondary" |
| School admins **(v0.4)** | School admins |
| School setup > Assessment **(v0.4)** | Assessment structure |
| My class **(v0.4)** | My class: {class}, for example "My class: JSS 1A" or "My class: Primary 4A" |
| School setup > Learning areas and skills **(v0.5)** | Learning areas and skills |
| Class page **(v0.5)** | {class}, for example "Primary 4A" |
| Rating sheet **(v0.5)** | {learning area}, {class}, for example "Number work, Nursery 2" |
| Super admin dashboard | Platform overview |
| Schools | Schools |
| Create school **(v0.4)** | Create school |
| Pricing | Pricing table |
| Invoices (super admin) | Billing |
| Payments (super admin) **(v0.4)** | Payments |
| Audit log (super admin) **(v0.4)** | Audit log |
| Email log (super admin) **(v0.4)** | Email log |
| Settings (super admin) **(v0.4)** | Platform settings |
| Login | Welcome back |
| Teacher sheets | My score sheets |
| Verify | Verify a report card |

## 3. Settings and their defaults

### School features (Create school and School detail > Features)
Six switches, in this order, with these descriptions:

| Label | Description | Default for a new school |
|---|---|---|
| Results | Score entry, review, approval and publishing | On |
| Report cards | Branded PDF report cards and the template editor | On |
| Parent portal | Parents and students see published results | On |
| Correction queue | Parents can report a problem with a result | Off |
| Notice board | School notices for every role | On |
| Email notifications | Activation, results and receipt emails | On |

Helper text under the list: "Turning a feature off hides it for this school straight away. Its data is kept."

### Report cards by level (School detail > Features, super admin only) **(v0.5)**
- Group heading: "Report cards by level".
- "School type" select and the three switches "Nursery report cards", "Primary report cards", "Secondary report cards", same as Create school.
- Turn-off confirmation: "Turning off {level} report cards hides {level} for this school. Its data and published reports are kept." with the affected classes listed when results are unpublished. Buttons: "Turn off", "Cancel".
- School admins see the same group read-only, with the note "Only SchoolFlow can change which levels your school uses." 

### Create school **(v0.4: replaces the Create school panel)**
Full page with sections:
1 · School details: School name, School email, Phone number, Address, City, State, Country, School code, School type **(v0.5)**, Report cards **(v0.5)**, School colour, Logo
2 · Features
3 · Billing: "Billing" switch (on; off means "Free pilot")
4 · Principal account: Full name, Username, Email

- State is a dropdown of the 36 states and FCT when Country is Nigeria (default), and a text field otherwise.
- School code: uppercase, 3 to 10 letters or numbers, suggested from the initials. Live messages: "{code} is available" and "{code} is taken".
- School type **(v0.5)**: select with options "Nursery and Primary", "Secondary only", "Nursery, Primary and Secondary", and "Custom" (shown automatically when the toggles don't match a type).
- Report cards **(v0.5)**: three switches, set by the school type: "Nursery report cards", "Primary report cards", "Secondary report cards" (description: "Junior and Senior Secondary"). Error if all are off: "Switch on at least one level." 
- School colour: full colour picker with a hex field. Warning: "Text on this colour may be hard to read. We'll use the SchoolFlow blue for buttons and text."
- Username: live messages "{username} is available" and "{username} is taken".
- Button: "Create school and send invite".
- Success message: "{School name} is ready. We've emailed {principal} an activation link and sent a set-up confirmation to {school email}."

### School detail tabs **(v0.4)**
Overview · Features · School admins · Subscription · Invoices · Activity

- **Overview:** details, usage (Students, Staff, Parents, Results published, Last activity); buttons "Edit details", "Change school code", "Resend set-up email", "Suspend school" (becomes "Reactivate school"). Suspending needs a reason and never deletes data.
- **School admins:** replaces "Principal account". Row actions, in this order: Resend activation, Change email, Send reset link, Issue temporary password, Sign out of all devices, Make principal, Deactivate account (becomes "Reactivate account").
- **Subscription:** "Billing" switch (on by default; off means free pilot), "Grace period" in days (default 14).

### Login support actions (school admins on people pages) **(v0.4)**
Resend activation, Send reset link, Issue temporary password, Sign out of all devices, Deactivate account (becomes "Reactivate account").
Temporary password dialog warning: "This password is shown only once. Print the slip or copy it now." Buttons: "Copy", "Print slip".

### School admins page (principal only) **(v0.4)**
Button: "Add school admin". Fields: Full name, Username, Email, Login method. Limit message: "You can add up to {n} school admins."

### Assessment structure **(v0.4)**
- Level tabs: Nursery · Primary · Junior Secondary · Senior Secondary **(v0.5: only levels switched on)**.
- **(v0.5)** "Assessment mode" segmented control: "Scores" (description "CAs and exams out of 100, with totals, grades and positions") · "Skill ratings" (description "Each skill rated from Excellent to Needs improvement, with no scores"). Defaults: Nursery Skill ratings; Primary, Junior Secondary, Senior Secondary Scores. When Skill ratings is chosen, the component table is replaced by the link "Set up learning areas and skills".
- Columns: Name · Short label · Max score. Button: "Add component" (up to 8).
- Default: CA1 /20 · CA2 /20 · Exam /60.
- Total messages: "Total 100" and "Total {n}. Add {100 - n} more to reach 100." (or "Remove {n - 100} to get back to 100.").
- Locked banner: "Scores have been entered for {term}, so this structure is locked. Changes you save will apply from {next term}."

### Grading **(v0.4)**
Adds "Pass mark" (default 40) with helper text "Results below this mark appear in Students needing attention."
**(v0.5)** Level tabs for levels on Scores. Defaults: Junior and Senior Secondary A1 to F9; Primary and Nursery A to F (A 70 to 100 Excellent, B 60 to 69 Very good, C 50 to 59 Good, D 45 to 49 Fair, E 40 to 44 Pass, F 0 to 39 Fail).

### Learning areas and skills **(v0.5)**
- Level tabs for levels on Skill ratings.
- Buttons: "Add learning area", "Add skill", "Assign to classes".
- Default learning areas: Number work, Letter work, Phonics, Rhymes and songs, Creative arts, Social habits, Health habits, Physical development.
- Skill fields: "Skill", "Description (optional)".
- Card heading: "Rating scale". Default points: Excellent (E), Very good (VG), Good (G), Fair (F), Needs improvement (NI). Fields: "Word", "Code", "Description". Button: "Add point".
- Select: "Flag in Students needing attention at or below" (default Needs improvement).
- Note: "Published reports keep the scale and skills they were published with."

### Class page: class teacher and assistants **(v0.5)**
- Select: "Class teacher". Switch: "Teaches all subjects", description "Gives this teacher every subject in {class}, including subjects added later."
- Section: "Class teacher assistants". Button: "Add assistant". Limit: "You can add up to 2 assistants." Note: "Assistants can enter scores, ratings and comments for this class. Only the class teacher can submit."
- Teacher detail lines: "Class teacher of {class} (all subjects)", "Assistant in {class}".

### Rating sheet **(v0.5)**
- Filter chips: "All", "Not rated". Search: "Search by name".
- Rating buttons show codes (E, VG, G, F, NI); the selected one shows its word.
- Field: "Comment on {learning area} (optional)".
- Summary: "{n} skills not rated yet. Show me."
- Buttons: "Save draft", "Submit" (assistants see "Save draft" only).

### Pricing table **(v0.4)**
- Columns: Plan name · Min students · Max students · Price per student (₦). Last plan's max is blank and shows the placeholder "and above".
- Defaults: Basic 1 to 499 at ₦1,000 · Standard 500 to 1,000 at ₦500 · Premium 1,001 and above at ₦300.
- Buttons: "Add plan", "Save as new version".
- **The "Volume" or "Graduated" choice is removed.** Line under the table: "Each school pays the price of the plan its student count falls into, for every student."
- Switch: "Cliff protection" (on), description "A school never pays more than the smallest bill on a higher plan."
- Panel heading: "Price check". Example lines: "Schools with 251 to 499 students would pay more than a school with 500 students." and "Schools with 601 to 1,000 students would pay more than a school with 1,001 students."
- Calculator heading: "Try it". Capped line: "Capped by cliff protection: {capped} instead of {full}".

### Score entry **(v0.4)**
- Assessment components come from the level's assessment structure (1 to 8 columns). Junior Secondary default: CA1 /20 · CA2 /20 · Exam /60.
- Sheets page: grouped by class, filter chips "Class", "Subject", "Status".
- In a sheet: search placeholder "Search by name or admission number"; filter chips "All", "Missing", "Errors" with counts.
- Buttons: "Save draft", "Submit". Submit stays disabled while any score is missing or invalid.
- Messages: "{Component} score is missing." and "{Component} score can't be more than {max}."

### My class (form teacher) **(v0.4)**
- Tabs: Broadsheet · Students · Preview.
- Field: "Times school opened".
- Student entry fields: "Class teacher's comment" (300 characters), "Affective", "Psychomotor", "Times present". Buttons: "Save", "Save and next".
- Button: "Submit class sections". Returned state shows "Returned by {name}: {comment}".
- Preview band: "Preview, not published".

### Publish results **(v0.4)**
- Checklist adds "Form teacher sections submitted".
- Step: "Principal's comments".
- Blocked message: "Form teacher comments for {class} are not submitted yet."

### Students needing attention **(v0.4)**
- Subtitle: "{term} {session} · Pass mark {n}%".
- Tabs: "By subject" · "By student" · "By learning area" **(v0.5, only when a level uses Skill ratings)**.
- Badges: "Below pass mark", "Average below pass mark".
- Buttons: "Export CSV", "Print".
- Empty: "No results below the pass mark for this selection." Before publication: "This list appears when results are published."

### Report template editor **(v0.4)**
- Templates are grouped by level **(v0.5)**.
- Styles: Modern (default) · Classic · Compact · Early Years **(v0.5)**. After the core: Bold Banner · Ink Saver · Cumulative.
- **(v0.5)** Template setting "Head's title": Head teacher · Principal · Head of school · Proprietor · Director · Custom. Default Head teacher for Nursery and Primary, Principal for Secondary. It replaces "Principal" in "{Head's title}'s comment" and the signature label.
- Blocks, in default order, with default visibility:

| Block | Shown by default |
|---|---|
| School header | Yes |
| Student details | Yes |
| Subject table | Yes |
| Summary: total, average, position | Yes |
| Affective and psychomotor | Yes |
| Attendance | No |
| Comments | Yes |
| Signatures | Yes |
| Footer, QR and report ID | Yes (always shown) |

- Block settings (switches unless a choice is listed; default in brackets):
  - School header: Logo (on), Logo position: Left, Centre, Right (Left), School motto (on), Address (on), Phone and email (on), Report title (text, "Student Report Card"), Session and term line (on).
  - Student details: Photo (off), Admission number (on), Gender (on), Age (off), Date of birth (off), Class and arm (on), House (off), Form teacher's name (on).
  - Subject table: one switch per assessment column (on), CA and exam breakdown (on), Total (on), Grade (on), Remark (on), Position in each subject (on), Class average per subject (on), Highest in class (off), Lowest in class (off), Subject teacher's initials (off), Highlight scores below pass mark (off), Row shading (on).
  - Summary: Total score (on), Total average (on), Overall class position (optional) (on), Number in class (on), Class average (off), Number of subjects (off), Promotion result (off).
  - Affective and psychomotor: Affective (on), Psychomotor (on), Rating key (on), Layout: Side by side, Stacked (Side by side).
  - Attendance: Times school opened (on), Times present (on), Times absent (on).
  - Comments: Form teacher's comment (on), Principal's comment (on), Show names (on).
  - Signatures: Form teacher signature line (on), Principal signature image (off), School stamp image (off), Date line (on).
  - Footer, QR and report ID: QR position: Left, Right (Right), Next term begins (on), School contact line (on), Custom footer note (text, empty). Locked rows with a lock icon and "Always shown": Report ID, Revision, Publication date, QR code.
- Template settings: Paper size: A4, Letter (A4) · Font: Inter, Merriweather, Nunito (Inter) · Text size: Small, Medium, Large (Medium) · Accent colour (school colour) · Borders: None, Lines, Boxed (Lines) · Logo watermark (off) · Grading key: Off, Below summary, In footer (Below summary) · Margins: Narrow, Normal (Normal).
- When "Overall class position (optional)" is off, the summary shows "No. in class" instead.
- Save button: "Save as version {n}". Published reports keep the version they were issued with.

### Skills report card **(v0.5)**
- Blocks, in default order: School header · Pupil details · Skills table · Rating key · Attendance · Comments · Signatures · Footer, QR and report ID (always shown).
- Block settings: Pupil details: Photo (off), Age (on), Class (on). Skills table: Group by area (on), Show skill descriptions (off), Show area comments (on), Rating display: Words, Codes, Words and codes (Words). Comments: Class teacher's comment (on), {Head's title}'s comment (on). Footer: Next term begins (on).
- Default style: Early Years.
- Print labels: SKILL · RATING · RATING KEY · CLASS TEACHER'S COMMENT · {HEAD'S TITLE}'S COMMENT.

### Report card summary labels (print)
TOTAL SCORE · TOTAL AVERAGE · OVERALL CLASS POSITION (or CLASS POSITION in the Classic style) · NO. IN CLASS

### Platform settings (super admin) **(v0.4)**
Tabs: General · Email · School defaults · Billing · Security
- General: Platform name, Logo, Support email, Support phone.
- Email: Sender name, Reply-to address.
- School defaults: Grading bands, Assessment structure, Pass mark, Remark bands, Rating traits, Report template style.
- Billing: Grace period (days, 14), Invoice due (days, 14), Gateway fees paid by: Platform, School (Platform), Cliff protection (on).
- Security: Additional school admins per school (2), Session length, Two-factor login for super admins (after the core).
- Each tab: "Save changes" and "Last changed by {name} on {date}".

### Login **(v0.4)**
Tabs: Staff and parents · Student.
- Staff and parents tab: Email or username, Password. Button: "Log in". Link: "Forgot password?".
- Student tab: School code, Username or admission number, Password. Button: "Log in". Text instead of a link: "Forgot your password? Ask your school admin for a new one."
- School login link (`/login/{code}`): school logo and name above the card, Student tab selected, School code filled in.
- Error: "That login didn't work. Check your details and try again."
- Forgot password note: "No email on your account? Ask your school admin to reset your password."
- School paused page: "Your school's access is paused. Contact your school admin."
- There is no sign-up anywhere.

## 4. Status labels
Use exactly the labels in the status table in `design-system/README.md` (Draft, Submitted, Returned for correction, Resubmitted, Reviewed, Approved, Published, Valid, Superseded, Revoked, and so on). In the public verification result they are uppercase: VALID, SUPERSEDED, REVOKED.

**(v0.5) New statuses:** Report card level: On, Off. Skill ratings: Excellent, Very good, Good, Fair, Needs improvement (always with the word or code). Attention: Needs attention (skills).

**(v0.4) New statuses:** Form teacher sections: Open, Submitted, Returned. School: Active, Suspended. Assessment structure: Editable, Locked for this term. Account: Invited, Active, Must change password, Deactivated. Invoice line: Capped by cliff protection. Attention: Below pass mark, Average below pass mark.


## 5. Labels proposed during the v0.5 design (waiting for sign-off)

These labels appear on the v0.5 boards but are not in sections 1 to 4 or the brief. Approve, rename or reject them. Until you approve them, treat them as placeholders in the build. Anything in curly brackets is filled in at run time.

### Shared
- Clear filters · Filters · Show me · Show all · Try again · Cancel · Close · Save · Save changes · Discard changes · Undo · Previous · Next · Done · To do · Not yet · Open · Rename · Remove
- Error states: "We couldn't load {thing}." with "Check your connection and try again."
- Teacher desktop sidebar: Home · Sheets · My class · Notices · Students needing attention · Profile (same order as the phone bar, then the slide-out items)
- Change password (forced): "You logged in with a temporary password. Choose a new one to continue." Fields "New password", "Confirm new password". Rules "At least 8 characters", "A letter and a number", "Different from your temporary password". Error "The passwords don't match." Done "Your password is changed." with "Continue".
- No-access state: badge "Principal only", "Only the principal can manage school admins.", "Back to dashboard".

### Super admin
- School detail: tabs Overview · Features · School admins · Subscription · Invoices · Activity. Usage tiles Students · Staff · Parents · Results published · Last activity. Dialogs "Reset login", "Temporary password", "Turn off {level} report cards?", "Suspend {school}?" with "Reason (required)", "Change school code" with "New school code".
- Billing overview: column "Cliff protection" with "Not applied" or "Capped"; line "Cliff protection is on."; empty "No schools to bill yet."
- Platform settings: Upload new logo, Preview, On light, On dark, Edit grading bands, Starts at, Ends at, Add trait, New trait, Group, Affective, Psychomotor.
- Payments: Resend receipt, View invoice, Receipt number, Recorded by, Gateway fee, Receipt email.
- Audit log: Show details, Hide details, Field, Before, After, Platform only, Everyone, SchoolFlow (automatic). Date filter Any time, Today, Last 7 days, Last 30 days. Action groups Schools, Report cards by level, Logins and accounts, Pricing, Invoices, Payments, Emails.
- Email log: Retry.

### School admin / principal
- Dashboard: "{n} form teacher sections still open" with "Remind form teachers"; card badge "Below 40%"; empty "Nothing is blocking release."
- Publish results: "Remind form teacher", "Go to dashboard", principal's comments placeholder "Write a comment", "Suggestion:", "Comment", "Apply to {n} students", "Students who already have a comment keep it."; empty "No results to publish yet."
- Billing: badge "Your plan"; empty "No invoices yet."
- Students needing attention: filters Arm, Learning area, Status; "Failed subjects or skills"; "Show failed subjects", "Show skills", "Hide details"; "Open publish results"; "Showing {n} of 37 results across JSS 1."; "{n} results for this selection."; "CSV downloaded with {n} rows."; "Print view opened for {n} rows."; "{term} {session} results for {class} are not published yet."; scope notes "Showing Basic Science and Basic Technology in JSS 1.", "Showing all subjects for your class Primary 4A.", "Showing all subjects in Primary 4 and all learning areas in Nursery 2."
- Assessment structure: Components, Score sheet preview, Order and remove, "{n} of 8 components", "You can have up to 8 components.", "Name is missing.", "Short label is missing.", "Short labels must be different.", "Max score must be a whole number from 1 to 100.", "Fix the highlighted fields to save.", "{level} uses Skill ratings".
- Grading: "Grade bands: {level}", Add band, "Covers 0 to 100", "Needs fixing", "Crosses pass mark", "No grade covers {a} to {b}.", "{g1} and {g2} overlap at {a} to {b}.", "Grade {g} is used twice.", "Pass mark must be a whole number from 0 to 100.", "Nursery uses Skill ratings, so it has no grade bands."
- School admins: "{n} of 2 school admin places left.", "No other school admins yet.", "You", "Staff login slip".
- Student detail and slips: Login support, Login ID, Login link, "Student login slip", "ONE-TIME TEMPORARY PASSWORD", "Issued {date} by {name}. Keep this slip private.", Print, Open report.
- Learning areas and skills: Change in Assessment, Save rating scale, Name, Shows as, In use, No classes, No description, "Choose at least one class.", "Word is needed.", "Code is needed.", "Code {X} is already used.", "There's already a learning area called {name}.", "{area} already has a skill called {name}.", "Fix the highlighted points to save the scale."
- Class page: tabs Overview · Subjects · Pupils; "On teacher pages"; Choose a teacher; Not assigned; Class teacher badge; Open teacher detail; "Choose a class teacher first."; "Primary 4A has 2 assistants. Remove one to add another."; "Class teacher of Primary 4A"; "{n} of 10 subjects in Primary 4A"; "Teaches {subjects} in Primary 4A".
- Report templates: Templates by level, Version history, Style, Settings, Upload image, Replace, Show block, Unsaved, Not saved yet, Custom colour, Custom title, Class teacher signature line, the Preview / Settings switch on phone, the sample student switch.

### Teacher
- My score sheets: search "Search by subject or class"; chips Class · Subject · Status with "All"; "No score sheets yet."; "No sheets match."
- Score entry: "Find a student", "No student matches "{text}".", "Showing {name}.", "No missing scores.", "No errors.", "No students in {class} yet."
- Rating sheet: "Not rated yet", "{n} skills not rated", Rated, "Every skill is rated.", "Back to my sheets", "Sheet submitted", "Submit Number work, Nursery 2?"
- My class: All subjects, Average, "{n} to go", "Still needed: {names}.", "Class sections: {status}", Class sections, Suggestions, Rating key, "Absent: {n}", "{n} of 300 characters", "Student {n} of {total}" (Pupil for Nursery and Primary), Complete, Needs comment, Needs ratings, Needs attendance, "Submit class sections for {class}?"

### Print and parent
- Report cards: STUDENT REPORT CARD, SKILLS REPORT, LEARNING AREA, COMMENT, PUPIL, AGE, CLASS TEACHER, CLASS AVERAGE, NO. OF SUBJECTS, PROMOTION RESULT, TIMES SCHOOL OPENED, TIMES PRESENT, TIMES ABSENT, School stamp, Date; key "Below pass mark (40). The score is bold, underlined and marked with a triangle."
- Parent Skills report: Skills report, Learning areas, Comment, Expand all, Collapse all, "{n} skills", "Class teacher's comment · {name}", "Head teacher's comment · {name}", "{name}'s First Term report is not ready yet".
