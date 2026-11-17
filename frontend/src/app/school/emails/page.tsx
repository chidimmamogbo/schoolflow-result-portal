"use client";

// Emails: this school's email statuses, newest first (CHANGE 2026-11-12 B).
// Status only: never an email's contents or scores.
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { dateTime } from "@/lib/format";

export default function EmailsPage() {
  const { data, isPending, isError, refetch } = useApi(
    ["school", "emails"],
    () => ok(api.GET("/api/v1/school/emails")),
  );
  return (
    <>
      <PageHeader title="Emails" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="email status" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Emails"
          rows={data}
          rowKey={(e) => e.id}
          empty="No emails yet."
          columns={[
            { key: "to", header: "To", cell: (e) => e.to_address },
            {
              key: "type",
              header: "Email",
              cell: (e) => e.type.replaceAll("_", " "),
            },
            {
              key: "status",
              header: "Status",
              cell: (e) => <StatusBadge status={e.status} />,
            },
            {
              key: "tries",
              header: "Tries",
              numeric: true,
              cell: (e) => e.attempts,
            },
            {
              key: "when",
              header: "Queued",
              cell: (e) => dateTime(e.created_at),
            },
            {
              key: "sent",
              header: "Sent",
              cell: (e) => (e.sent_at ? dateTime(e.sent_at) : ""),
            },
          ]}
        />
      )}
    </>
  );
}
