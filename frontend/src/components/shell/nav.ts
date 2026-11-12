// The menus by role, word for word from design/NAVIGATION_AND_SETTINGS.md
// section 1 (and the approved section 5 teacher sidebar). A menu shows only
// features switched on for the school and items the role may use (F01, F20);
// the server still refuses anything else.
import {
  Bell,
  CheckSquare,
  ClipboardList,
  CreditCard,
  FileText,
  Flag,
  GraduationCap,
  History,
  Home,
  LayoutDashboard,
  type LucideIcon,
  Mail,
  PenLine,
  Receipt,
  School,
  Send,
  Settings,
  Shield,
  Tag,
  User,
  UserCheck,
  Users,
  Wallet,
} from "lucide-react";

import type { Me } from "@/lib/api/types";
import { type Role, featureOn, roleOf } from "@/lib/auth";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  group?: string;
  feature?: string;
  principalOnly?: boolean;
  formTeacherOnly?: boolean;
};

const SCHOOL_ADMIN: NavItem[] = [
  { label: "Dashboard", href: "/school/dashboard", icon: LayoutDashboard },
  {
    group: "RESULTS",
    label: "Approvals",
    href: "/school/approvals",
    icon: CheckSquare,
    feature: "results",
  },
  {
    group: "RESULTS",
    label: "Publish results",
    href: "/school/publish",
    icon: Send,
    feature: "results",
  },
  {
    group: "RESULTS",
    label: "Students needing attention",
    href: "/school/attention",
    icon: Flag,
    feature: "results",
  },
  {
    group: "RESULTS",
    label: "Report templates",
    href: "/school/report-templates",
    icon: FileText,
    feature: "report_cards",
  },
  {
    group: "RESULTS",
    label: "Audit trail",
    href: "/school/audit",
    icon: History,
  },
  {
    group: "PEOPLE",
    label: "Students",
    href: "/school/students",
    icon: GraduationCap,
  },
  { group: "PEOPLE", label: "Teachers", href: "/school/teachers", icon: User },
  {
    group: "PEOPLE",
    label: "Reviewers",
    href: "/school/reviewers",
    icon: UserCheck,
  },
  { group: "PEOPLE", label: "Parents", href: "/school/parents", icon: Users },
  {
    group: "PEOPLE",
    label: "School admins",
    href: "/school/admins",
    icon: Shield,
    principalOnly: true,
  },
  {
    group: "SCHOOL",
    label: "School setup",
    href: "/school/setup",
    icon: School,
  },
  {
    group: "SCHOOL",
    label: "Notices",
    href: "/school/notices",
    icon: Bell,
    feature: "notice_board",
  },
  {
    group: "SCHOOL",
    label: "Corrections",
    href: "/school/corrections",
    icon: PenLine,
    feature: "correction_queue",
  },
  { group: "SCHOOL", label: "Emails", href: "/school/emails", icon: Mail },
  {
    group: "SCHOOL",
    label: "Billing",
    href: "/school/billing",
    icon: CreditCard,
  },
  {
    group: "SCHOOL",
    label: "School settings",
    href: "/school/settings",
    icon: Settings,
  },
];

const SUPER_ADMIN: NavItem[] = [
  { label: "Dashboard", href: "/platform", icon: LayoutDashboard },
  { label: "Schools", href: "/platform/schools", icon: School },
  { label: "Pricing", href: "/platform/pricing", icon: Tag },
  {
    group: "BILLING",
    label: "Invoices",
    href: "/platform/billing",
    icon: Receipt,
  },
  {
    group: "BILLING",
    label: "Payments",
    href: "/platform/payments",
    icon: Wallet,
  },
  {
    group: "PLATFORM",
    label: "Audit log",
    href: "/platform/audit",
    icon: History,
  },
  {
    group: "PLATFORM",
    label: "Email log",
    href: "/platform/emails",
    icon: Mail,
  },
  {
    group: "PLATFORM",
    label: "Settings",
    href: "/platform/settings",
    icon: Settings,
  },
];

const TEACHER: NavItem[] = [
  { label: "Home", href: "/teacher", icon: Home },
  {
    label: "Sheets",
    href: "/teacher/sheets",
    icon: ClipboardList,
    feature: "results",
  },
  {
    label: "My class",
    href: "/teacher/my-class",
    icon: Users,
    formTeacherOnly: true,
  },
  { label: "Notices", href: "/notices", icon: Bell, feature: "notice_board" },
  {
    label: "Students needing attention",
    href: "/teacher/attention",
    icon: Flag,
    feature: "results",
  },
  { label: "Profile", href: "/profile", icon: User },
];

const REVIEWER: NavItem[] = [
  { label: "Dashboard", href: "/review", icon: LayoutDashboard },
  {
    label: "Review queue",
    href: "/review/queue",
    icon: ClipboardList,
    feature: "results",
  },
  {
    label: "Students needing attention",
    href: "/review/attention",
    icon: Flag,
    feature: "results",
  },
  { label: "Notices", href: "/notices", icon: Bell, feature: "notice_board" },
  { label: "Profile", href: "/profile", icon: User },
];

const PARENT: NavItem[] = [
  { label: "Home", href: "/parent", icon: Home },
  { label: "Results", href: "/parent/results", icon: FileText },
  { label: "Notices", href: "/notices", icon: Bell, feature: "notice_board" },
  { label: "Profile", href: "/profile", icon: User },
  {
    label: "Corrections",
    href: "/parent/corrections",
    icon: PenLine,
    feature: "correction_queue",
  },
];

const STUDENT: NavItem[] = [
  { label: "Home", href: "/student", icon: Home },
  { label: "My results", href: "/student/results", icon: FileText },
  { label: "Notices", href: "/notices", icon: Bell, feature: "notice_board" },
  { label: "Profile", href: "/profile", icon: User },
];

const MENUS: Record<Role, NavItem[]> = {
  super_admin: SUPER_ADMIN,
  school_admin: SCHOOL_ADMIN,
  reviewer: REVIEWER,
  teacher: TEACHER,
  parent: PARENT,
  student: STUDENT,
};

export function menuFor(me: Me): NavItem[] {
  const role = roleOf(me);
  return MENUS[role].filter((item) => {
    if (item.principalOnly && !me.is_primary) return false;
    if (item.formTeacherOnly && !me.form_class) return false;
    // The super admin has no school, so no feature switches apply.
    if (item.feature && role !== "super_admin" && !featureOn(me, item.feature))
      return false;
    return true;
  });
}

export function roleLabel(me: Me): string {
  const role = roleOf(me);
  if (role === "school_admin")
    return me.is_primary ? "Principal" : "School admin";
  return {
    super_admin: "Super admin",
    reviewer: "Reviewer",
    teacher: "Teacher",
    parent: "Parent",
    student: "Student",
  }[role];
}
