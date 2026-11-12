"use client";

// Login support on people pages (NAVIGATION "Login support actions"), and the
// one-time slip for a temporary password (D-040: shown once, never emailed).
import { Copy, Printer } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";

export function CredentialSlip({
  password,
  name,
  username,
  schoolCode,
  title = "Staff login slip",
  onClose,
}: {
  password: string | null;
  name: string;
  username: string;
  schoolCode?: string;
  title?: string;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={password !== null}
      onOpenChange={(open) => (open ? null : onClose())}
      title="Temporary password"
      description="This password is shown only once. Print the slip or copy it now."
      footer={
        <>
          <Button
            onClick={async () => {
              await navigator.clipboard?.writeText(password ?? "");
              toast.success("Copied.");
            }}
          >
            <Copy aria-hidden="true" />
            Copy
          </Button>
          <Button variant="primary" onClick={() => window.print()}>
            <Printer aria-hidden="true" />
            Print slip
          </Button>
        </>
      }
    >
      <section
        aria-label={title}
        className="rounded-md border border-dashed border-border-strong p-4"
      >
        <p className="text-xs font-medium tracking-wide text-muted">
          {title.toUpperCase()}
        </p>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted">Name</dt>
          <dd>{name}</dd>
          {schoolCode ? (
            <>
              <dt className="text-muted">School code</dt>
              <dd>{schoolCode}</dd>
            </>
          ) : null}
          <dt className="text-muted">Login ID</dt>
          <dd>{username}</dd>
          <dt className="text-muted">Temporary password</dt>
          <dd className="font-mono text-lg font-semibold break-all">
            {password}
          </dd>
        </dl>
      </section>
    </Dialog>
  );
}

type Person = {
  id: string;
  full_name: string;
  username: string;
  email: string | null;
  is_active: boolean;
  activated: boolean;
};

export function LoginSupport({
  person,
  invalidate,
}: {
  person: Person;
  invalidate: readonly unknown[][];
}) {
  const path = { params: { path: { user_id: person.id } } };
  const [slip, setSlip] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"deactivate" | null>(null);
  const keys = invalidate.map((k) => [...k]);

  const resend = useAction(
    () =>
      ok(api.POST("/api/v1/school/people/{user_id}/resend-activation", path)),
    {
      done: "Activation email sent.",
    },
  );
  const reset = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/people/{user_id}/send-reset-link", {
          ...path,
          body: { sign_out_all: false },
        }),
      ),
    { done: "Reset link sent." },
  );
  const temporary = useAction(
    () =>
      ok(api.POST("/api/v1/school/people/{user_id}/temporary-password", path)),
    {
      invalidate: keys,
      onDone: (result) => setSlip(result.temporary_password),
    },
  );
  const signOut = useAction(
    () => ok(api.POST("/api/v1/school/people/{user_id}/sign-out-all", path)),
    {
      done: "Signed out of all devices.",
    },
  );
  const deactivate = useAction(
    () => ok(api.POST("/api/v1/school/people/{user_id}/deactivate", path)),
    {
      invalidate: keys,
      done: "Account deactivated.",
      onDone: () => setConfirm(null),
    },
  );
  const reactivate = useAction(
    () => ok(api.POST("/api/v1/school/people/{user_id}/reactivate", path)),
    {
      invalidate: keys,
      done: "Account reactivated.",
    },
  );

  return (
    <div className="flex flex-wrap gap-2">
      {person.email && !person.activated ? (
        <Button
          busy={resend.isPending}
          onClick={() => resend.mutate(undefined)}
        >
          Resend activation
        </Button>
      ) : null}
      {person.email ? (
        <Button busy={reset.isPending} onClick={() => reset.mutate(undefined)}>
          Send reset link
        </Button>
      ) : null}
      <Button
        busy={temporary.isPending}
        onClick={() => temporary.mutate(undefined)}
      >
        Issue temporary password
      </Button>
      <Button
        busy={signOut.isPending}
        onClick={() => signOut.mutate(undefined)}
      >
        Sign out of all devices
      </Button>
      {person.is_active ? (
        <Button variant="danger" onClick={() => setConfirm("deactivate")}>
          Deactivate account
        </Button>
      ) : (
        <Button
          busy={reactivate.isPending}
          onClick={() => reactivate.mutate(undefined)}
        >
          Reactivate account
        </Button>
      )}
      <ConfirmDialog
        open={confirm === "deactivate"}
        onOpenChange={(open) => setConfirm(open ? "deactivate" : null)}
        title={`Deactivate ${person.full_name}?`}
        description="They can't log in until the account is reactivated. Nothing they entered is deleted."
        confirmLabel="Deactivate account"
        danger
        busy={deactivate.isPending}
        onConfirm={() => deactivate.mutate(undefined)}
      />
      <CredentialSlip
        password={slip}
        name={person.full_name}
        username={person.username}
        onClose={() => setSlip(null)}
      />
    </div>
  );
}
