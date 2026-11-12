"use client";

// Approvals: sheets waiting for the principal. A sheet a reviewer covers waits
// for review first (D-142); the person who submitted can't approve (D-052).
import { DataTable } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { waitsForApproval } from "@/components/results/approvals";

export default function ApprovalsPage() {
  const { data, isPending, isError, refetch } = useApi(
    ["school", "sheets"],
    () => ok(api.GET("/api/v1/school/sheets")),
  );
  const approve = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/sheets/{sheet_id}/approve", {
          params: { path: { sheet_id: id } },
        }),
      ),
    {
      invalidate: [
        ["school", "sheets"],
        ["dashboard", "school"],
      ],
      done: "Sheet approved.",
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="sheets" onRetry={() => void refetch()} />;
  const waiting = data.filter(waitsForApproval);
  return (
    <>
      <PageHeader title="Approvals" />
      <DataTable
        caption="Waiting for approval"
        rows={waiting}
        rowKey={(s) => s.id}
        empty="No sheets are waiting for your approval."
        columns={[
          { key: "class", header: "Class", cell: (s) => s.class_name },
          { key: "name", header: "Sheet", cell: (s) => s.name },
          {
            key: "status",
            header: "Status",
            cell: (s) => <StatusBadge status={s.status} />,
          },
          {
            key: "act",
            header: "",
            cell: (s) => (
              <Button
                size="sm"
                variant="primary"
                busy={approve.isPending && approve.variables === s.id}
                onClick={() => approve.mutate(s.id)}
              >
                Approve
              </Button>
            ),
          },
        ]}
      />
      <h2 className="mt-8 mb-3 text-xl font-semibold">All sheets this term</h2>
      <DataTable
        caption="All sheets"
        rows={data}
        rowKey={(s) => s.id}
        empty="No sheets yet."
        columns={[
          { key: "class", header: "Class", cell: (s) => s.class_name },
          { key: "name", header: "Sheet", cell: (s) => s.name },
          {
            key: "status",
            header: "Status",
            cell: (s) => <StatusBadge status={s.status} />,
          },
        ]}
      />
    </>
  );
}
