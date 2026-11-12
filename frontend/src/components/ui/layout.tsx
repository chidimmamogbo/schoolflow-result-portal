// Cards, page headers and the empty, loading and error states every page uses.
import { AlertCircle, Inbox, Loader2 } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      className={cn(
        "rounded-lg border border-border bg-surface p-4 shadow-sm md:p-6",
        className,
      )}
      {...props}
    />
  );
}

export function PageHeader({
  title,
  caption,
  actions,
}: {
  title: string;
  caption?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        {caption ? (
          <span className="text-xs font-medium tracking-wide text-muted">
            {caption}
          </span>
        ) : null}
        <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 py-10 text-muted"
    >
      <Loader2 className="size-5 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex flex-col items-center gap-2 py-10 text-center">
      <Inbox className="size-8 text-muted" aria-hidden="true" />
      <p className="text-lg font-semibold">{title}</p>
      {body ? <p className="max-w-md text-muted">{body}</p> : null}
      {action}
    </Card>
  );
}

// "We couldn't load {thing}." with "Check your connection and try again." (NAVIGATION section 5)
export function ErrorState({
  thing,
  onRetry,
}: {
  thing: string;
  onRetry?: () => void;
}) {
  return (
    <Card
      role="alert"
      className="flex flex-col items-center gap-2 py-10 text-center"
    >
      <AlertCircle className="size-8 text-danger" aria-hidden="true" />
      <p className="text-lg font-semibold">{`We couldn't load ${thing}.`}</p>
      <p className="text-muted">Check your connection and try again.</p>
      {onRetry ? (
        <Button variant="primary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </Card>
  );
}
