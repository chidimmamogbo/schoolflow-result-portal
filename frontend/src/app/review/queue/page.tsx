"use client";

// Review queue: submitted sheets in the reviewer's scope, oldest first (AT-13.4).
import Link from "next/link";

import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";

export default function ReviewQueue() {
  const { data, isPending, isError, refetch } = useApi(["reviews"], () =>
    ok(api.GET("/api/v1/reviews")),
  );
  return (
    <>
      <PageHeader title="Review queue" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="the review queue" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Review queue"
          rows={data}
          rowKey={(s) => s.id}
          empty="No sheets are waiting for review."
          columns={[
            { key: "class", header: "Class", cell: (s) => s.class_name },
            {
              key: "name",
              header: "Subject",
              cell: (s) => (
                <Link
                  className="font-medium text-primary hover:underline"
                  href={`/review/${s.id}`}
                >
                  {s.name}
                </Link>
              ),
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
