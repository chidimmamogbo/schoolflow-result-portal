"use client";

// Email log: every queued, sent and failed email (never its contents).
import { DataTable } from "@/components/ui/data-table";
import { LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { dateTime } from "@/lib/format";

export default function EmailLogPage() {
  const { data, isPending } = useApi(["platform", "emails"], () =>
    ok(
      api.GET("/api/v1/platform/email-log", {
        params: { query: { limit: 200 } },
      }),
    ),
  );
  return (
    <>
      <PageHeader title="Email log" />
      {isPending ? (
        <LoadingState />
      ) : (
        <DataTable
          caption="Email log"
          rows={data ?? []}
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
          ]}
        />
      )}
    </>
  );
}
