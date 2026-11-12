"use client";

// CSV import (AC05.1): check the file first, then import every valid row in one go.
import { type FormEvent, useState } from "react";

import { ArmSelect } from "@/components/people/arm-select";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, FormError, Input } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { sendForm } from "@/lib/api/client";
import { problemText, useAction } from "@/lib/api/hooks";
import { KEYS } from "@/lib/api/school";
// The import route answers a preview or a count (its OpenAPI shape is open).
type Preview = {
  rows: {
    row: number;
    admission_number: string;
    surname: string;
    first_name: string;
    errors: string[];
  }[];
  valid: number;
  invalid: number;
};

export default function ImportStudentsPage() {
  const [arm, setArm] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const send = (commit: boolean) => {
    const form = new FormData();
    form.append("file", file as File);
    return sendForm<Preview & { created?: number }>(
      `/api/v1/school/students/import?arm_id=${encodeURIComponent(arm)}&commit=${commit}`,
      form,
    );
  };
  const check = useAction(() => send(false), {
    onDone: (result) => setPreview(result),
  });
  const commit = useAction(() => send(true), {
    invalidate: [[...KEYS.students]],
    done: (result) => `${result.created ?? 0} students imported.`,
    onDone: () => setPreview(null),
  });
  function onCheck(event: FormEvent) {
    event.preventDefault();
    setError(arm && file ? null : "Choose a class and a CSV file.");
    if (arm && file)
      check.mutate(undefined, { onError: (e) => setError(problemText(e)) });
  }
  return (
    <>
      <PageHeader title="Import students" />
      <Card className="mb-6 max-w-[var(--form-max)]">
        <form onSubmit={onCheck} className="grid gap-4" noValidate>
          <FormError message={error} />
          <Field label="Class">
            {(f) => (
              <ArmSelect
                {...f}
                value={arm}
                onChange={(e) => setArm(e.target.value)}
              />
            )}
          </Field>
          <Field
            label="CSV file"
            hint={
              <a
                className="text-primary underline"
                href="/api/v1/school/students/import/template"
              >
                Download the template
              </a>
            }
          >
            {(f) => (
              <Input
                {...f}
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setPreview(null);
                }}
              />
            )}
          </Field>
          <div>
            <Button type="submit" busy={check.isPending}>
              Check file
            </Button>
          </div>
        </form>
      </Card>
      {preview ? (
        <>
          <p className="mb-3" role="status">
            {preview.valid} ready to import, {preview.invalid} with problems.
          </p>
          <DataTable
            caption="Rows in the file"
            rows={preview.rows}
            rowKey={(r) => String(r.row)}
            empty="The file has no rows."
            columns={[
              { key: "row", header: "Row", cell: (r) => r.row, numeric: true },
              {
                key: "number",
                header: "Admission number",
                cell: (r) => r.admission_number,
              },
              {
                key: "name",
                header: "Name",
                cell: (r) => `${r.first_name} ${r.surname}`,
              },
              {
                key: "problems",
                header: "Problems",
                cell: (r) =>
                  r.errors.length ? (
                    <span className="text-danger">{r.errors.join(" ")}</span>
                  ) : (
                    "None"
                  ),
              },
            ]}
          />
          <div className="mt-4">
            <Button
              variant="primary"
              disabled={preview.valid === 0 || preview.invalid > 0}
              busy={commit.isPending}
              onClick={() => commit.mutate(undefined)}
            >
              Import {preview.valid} students
            </Button>
            {preview.invalid > 0 ? (
              <p className="mt-2 text-sm text-muted">
                Fix the rows with problems and check the file again.
              </p>
            ) : null}
          </div>
        </>
      ) : null}
    </>
  );
}
