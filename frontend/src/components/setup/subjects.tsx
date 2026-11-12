"use client";

// Subjects (each optionally in a department) and departments.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input, Select } from "@/components/ui/form";
import { Card } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, useDepartments, useSubjects } from "@/lib/api/school";

export function SubjectsTab() {
  const { data: subjects } = useSubjects();
  const { data: departments } = useDepartments();
  const [v, setV] = useState({ name: "", department_id: "" });
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/subjects", {
          body: {
            name: v.name.trim(),
            department_id: v.department_id || null,
            category: null,
          },
        }),
      ),
    {
      invalidate: [[...KEYS.subjects]],
      done: "Subject added.",
      onDone: () => setV({ ...v, name: "" }),
    },
  );
  const remove = useAction(
    (id: string) =>
      ok(
        api.DELETE("/api/v1/school/subjects/{subject_id}", {
          params: { path: { subject_id: id } },
        }),
      ),
    { invalidate: [[...KEYS.subjects]], done: "Subject removed." },
  );
  const dept = new Map((departments ?? []).map((d) => [d.id, d.name]));
  return (
    <div className="grid gap-4">
      <DataTable
        caption="Subjects"
        rows={subjects ?? []}
        rowKey={(s) => s.id}
        empty="No subjects yet."
        columns={[
          { key: "name", header: "Subject", cell: (s) => s.name },
          {
            key: "dept",
            header: "Department",
            cell: (s) => (s.department_id ? dept.get(s.department_id) : "None"),
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
      <Card className="grid gap-3 md:grid-cols-3 md:items-end">
        <Field label="Subject">
          {(f) => (
            <Input
              {...f}
              value={v.name}
              onChange={(e) => setV({ ...v, name: e.target.value })}
            />
          )}
        </Field>
        <Field label="Department">
          {(f) => (
            <Select
              {...f}
              value={v.department_id}
              onChange={(e) => setV({ ...v, department_id: e.target.value })}
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
        <Button
          variant="primary"
          disabled={!v.name.trim()}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add subject
        </Button>
      </Card>
    </div>
  );
}

export function DepartmentsTab() {
  const { data } = useDepartments();
  const [name, setName] = useState("");
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/departments", { body: { name: name.trim() } }),
      ),
    {
      invalidate: [[...KEYS.departments]],
      done: "Department added.",
      onDone: () => setName(""),
    },
  );
  const remove = useAction(
    (id: string) =>
      ok(
        api.DELETE("/api/v1/school/departments/{department_id}", {
          params: { path: { department_id: id } },
        }),
      ),
    { invalidate: [[...KEYS.departments]], done: "Department removed." },
  );
  return (
    <div className="grid gap-4">
      <DataTable
        caption="Departments"
        rows={data ?? []}
        rowKey={(d) => d.id}
        empty="No departments yet."
        columns={[
          { key: "name", header: "Department", cell: (d) => d.name },
          {
            key: "remove",
            header: "",
            cell: (d) => (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => remove.mutate(d.id)}
              >
                Remove
              </Button>
            ),
          },
        ]}
      />
      <Card className="grid gap-3 md:grid-cols-[2fr_auto] md:items-end">
        <Field
          label="Department"
          hint="Used for HOD review and the senior secondary department."
        >
          {(f) => (
            <Input
              {...f}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <Button
          variant="primary"
          disabled={!name.trim()}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add department
        </Button>
      </Card>
    </div>
  );
}
