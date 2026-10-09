SchoolFlow Result Portal is a results-first platform for Nigerian primary and secondary schools: teachers enter scores once, reviewers and principals approve, each school publishes its own branded report card, and parents get a result they can verify. The interface should feel like a well-run school office with good software: trustworthy, calm, official, modern and warm. Never flashy.

## Principles

1. **Trust you can see.** Always show status, history and verification: who changed what, which version, whether it is valid.
2. **Errors before embarrassment.** Catch problems at the point of entry, in plain words, with the fix next to them.
3. **One clear next action.** Every screen has one obvious primary button (Submit, Approve, Publish, Pay now). Only one `primary` filled button per view.
4. **Phone first for teachers and parents, desk first for admins.** Design both, starting from the device each role really uses.
5. **Calm, official, modern.** Plenty of `bg`, white `surface` cards, one accent colour.
6. **Accessible by default.** Readable sizes, AA contrast in both themes, never colour alone.

## Content fundamentals

- Plain, friendly, specific English. Say what happened and what to do next. Short sentences.
- Speak to the user as "you". The product does not say "I" or "we" in UI copy.
- Sentence case for buttons, titles and labels ("Save draft", "Publish results"). Uppercase only in `caption` sidebar group headings.
- No em dashes. No emoji. No jargon such as "tenant", "revision hash", "RBAC" or internal codes in front of parents, students or teachers.
- Money: `₦321,000` (Naira sign, comma thousands, no kobo unless needed). Dates: `5 Jan 2027`. Times in West Africa Time.
- Real examples to follow:
  - Error: "Exam score can't be more than 60."
  - Missing: "3 students still need scores. Show me."
  - Publish confirmation: "Publish JSS 1A results? Parents and students will be notified and results become final. Any later change needs a correction with a reason."
  - Login error: "That login didn't work. Check your details and try again."
  - Empty state: "No score sheets yet. Your principal will assign your subjects."
  - Payment: "Confirming your payment. This usually takes a few seconds."
- Mockups use only the fictional sample data from the design brief (Greenfield Model College, Mrs. Ngozi Okeke, Chukwuemeka Obi and so on). Never real student names, photos or scores.

## Colour

- Page: `bg`. Cards, panels, sidebar and dialogs: `surface`. Table headers, row hover and input fills: `surface-2`.
- Body text in `text`; secondary text, helper text and labels in `text-muted`.
- `primary` is for the main action, links and the active nav item. A filled primary button uses `primary` with its label in `on-primary` (white in light, deep navy in dark). Selected nav and selected rows sit on `primary-soft`.
- `border` divides and outlines cards but is too faint to be the only edge of a control. Inputs, selects, checkboxes and score cells use `border-strong`.
- Status colours carry meaning, not decoration. In light mode `success` and `warning` are for icons and fills only; set success and warning text in `success-ink` and `warning-ink`.
- Each school has its own colour. Use it in limited places only: the school name area in the header, report card accents and the parent portal header. If a school colour fails 4.5:1 against its ground, fall back to `primary` for text and buttons.

## Status system

Every status is a pill badge (`radius-full`, `body-sm`, `space-1` by `space-2` padding) with an icon **and** a word. Never colour alone.

| Status | Text and icon | Background | Icon |
|---|---|---|---|
| Draft | `neutral` | `neutral-soft` | pencil |
| Submitted | `info` | `info-soft` | paper plane |
| Returned for correction | `warning-ink` | `warning-soft` | arrow back |
| Resubmitted | `info` | transparent, `info` outline | refresh |
| Reviewed | `reviewed` | `reviewed-soft` | eye check |
| Approved | `success-ink` | `success-soft` | check |
| Published | `on-success` | `success-ink` fill | badge check |
| Valid / Superseded / Revoked | `success-ink` / `warning-ink` / `danger` | matching `-soft` | shield check / layers / shield x |
| Correction: Open, Investigating, Needs more information, Resolved, Rejected | `info`, `info`, `warning-ink`, `success-ink`, `neutral` | matching `-soft` | |
| Subscription: Free pilot, Active, Due, Overdue, Suspended | `info`, `success-ink`, `warning-ink`, `danger`, `danger` on `neutral-soft` | matching `-soft` | |
| Invoice: Unpaid, Paid, Void | `warning-ink`, `success-ink`, `neutral` | matching `-soft` | |
| Email: Queued, Sent, Failed | `neutral`, `success-ink`, `danger` | matching `-soft` | |

## Typography

- One family, `sans` (Inter, loaded from Google Fonts, falling back to system sans). It has a proper Naira sign and tabular figures.
- Page titles: `h1` on desktop, `h2` on phone. Card titles `h3`, dialog titles `h4`.
- Body copy in `body` (16px). `body-sm` (14px) is the floor for any body text on phones. `caption` (12px) is for desktop-only metadata and uppercase sidebar group headings.
- Scores, totals and money always use `font-variant-numeric: tabular-nums`. Score grid cells use `score`, never smaller than 16px. Dashboard figures use `stat`.
- The verification result word (VALID, SUPERSEDED, REVOKED) is set in `display` in its status colour.

## Spacing, shape and depth

- 8px grid: `space-2` is the base. `space-4` gutters and card padding on phone; `space-5` card padding and `space-6` gutters on desktop.
- Corners: `radius-md` for buttons and inputs, `radius-lg` for cards and dialogs, `radius-sm` for score cells, `radius-full` for badges and chips.
- Light mode lifts cards with `shadow-sm`, menus with `shadow-md`, dialogs with `shadow-lg`. Dark mode has no shadows (the tokens resolve to `none`): separate layers with `border` instead.
- Motion is short and functional: sidebar collapse, drawer slide, toasts, around 150 to 200ms. Turn it off under `prefers-reduced-motion`.

## Layout

- Desktop (from `bp-laptop`): left sidebar at `sidebar-expanded` with icon and label, collapsible to `sidebar-collapsed` with tooltips on hover and focus. The choice is remembered. Sidebar groups get `caption` headings (Results, People, School, Billing).
- Header (`header-height`): page title and breadcrumb left; notice bell with unread count, theme toggle (light, dark, system) and profile menu right.
- Tablet (`bp-tablet` to `bp-laptop`): sidebar starts collapsed and expands over content.
- Phone: no sidebar. A menu icon opens a slide-out drawer. Parents and teachers may get a 3 or 4 item bottom bar. Wide tables scroll inside their own container or become cards; the page never scrolls sideways from 320px. Long forms and the score grid get a sticky bottom action bar with `shadow-md`.
- Every tappable control is at least `touch-target` on phones. Forms stop at `form-max`; tables and dashboards go full width.
- Focus: a 2px solid `focus` ring with a 2px offset on every focusable element, visible in both themes.

## Score grid

The most important teacher screen. Spreadsheet feel on desktop (arrow keys and Enter move between cells); on phone, a sticky name column or one card per student with large inputs. Cells use `score` on `surface` with a `border-strong` outline. A missing score gets a `warning` outline and the word "Missing"; an out-of-range score gets a `danger` outline and "Max is 20". A summary bar ("3 missing, 1 invalid") sits above the sticky Save draft and Submit bar, and Submit stays disabled until both are zero.

## Report cards and print

Report cards, PDFs and print previews are always the light design, A4 portrait, whatever theme the viewer uses. The school's colour is the only accent. The footer carries report ID, revision, publication date and QR code.

## Iconography

Use one consistent outline icon set with a 1.5 to 2px stroke at 20 or 24px. The brief names no set yet. Lucide is the suggested match because it has every glyph in the status table (pencil, send, undo, refresh, eye, check, badge check, shield check, layers, shield x). This is not confirmed. Icons take the colour of the text beside them. Every icon in the collapsed sidebar has a tooltip. No emoji anywhere.

## Logo

The mark is a single rounded stroke that starts as a tick and flows into an S: SchoolFlow, approved. It sits on a `primary` tile with `radius-lg` style corners (12 on a 48 grid). The files are in the Logos group:

- `schoolflow-logo.svg`: full lockup (mark, "SchoolFlow" in Inter Bold `text`, "Result Portal" in Inter Medium `text-muted`) for light grounds.
- `schoolflow-logo-dark.svg`: the same lockup for dark grounds (`primary` dark tile with `bg` stroke, `text` and `text-muted` dark values).
- `schoolflow-mark.svg`: the tile on its own for the collapsed sidebar, favicon and app icon.
- `schoolflow-mark-white.svg`: the stroke alone in white, for use on a `primary` or photo ground.

Rules: keep clear space of half the tile width on every side. Never recolour the stroke, rotate it, add effects or set the wordmark in another font. The lockup text is outlined, so it renders the same everywhere. Smallest size: 16px for the mark, 120px wide for the lockup. For school users the sidebar shows the school's own logo and name, with "Powered by SchoolFlow" and the mark in the footer.
