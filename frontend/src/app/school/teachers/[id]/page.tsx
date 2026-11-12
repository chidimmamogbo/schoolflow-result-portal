"use client";

// A teacher: assignments (subject in a class, form teacher, teaches all
// subjects) and login support. Teaching comes from assignments (D-144).
import { useParams } from "next/navigation";
import { useState } from "react";

import { ArmSelect } from "@/components/people/arm-select";
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
import { useAction } from "@/lib/api/hooks";
import {
  KEYS,
  armNames,
  useAssignments,
  useClasses,
  useStaff,
  useSubjects,
} from "@/lib/api/school";

const FORM = "__form__";

export default function TeacherPage() {
  const { id } = useParams<{ id: string }>();
  const { data: staff, isPending } = useStaff();
  const { data: assignments } = useAssignments();
  const { data: classes } = useClasses();
  const { data: subjects } = useSubjects();
  const [arm, setArm] = useState("");
  const [what, setWhat] = useState("");
  const [all, setAll] = useState(false);
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/assignments", {
          body: {
            teacher_id: id,
            arm_id: arm,
            subject_id: what === FORM ? null : what,
            learning_area_id: null,
            is_form_teacher: what === FORM,
            teaches_all_subjects: what === FORM && all,
          },
        }),
      ),
    {
      invalidate: [[...KEYS.assignments]],
      done: "Assignment added.",
      onDone: () => {
        setWhat("");
        setAll(false);
      },
    },
  );
  const remove = useAction(
    (assignment: string) =>
      ok(
        api.DELETE("/api/v1/school/assignments/{assignment_id}", {
          params: { path: { assignment_id: assignment } },
        }),
      ),
    {
      invalidate: [[...KEYS.assignments]],
      done: "Assignment removed.",
    },
  );
  const person = staff?.find((s) => s.id === id);
  if (isPending) return <LoadingState />;
  if (!person) return <EmptyState title="We couldn't find that person." />;
  const names = armNames(classes);
  const subjectName = new Map((subjects ?? []).map((s) => [s.id, s.name]));
  const mine = (assignments ?? []).filter((a) => a.teacher_id === id);
  const describe = (a: (typeof mine)[number]) => {
    const where = names.get(a.arm_id) ?? "a class";
    if (a.is_form_teacher)
      return a.teaches_all_subjects
        ? `Class teacher of ${where} (all subjects)`
        : `Form teacher of ${where}`;
    return `${a.subject_id ? subjectName.get(a.subject_id) : "A learning area"} in ${where}`;
  };
  return (
    <>
      <PageHeader
        title={person.full_name}
        caption={`${person.username} · ${accountState(person)}`}
      />
      <div className="grid gap-6">
        <Card>
          <h2 className="mb-4 text-xl font-semibold">Assignments</h2>
          <DataTable
            caption="Assignments"
            rows={mine}
            rowKey={(a) => a.id}
            empty="No assignments yet."
            columns={[
              { key: "what", header: "Assignment", cell: describe },
              {
                key: "remove",
                header: "",
                cell: (a) => (
                  <Button
                    size="sm"
                    variant="ghost"
                    busy={remove.isPending && remove.variables === a.id}
                    onClick={() => remove.mutate(a.id)}
                  >
                    Remove
                  </Button>
                ),
              },
            ]}
          />
          <div className="mt-4 grid gap-3 md:grid-cols-3 md:items-end">
            <Field label="Class">
              {(f) => (
                <ArmSelect
                  {...f}
                  value={arm}
                  onChange={(e) => setArm(e.target.value)}
                />
              )}
            </Field>
            <Field label="Subject">
              {(f) => (
                <Select
                  {...f}
                  value={what}
                  onChange={(e) => setWhat(e.target.value)}
                >
                  <option value="">Choose</option>
                  <option value={FORM}>Form teacher (class teacher)</option>
                  {(subjects ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Button
              variant="primary"
              disabled={!arm || !what}
              busy={add.isPending}
              onClick={() => add.mutate(undefined)}
            >
              Add assignment
            </Button>
          </div>
          {what === FORM ? (
            <label className="mt-3 flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                className="size-5"
                checked={all}
                onChange={(e) => setAll(e.target.checked)}
              />
              <span>Teaches all subjects</span>
            </label>
          ) : null}
        </Card>
        <Card>
          <h2 className="mb-4 text-xl font-semibold">Login support</h2>
          <LoginSupport person={person} invalidate={[[...KEYS.staff]]} />
        </Card>
      </div>
    </>
  );
}
