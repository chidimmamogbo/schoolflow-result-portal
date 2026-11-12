"use client";

// Students: search by name or admission number, filter by class.
import Link from "next/link";
import { useMemo, useState } from "react";

import { ArmSelect } from "@/components/people/arm-select";
import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input } from "@/components/ui/form";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { armNames, fullName, useClasses, useStudents } from "@/lib/api/school";

export default function StudentsPage() {
  const { data, isPending, isError, refetch } = useStudents();
  const { data: classes } = useClasses();
  const [search, setSearch] = useState("");
  const [arm, setArm] = useState("");
  const names = armNames(classes);
  const rows = useMemo(() => {
    const text = search.trim().toLowerCase();
    return (data ?? []).filter(
      (p) =>
        (!arm || p.arm_id === arm) &&
        (!text ||
          fullName(p).toLowerCase().includes(text) ||
          p.admission_number.toLowerCase().includes(text)),
    );
  }, [data, search, arm]);
  return (
    <>
      <PageHeader
        title="Students"
        actions={
          <>
            <Link
              href="/school/students/import"
              className={buttonVariants({ variant: "secondary" })}
            >
              Import students
            </Link>
            <Link
              href="/school/students/new"
              className={buttonVariants({ variant: "primary" })}
            >
              Add student
            </Link>
          </>
        }
      />
      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <Field label="Search">
          {(f) => (
            <Input
              {...f}
              placeholder="Name or admission number"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          )}
        </Field>
        <Field label="Class">
          {(f) => (
            <ArmSelect
              {...f}
              placeholder="All"
              value={arm}
              onChange={(e) => setArm(e.target.value)}
            />
          )}
        </Field>
      </div>
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="students" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Students"
          rows={rows}
          rowKey={(p) => p.id}
          empty={data.length ? "No students match." : "No students yet."}
          cardTitle={(p) => (
            <Link
              href={`/school/students/${p.id}`}
              className="text-primary hover:underline"
            >
              {fullName(p)}
            </Link>
          )}
          columns={[
            {
              key: "name",
              header: "Name",
              hideOnCard: true,
              cell: (p) => (
                <Link
                  href={`/school/students/${p.id}`}
                  className="font-medium text-primary hover:underline"
                >
                  {fullName(p)}
                </Link>
              ),
            },
            {
              key: "number",
              header: "Admission number",
              cell: (p) => p.admission_number,
            },
            {
              key: "class",
              header: "Class",
              cell: (p) =>
                (p.arm_id ? names.get(p.arm_id) : null) ?? "Not in a class",
            },
            {
              key: "status",
              header: "Status",
              cell: (p) => <StatusBadge status={p.status} />,
            },
            {
              key: "login",
              header: "Login",
              cell: (p) => (p.has_login ? "Has login" : "No login"),
            },
          ]}
        />
      )}
    </>
  );
}
