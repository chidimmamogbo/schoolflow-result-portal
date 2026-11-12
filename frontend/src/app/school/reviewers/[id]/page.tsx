"use client";

// A reviewer (HOD): what they review, as a whole department or subjects and
// classes, and login support.
import { useParams } from "next/navigation";
import { useState } from "react";

import { LoginSupport } from "@/components/people/login-support";
import { accountState } from "@/components/people/staff-pages";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Select } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import {
  KEYS,
  useClasses,
  useDepartments,
  useStaff,
  useSubjects,
} from "@/lib/api/school";

export default function ReviewerPage() {
  const { id } = useParams<{ id: string }>();
  const { data: staff, isPending } = useStaff();
  const { data: departments } = useDepartments();
  const { data: subjects } = useSubjects();
  const { data: classes } = useClasses();
  const key = ["school", "scopes", id];
  const { data: scopes } = useApi(key, () =>
    ok(
      api.GET("/api/v1/school/reviewers/{user_id}/scopes", {
        params: { path: { user_id: id } },
      }),
    ),
  );
  const [department, setDepartment] = useState("");
  const [subject, setSubject] = useState("");
  const [klass, setKlass] = useState("");
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/reviewers/{user_id}/scopes", {
          params: { path: { user_id: id } },
          body: department
            ? { department_id: department }
            : { subject_id: subject || null, class_id: klass || null },
        }),
      ),
    {
      invalidate: [key],
      done: "Scope added.",
      onDone: () => {
        setDepartment("");
        setSubject("");
        setKlass("");
      },
    },
  );
  const remove = useAction(
    (scope: string) =>
      ok(
        api.DELETE("/api/v1/school/reviewer-scopes/{scope_id}", {
          params: { path: { scope_id: scope } },
        }),
      ),
    {
      invalidate: [key],
      done: "Scope removed.",
    },
  );
  const person = staff?.find((s) => s.id === id);
  if (isPending) return <LoadingState />;
  if (!person) return <EmptyState title="We couldn't find that person." />;
  const name = (
    list: { id: string; name: string }[] | undefined,
    value: string | null,
  ) => list?.find((x) => x.id === value)?.name;
  return (
    <>
      <PageHeader
        title={person.full_name}
        caption={`${person.username} · ${accountState(person)}`}
      />
      <div className="grid gap-6">
        <Card>
          <h2 className="mb-4 text-xl font-semibold">Reviews</h2>
          <DataTable
            caption="Scope"
            rows={scopes ?? []}
            rowKey={(s) => s.id}
            empty="Nothing to review yet."
            columns={[
              {
                key: "what",
                header: "Reviews",
                cell: (s) =>
                  s.department_id
                    ? `All of ${name(departments, s.department_id)}`
                    : [
                        name(subjects, s.subject_id) ?? "Every subject",
                        name(classes, s.class_id) ?? "every class",
                      ].join(" in "),
              },
              {
                key: "remove",
                header: "",
                cell: (s) => (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove.mutate(s.id)}
                  >
                    Remove
                  </Button>
                ),
              },
            ]}
          />
          <div className="mt-4 grid gap-3 md:grid-cols-4 md:items-end">
            <Field label="Department">
              {(f) => (
                <Select
                  {...f}
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                >
                  <option value="">None</option>
                  {(departments ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Subject">
              {(f) => (
                <Select
                  {...f}
                  disabled={Boolean(department)}
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                >
                  <option value="">Every subject</option>
                  {(subjects ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Class">
              {(f) => (
                <Select
                  {...f}
                  disabled={Boolean(department)}
                  value={klass}
                  onChange={(e) => setKlass(e.target.value)}
                >
                  <option value="">Every class</option>
                  {(classes ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Button
              variant="primary"
              disabled={!department && !subject && !klass}
              busy={add.isPending}
              onClick={() => add.mutate(undefined)}
            >
              Add scope
            </Button>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 text-xl font-semibold">Login support</h2>
          <LoginSupport person={person} invalidate={[[...KEYS.staff]]} />
        </Card>
      </div>
    </>
  );
}
