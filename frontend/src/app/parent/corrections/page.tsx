"use client";

// A parent's correction requests and their status.
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { date } from "@/lib/format";

export default function ParentCorrectionsPage() {
  const { data, isPending, isError, refetch } = useApi(["corrections"], () =>
    ok(api.GET("/api/v1/corrections")),
  );
  return (
    <>
      <PageHeader title="Corrections" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="your requests" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Corrections"
          rows={data.requests}
          rowKey={(r) => r.id}
          empty="No requests yet. Use Report a problem on a result."
          columns={[
            { key: "number", header: "Request", cell: (r) => r.number },
            { key: "student", header: "Child", cell: (r) => r.student_name },
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
