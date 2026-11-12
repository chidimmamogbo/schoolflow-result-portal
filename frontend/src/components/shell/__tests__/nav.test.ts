// Menus follow NAVIGATION section 1 word for word, and hide what the school
// switched off or the role cannot use (the server still refuses it).
import { expect, test } from "vitest";

import { menuFor, roleLabel } from "@/components/shell/nav";
import { makeMe } from "@/test/helpers";

const labels = (me = makeMe()) => menuFor(me).map((item) => item.label);

test("the principal sees the school admin menu in order", () => {
  expect(labels()).toEqual([
    "Dashboard",
    "Approvals",
    "Publish results",
    "Students needing attention",
    "Report templates",
    "Audit trail",
    "Students",
    "Teachers",
    "Reviewers",
    "Parents",
    "School admins",
    "School setup",
    "Notices",
    "Corrections",
    "Emails",
    "Billing",
    "School settings",
  ]);
  expect(roleLabel(makeMe())).toBe("Principal");
});

test("an additional school admin has no School admins item", () => {
  const me = makeMe({ is_primary: false });
  expect(labels(me)).not.toContain("School admins");
  expect(roleLabel(me)).toBe("School admin");
});

test("a feature that is off disappears from the menu", () => {
  const me = makeMe({
    features: ["results", "report_cards", "parent_portal", "notice_board"],
  });
  expect(labels(me)).not.toContain("Corrections");
});

test("My class shows only for a form teacher", () => {
  const teacher = makeMe({ role: "teacher", is_primary: false });
  expect(labels(teacher)).toEqual([
    "Home",
    "Sheets",
    "Notices",
    "Students needing attention",
    "Profile",
  ]);
  const form = makeMe({
    role: "teacher",
    is_primary: false,
    form_class: { arm_id: "a1", name: "JSS 1A" },
  });
  expect(labels(form)).toEqual([
    "Home",
    "Sheets",
    "My class",
    "Notices",
    "Students needing attention",
    "Profile",
  ]);
});

test("the super admin sees the platform menu, whatever the features", () => {
  const me = makeMe({ is_super_admin: true, school: null, features: [] });
  expect(labels(me)).toEqual([
    "Dashboard",
    "Schools",
    "Pricing",
    "Invoices",
    "Payments",
    "Audit log",
    "Email log",
    "Settings",
  ]);
});

test("parents and students have their own short menus", () => {
  expect(labels(makeMe({ role: "parent", is_primary: false }))).toEqual([
    "Home",
    "Results",
    "Notices",
    "Profile",
    "Corrections",
  ]);
  expect(labels(makeMe({ role: "student", is_primary: false }))).toEqual([
    "Home",
    "My results",
    "Notices",
    "Profile",
  ]);
});
