// Every status is a pill with an icon and a word, never colour alone
// (design-system README, status table; NAVIGATION section 4).
import {
  ArrowLeft,
  BadgeCheck,
  Check,
  Circle,
  Clock,
  Eye,
  Layers,
  type LucideIcon,
  Pencil,
  RefreshCw,
  Send,
  ShieldCheck,
  ShieldX,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";

type Tone =
  | "neutral"
  | "info"
  | "warning"
  | "reviewed"
  | "success"
  | "published"
  | "danger"
  | "outline";

const TONES: Record<Tone, string> = {
  neutral: "bg-neutral-soft text-neutral",
  info: "bg-info-soft text-info",
  warning: "bg-warning-soft text-warning-ink",
  reviewed: "bg-reviewed-soft text-reviewed",
  success: "bg-success-soft text-success-ink",
  published: "bg-success-ink text-on-success",
  danger: "bg-danger-soft text-danger",
  outline: "border border-info text-info",
};

type Look = { label: string; tone: Tone; icon: LucideIcon };

const LOOKS: Record<string, Look> = {
  // Result sheets
  not_started: { label: "Not started", tone: "neutral", icon: Circle },
  draft: { label: "Draft", tone: "neutral", icon: Pencil },
  submitted: { label: "Submitted", tone: "info", icon: Send },
  returned_for_correction: {
    label: "Returned for correction",
    tone: "warning",
    icon: ArrowLeft,
  },
  resubmitted: { label: "Resubmitted", tone: "outline", icon: RefreshCw },
  reviewed: { label: "Reviewed", tone: "reviewed", icon: Eye },
  approved: { label: "Approved", tone: "success", icon: Check },
  published: { label: "Published", tone: "published", icon: BadgeCheck },
  // Reports
  valid: { label: "Valid", tone: "success", icon: ShieldCheck },
  superseded: { label: "Superseded", tone: "warning", icon: Layers },
  revoked: { label: "Revoked", tone: "danger", icon: ShieldX },
  // Corrections
  open: { label: "Open", tone: "info", icon: Circle },
  investigating: { label: "Investigating", tone: "info", icon: Eye },
  needs_more_information: {
    label: "Needs more information",
    tone: "warning",
    icon: Clock,
  },
  resolved: { label: "Resolved", tone: "success", icon: Check },
  rejected: { label: "Rejected", tone: "neutral", icon: X },
  // Form teacher sections
  returned: { label: "Returned", tone: "warning", icon: ArrowLeft },
  // Subscriptions
  free_pilot: { label: "Free pilot", tone: "info", icon: Circle },
  active: { label: "Active", tone: "success", icon: Check },
  due: { label: "Due", tone: "warning", icon: Clock },
  overdue: { label: "Overdue", tone: "danger", icon: Clock },
  suspended: { label: "Suspended", tone: "danger", icon: X },
  // Invoices
  unpaid: { label: "Unpaid", tone: "warning", icon: Clock },
  paid: { label: "Paid", tone: "success", icon: Check },
  void: { label: "Void", tone: "neutral", icon: X },
  // Emails
  queued: { label: "Queued", tone: "neutral", icon: Clock },
  sent: { label: "Sent", tone: "success", icon: Check },
  failed: { label: "Failed", tone: "danger", icon: X },
};

export function statusLabel(status: string): string {
  return LOOKS[status]?.label ?? status.replaceAll("_", " ");
}

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const look = LOOKS[status] ?? {
    label: statusLabel(status),
    tone: "neutral" as Tone,
    icon: Circle,
  };
  const Icon = look.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-1 text-sm font-medium whitespace-nowrap",
        TONES[look.tone],
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {look.label}
    </span>
  );
}
