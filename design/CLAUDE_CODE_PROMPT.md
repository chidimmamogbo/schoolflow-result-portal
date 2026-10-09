# Prompt to paste into Claude Code

Unzip this folder into your project (for example as `design/` at the root), then paste the text below into Claude Code.

---

I've added our approved UI/UX handoff in the `design/` folder. Start by reading `design/README.md` and `design/NAVIGATION_AND_SETTINGS.md`, then `design/docs/SPEC.md`, `design/docs/DESIGN_REVIEW_v0.5.md`, `design/design-system/README.md` and `design/design-system/tokens.json`.

Important: use every label exactly as it appears in `design/NAVIGATION_AND_SETTINGS.md` and the screens. That covers menu items and their order, group headings, page titles, tabs, buttons, switch labels and descriptions, default settings, and messages. Don't rename, shorten, merge or reorder anything. If you need a label that isn't there, ask me first. Labels in section 5 of that file are proposals: check with me before treating them as final.

The screens in `design/screens/` are prototype files from a design canvas. They don't run on their own. Treat them as exact visual specs: copy layout, spacing, colours, type and copy from the markup, and the validation rules and state changes from the script at the bottom of each file. The README explains the syntax. The v0.5 screens style themselves with `design/screens/sf.css`, which maps one to one onto the tokens. Build from the v0.5 files where a v0.3 file has been superseded (the README lists which).

What I want:

1. Set up the design tokens from `design/design-system/tokens.css` (or `tokens.json`) as the single source of colours, type, spacing and radius, with light and dark themes. Don't hard-code hex values in components.
2. Build shared components first, matching the screens: button (primary, secondary, danger), input, select, toggle switch, status badge (icon and text, every status in the design-system README), card, table, dialog, side drawer, toast, stepper, tabs, and the app shell (sidebar with collapse, header with notice bell, theme toggle and profile menu, mobile drawer and bottom nav).
3. Then build the screens in this order, matching `design/screens/` as closely as possible: Login and Change password, My score sheets, Score entry (3 and 5 components), Rating sheet, My class, Principal dashboard, Approvals, Publish results, Students needing attention, School setup (Assessment, Grading, Learning areas and skills), Class page, School admins, Student detail, Report templates and the report cards, Billing, then the parent screens and Verify, then the super admin screens.
4. Use the logos in `design/brand/logos/` as files. Don't redraw them.

5. Put all menu definitions in one config file per role (labels, order, icons, routes), taken from `design/NAVIGATION_AND_SETTINGS.md`, so they can't drift between pages.

Before you write code, tell me which stack you're going to use and your component list, and wait for me to confirm. When each screen is done, list any label that differs from the design and why.
