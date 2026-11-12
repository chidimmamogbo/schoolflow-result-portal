"use client";

// School admins (principal only, NAVIGATION "School admins page"): up to 2
// more. The server refuses anyone else; the page says so too.
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { CredentialSlip } from "@/components/people/login-support";
import { accountState } from "@/components/people/staff-pages";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { DataTable } from "@/components/ui/data-table";
import { Field, FormError, Input, Select } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { KEYS } from "@/lib/api/school";
import { useMe } from "@/lib/auth";

export default function SchoolAdminsPage() {
  const { data: me } = useMe();
  const principal = Boolean(me?.is_primary);
  const { data, isPending, isError, refetch } = useApi(
    [...KEYS.admins],
    () => ok(api.GET("/api/v1/school/admins")),
    principal,
  );
  const [v, setV] = useState({
    full_name: "",
    username: "",
    email: "",
    login_method: "temporary_password" as "activation" | "temporary_password",
  });
  const [error, setError] = useState<string | null>(null);
  const [slip, setSlip] = useState<string | null>(null);
  const [removing, setRemoving] = useState<{ id: string; name: string } | null>(
    null,
  );
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/admins", {
          body: {
            full_name: v.full_name.trim(),
            username: v.username.trim(),
            email: v.email.trim() || null,
            login_method: v.login_method,
          },
        }),
      ),
    {
      invalidate: [[...KEYS.admins]],
      done: (r) =>
        r.temporary_password
          ? null
          : "Added. An activation email is on its way.",
      onDone: (r) => setSlip(r.temporary_password),
    },
  );
  const remove = useAction(
    (id: string) =>
      ok(
        api.DELETE("/api/v1/school/admins/{user_id}", {
          params: { path: { user_id: id } },
        }),
      ),
    {
      invalidate: [[...KEYS.admins]],
      done: "School admin removed.",
      onDone: () => setRemoving(null),
    },
  );
  if (me && !principal) {
    return (
      <EmptyState
        title="Principal only"
        body="Only the principal can manage school admins."
        action={
          <Link
            href="/school/dashboard"
            className={buttonVariants({ variant: "secondary" })}
          >
            Back to dashboard
          </Link>
        }
      />
    );
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!v.full_name.trim() || !v.username.trim())
      return setError("Full name and username are needed.");
    if (v.login_method === "activation" && !v.email.trim())
      return setError("An activation email needs an email address.");
    setError(null);
    add.mutate(undefined);
  }
  return (
    <>
      <PageHeader title="School admins" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="school admins" onRetry={() => void refetch()} />
      ) : (
        <div className="grid gap-6">
          <DataTable
            caption="School admins"
            rows={data.admins}
            rowKey={(a) => a.id}
            empty="No other school admins yet."
            columns={[
              {
                key: "name",
                header: "Name",
                cell: (a) =>
                  a.id === me?.user.id ? `${a.full_name} (You)` : a.full_name,
              },
              { key: "username", header: "Username", cell: (a) => a.username },
              {
                key: "role",
                header: "Role",
                cell: (a) => (a.is_primary ? "Principal" : "School admin"),
              },
              { key: "state", header: "Account", cell: (a) => accountState(a) },
              {
                key: "remove",
                header: "",
                cell: (a) =>
                  a.is_primary ? null : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setRemoving({ id: a.id, name: a.full_name })
                      }
                    >
                      Remove
                    </Button>
                  ),
              },
            ]}
          />
          <Card className="max-w-[var(--form-max)]">
            <h2 className="mb-1 text-xl font-semibold">Add school admin</h2>
            <p className="mb-4 text-muted">{`${data.places_left} of 2 school admin places left.`}</p>
            {data.places_left > 0 ? (
              <form onSubmit={submit} className="grid gap-4" noValidate>
                <FormError message={error} />
                <Field label="Full name">
                  {(f) => (
                    <Input
                      {...f}
                      value={v.full_name}
                      onChange={(e) =>
                        setV({ ...v, full_name: e.target.value })
                      }
                    />
                  )}
                </Field>
                <Field label="Username">
                  {(f) => (
                    <Input
                      {...f}
                      value={v.username}
                      onChange={(e) => setV({ ...v, username: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Email">
                  {(f) => (
                    <Input
                      {...f}
                      type="email"
                      value={v.email}
                      onChange={(e) => setV({ ...v, email: e.target.value })}
                    />
                  )}
                </Field>
                <Field label="Login method">
                  {(f) => (
                    <Select
                      {...f}
                      value={v.login_method}
                      onChange={(e) =>
                        setV({
                          ...v,
                          login_method: e.target.value as typeof v.login_method,
                        })
                      }
                    >
                      <option value="temporary_password">
                        Temporary password slip
                      </option>
                      <option value="activation">Activation email</option>
                    </Select>
                  )}
                </Field>
                <div>
                  <Button type="submit" variant="primary" busy={add.isPending}>
                    Add school admin
                  </Button>
                </div>
              </form>
            ) : (
              <p>You can add up to 2 school admins.</p>
            )}
          </Card>
        </div>
      )}
      <CredentialSlip
        password={slip}
        name={v.full_name}
        username={v.username}
        onClose={() => setSlip(null)}
      />
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => (open ? null : setRemoving(null))}
        title={`Remove ${removing?.name ?? ""}?`}
        description="They will no longer be a school admin here. Nothing they did is deleted."
        confirmLabel="Remove"
        danger
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
      />
    </>
  );
}
