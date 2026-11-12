"use client";

// Dialogs on Radix (focus is trapped and returned; Escape closes). ReasonDialog
// is for every action the spec says needs a reason (return, reopen, revoke ...).
import { Dialog as Radix } from "radix-ui";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/form";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
};

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
}: DialogProps) {
  return (
    <Radix.Root open={open} onOpenChange={onOpenChange}>
      <Radix.Portal>
        <Radix.Overlay className="fixed inset-0 z-40 bg-black/40" />
        <Radix.Content className="fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-y-auto rounded-lg border border-border bg-surface p-6 shadow-lg">
          <Radix.Title className="text-lg font-semibold">{title}</Radix.Title>
          {description ? (
            <Radix.Description className="text-muted">
              {description}
            </Radix.Description>
          ) : (
            <Radix.Description className="sr-only">{title}</Radix.Description>
          )}
          {children}
          {footer ? (
            <div className="flex flex-wrap justify-end gap-2">{footer}</div>
          ) : null}
        </Radix.Content>
      </Radix.Portal>
    </Radix.Root>
  );
}

type ConfirmProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
};

export function ConfirmDialog({
  confirmLabel,
  danger,
  busy,
  onConfirm,
  ...props
}: ConfirmProps) {
  return (
    <Dialog
      {...props}
      footer={
        <>
          <Button onClick={() => props.onOpenChange(false)}>Cancel</Button>
          <Button
            variant={danger ? "danger" : "primary"}
            busy={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </>
      }
    />
  );
}

type ReasonProps = Omit<ConfirmProps, "onConfirm"> & {
  label?: string;
  onConfirm: (reason: string) => void;
};

export function ReasonDialog({
  label = "Reason (required)",
  onConfirm,
  confirmLabel,
  danger,
  busy,
  ...props
}: ReasonProps) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string>();
  return (
    <Dialog
      {...props}
      footer={
        <>
          <Button onClick={() => props.onOpenChange(false)}>Cancel</Button>
          <Button
            variant={danger ? "danger" : "primary"}
            busy={busy}
            onClick={() => {
              if (!reason.trim()) {
                setError("Give a reason.");
                return;
              }
              onConfirm(reason.trim());
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <Field label={label} error={error}>
        {(field) => (
          <Textarea
            {...field}
            value={reason}
            maxLength={500}
            onChange={(event) => {
              setReason(event.target.value);
              setError(undefined);
            }}
          />
        )}
      </Field>
    </Dialog>
  );
}
