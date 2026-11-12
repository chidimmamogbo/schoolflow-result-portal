// Inputs and labelled fields: inputs use border-strong, errors sit under the
// field in plain words, and a field's label is always tied to its input.
import { type ComponentProps, type ReactNode, useId } from "react";

import { cn } from "@/lib/utils";

const control =
  "min-h-11 w-full rounded-md border border-border-strong bg-surface px-3 text-base text-text placeholder:text-muted aria-[invalid=true]:border-danger";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(control, className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(control, "pr-8", className)} {...props} />;
}

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea className={cn(control, "min-h-24 py-2", className)} {...props} />
  );
}

type FieldProps = {
  label: string;
  error?: string;
  hint?: ReactNode;
  children: (props: {
    id: string;
    "aria-invalid": boolean;
    "aria-describedby"?: string;
  }) => ReactNode;
};

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children({
        id,
        "aria-invalid": Boolean(error),
        "aria-describedby": describedBy || undefined,
      })}
      {hint ? (
        <p id={`${id}-hint`} className="text-sm text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger"
    >
      {message}
    </p>
  );
}
