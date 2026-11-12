"use client";

// Corrections: requests from parents and staff, newest first.
import Link from "next/link";

import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { date } from "@/lib/format";

export default function CorrectionsPage() {
  const { data, isPending, isError, refetch } = useApi(["corrections"], () =>
    ok(api.GET("/api/v1/corrections")),
  );
  return (
    <>
      <PageHeader
        title="Corrections"
        caption={data ? `${data.open} open` : undefined}
      />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="corrections" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Corrections"
          rows={data.requests}
          rowKey={(r) => r.id}
          empty="No correction requests."
          columns={[
            {
              key: "number",
              header: "Request",
              cell: (r) => (
                <Link
                  className="font-medium text-primary hover:underline"
                  href={`/school/corrections/${r.id}`}
                >
                  {r.number}
                </Link>
              ),
            },
            {
              key: "student",
              header: "Student",
              cell: (r) => `${r.student_name}, ${r.class_name}`,
            },
            {
              key: "what",
              header: "About",
              cell: (r) => r.subject ?? r.learning_area ?? "Whole report",
            },
            {
              key: "status",
              header: "Status",
              cell: (r) => <StatusBadge status={r.status} />,
            },
            { key: "date", header: "Sent", cell: (r) => date(r.created_at) },
          ]}
        />
      )}
    </>
  );
}
