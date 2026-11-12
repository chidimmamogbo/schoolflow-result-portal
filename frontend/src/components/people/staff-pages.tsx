"use client";

// Teachers and reviewers: the list and the add form (login by activation email
// or a printed slip, D-040).
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { CredentialSlip } from "@/components/people/login-support";
import { Button, buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input, Select } from "@/components/ui/form";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, type Staff, useStaff } from "@/lib/api/school";

type Kind = "teacher" | "reviewer";
const WORDS: Record<Kind, { plural: string; base: string; add: string }> = {
  teacher: { plural: "Teachers", base: "/school/teachers", add: "Add teacher" },
  reviewer: {
    plural: "Reviewers",
    base: "/school/reviewers",
    add: "Add reviewer",
  },
};

export function accountState(
  person: Pick<Staff, "is_active" | "activated">,
): string {
  if (!person.is_active) return "Deactivated";
  return person.activated ? "Active" : "Invited";
}

export function StaffList({ kind }: { kind: Kind }) {
  const words = WORDS[kind];
  const { data, isPending, isError, refetch } = useStaff();
  const rows = (data ?? []).filter((s) => s.role === kind);
  return (
    <>
      <PageHeader
        title={words.plural}
        actions={
          <Link
            href={`${words.base}/new`}
            className={buttonVariants({ variant: "primary" })}
          >
            {words.add}
          </Link>
        }
      />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState
          thing={words.plural.toLowerCase()}
          onRetry={() => void refetch()}
        />
      ) : (
        <DataTable
          caption={words.plural}
          rows={rows}
          rowKey={(s) => s.id}
          empty={`No ${words.plural.toLowerCase()} yet.`}
          cardTitle={(s) => (
            <Link
              className="text-primary hover:underline"
              href={`${words.base}/${s.id}`}
            >
              {s.full_name}
            </Link>
          )}
          columns={[
            {
              key: "name",
              header: "Name",
              hideOnCard: true,
              cell: (s) => (
                <Link
                  className="font-medium text-primary hover:underline"
                  href={`${words.base}/${s.id}`}
                >
                  {s.full_name}
                </Link>
              ),
            },
            { key: "username", header: "Username", cell: (s) => s.username },
            { key: "email", header: "Email", cell: (s) => s.email ?? "None" },
            { key: "state", header: "Account", cell: (s) => accountState(s) },
          ]}
        />
      )}
    </>
  );
}

export function AddStaff({ kind }: { kind: Kind }) {
  const words = WORDS[kind];
  const router = useRouter();
  const [v, setV] = useState({
    full_name: "",
    username: "",
    email: "",
    login_method: "temporary_password" as "activation" | "temporary_password",
  });
  const [error, setError] = useState<string>();
  const [made, setMade] = useState<{
    id: string;
    password: string | null;
  } | null>(null);
  const create = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/staff", {
          body: {
            full_name: v.full_name.trim(),
            username: v.username.trim(),
            email: v.email.trim() || null,
            role: kind,
            login_method: v.login_method,
          },
        }),
      ),
    {
      invalidate: [[...KEYS.staff]],
      done: (r) =>
        r.temporary_password
          ? null
          : "Added. An activation email is on its way.",
      onDone: (r) =>
        r.temporary_password
          ? setMade({ id: r.id, password: r.temporary_password })
          : router.push(`${words.base}/${r.id}`),
    },
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!v.full_name.trim() || !v.username.trim())
      return setError("Full name and username are needed.");
    if (v.login_method === "activation" && !v.email.trim())
      return setError("An activation email needs an email address.");
    setError(undefined);
    create.mutate(undefined);
  }
  return (
    <>
      <PageHeader title={words.add} />
      <form
        onSubmit={submit}
        className="grid max-w-[var(--form-max)] gap-4"
        noValidate
      >
        {error ? (
          <p role="alert" className="text-danger">
            {error}
          </p>
        ) : null}
        <Field label="Full name">
          {(f) => (
            <Input
              {...f}
              value={v.full_name}
              onChange={(e) => setV({ ...v, full_name: e.target.value })}
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
          <Button type="submit" variant="primary" busy={create.isPending}>
            {words.add}
          </Button>
        </div>
      </form>
      <CredentialSlip
        password={made?.password ?? null}
        name={v.full_name}
        username={v.username}
        onClose={() => made && router.push(`${words.base}/${made.id}`)}
      />
    </>
  );
}
