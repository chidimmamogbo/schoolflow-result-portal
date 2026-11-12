"use client";

// Schools: search and open each school.
import Link from "next/link";
import { useState } from "react";

import { usePlatformSchools } from "@/components/platform/data";
import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/form";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";

const TYPES: Record<string, string> = {
  nursery_primary: "Nursery and Primary",
  secondary_only: "Secondary only",
  all_levels: "Nursery, Primary and Secondary",
  custom: "Custom",
};

export default function SchoolsPage() {
  const [q, setQ] = useState("");
  const { data, isPending, isError, refetch } = usePlatformSchools(q.trim());
  return (
    <>
      <PageHeader
        title="Schools"
        actions={
          <Link
            className={buttonVariants({ variant: "primary" })}
            href="/platform/schools/new"
          >
            Create school
          </Link>
        }
      />
      <Input
        aria-label="Search schools"
        placeholder="Search by name or code"
        className="mb-4 max-w-sm"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="schools" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Schools"
          rows={data}
          rowKey={(s) => s.id}
          empty="No schools yet."
          columns={[
            {
              key: "name",
              header: "School",
              cell: (s) => (
                <Link
                  className="font-medium text-primary hover:underline"
                  href={`/platform/schools/${s.id}`}
                >
                  {s.name}
                </Link>
              ),
            },
            { key: "code", header: "Code", cell: (s) => s.code },
            {
              key: "type",
              header: "School type",
              cell: (s) => TYPES[s.school_type] ?? s.school_type,
            },
            {
              key: "place",
              header: "Town",
              cell: (s) => `${s.city}, ${s.state}`,
            },
            {
              key: "status",
              header: "Status",
              cell: (s) => <StatusBadge status={s.status} />,
            },
          ]}
        />
      )}
    </>
  );
}
