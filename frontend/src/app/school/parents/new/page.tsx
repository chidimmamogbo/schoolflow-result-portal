"use client";

// Add a parent: with an email, a link request they accept (D-138, D-140);
// without, a login slip or no login at all.
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { CredentialSlip } from "@/components/people/login-support";
import { WardPicker } from "@/components/people/ward-picker";
import { Button } from "@/components/ui/button";
import { Field, FormError, Input, Select } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, fullName, useStudents } from "@/lib/api/school";

export default function NewParentPage() {
  const router = useRouter();
  const { data: pupils } = useStudents();
  const [v, setV] = useState({
    full_name: "",
    phone: "",
    email: "",
    username: "",
    login: "temporary_password" as "temporary_password" | "none",
  });
  const [wards, setWards] = useState<
    { student_id: string; relationship: string }[]
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [made, setMade] = useState<{ id: string; password: string } | null>(
    null,
  );
  const withEmail = Boolean(v.email.trim());
  const create = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/guardians", {
          body: {
            full_name: v.full_name.trim(),
            phone: v.phone.trim() || null,
            email: v.email.trim() || null,
            wards,
            login: withEmail ? "link_request" : v.login,
            username:
              !withEmail && v.login === "temporary_password"
                ? v.username.trim()
                : null,
          },
        }),
      ),
    {
      invalidate: [[...KEYS.guardians]],
      done: () =>
        withEmail
          ? "Parent added. If the email is new or already a parent's, a link request is on its way."
          : null,
      onDone: (r) =>
        r.temporary_password
          ? setMade({ id: r.id, password: r.temporary_password })
          : router.push(`/school/parents/${r.id}`),
    },
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!v.full_name.trim()) return setError("Full name is needed.");
    if (!wards.length) return setError("Add at least one child.");
    if (!withEmail && v.login === "temporary_password" && !v.username.trim())
      return setError("A login slip needs a username.");
    setError(null);
    create.mutate(undefined);
  }
  const name = (id: string) => {
    const p = pupils?.find((x) => x.id === id);
    return p ? fullName(p) : "Pupil";
  };
  return (
    <>
      <PageHeader title="Add parent" />
      <form
        onSubmit={submit}
        className="grid max-w-[var(--form-max)] gap-4"
        noValidate
      >
        <FormError message={error} />
        <Field label="Full name">
          {(f) => (
            <Input
              {...f}
              value={v.full_name}
              onChange={(e) => setV({ ...v, full_name: e.target.value })}
            />
          )}
        </Field>
        <Field label="Phone">
          {(f) => (
            <Input
              {...f}
              type="tel"
              value={v.phone}
              onChange={(e) => setV({ ...v, phone: e.target.value })}
            />
          )}
        </Field>
        <Field
          label="Email"
          hint="With an email, the parent gets a link request and accepts it to see results."
        >
          {(f) => (
            <Input
              {...f}
              type="email"
              value={v.email}
              onChange={(e) => setV({ ...v, email: e.target.value })}
            />
          )}
        </Field>
        {withEmail ? null : (
          <>
            <Field label="Login method">
              {(f) => (
                <Select
                  {...f}
                  value={v.login}
                  onChange={(e) =>
                    setV({ ...v, login: e.target.value as typeof v.login })
                  }
                >
                  <option value="temporary_password">
                    Temporary password slip
                  </option>
                  <option value="none">No login</option>
                </Select>
              )}
            </Field>
            {v.login === "temporary_password" ? (
              <Field label="Username">
                {(f) => (
                  <Input
                    {...f}
                    value={v.username}
                    onChange={(e) => setV({ ...v, username: e.target.value })}
                  />
                )}
              </Field>
            ) : null}
          </>
        )}
        <Card>
          <h2 className="mb-3 text-lg font-semibold">Children</h2>
          <ul className="mb-3 grid gap-1">
            {wards.map((w) => (
              <li
                key={w.student_id}
                className="flex items-center justify-between gap-2"
              >
                <span>
                  {name(w.student_id)} ({w.relationship})
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setWards(wards.filter((x) => x.student_id !== w.student_id))
                  }
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
          <WardPicker
            exclude={wards.map((w) => w.student_id)}
            onAdd={(w) => setWards([...wards, w])}
          />
        </Card>
        <div>
          <Button type="submit" variant="primary" busy={create.isPending}>
            Add parent
          </Button>
        </div>
      </form>
      <CredentialSlip
        title="Parent login slip"
        password={made?.password ?? null}
        name={v.full_name}
        username={v.username}
        onClose={() => made && router.push(`/school/parents/${made.id}`)}
      />
    </>
  );
}
