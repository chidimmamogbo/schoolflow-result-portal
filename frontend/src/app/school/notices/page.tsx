"use client";

// The school's notices: post, see reach, archive.
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date } from "@/lib/format";

export default function SchoolNoticesPage() {
  const { data, isPending, isError, refetch } = useApi(
    ["school", "notices"],
    () => ok(api.GET("/api/v1/school/notices")),
  );
  const archive = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/school/notices/{notice_id}/archive", {
          params: { path: { notice_id: id } },
        }),
      ),
    { invalidate: [["school", "notices"]], done: "Notice archived." },
  );
  return (
    <>
      <PageHeader
        title="Notices"
        actions={
          <Link
            className={buttonVariants({ variant: "primary" })}
            href="/school/notices/new"
          >
            Post notice
          </Link>
        }
      />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="notices" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Notices"
          rows={data.notices}
          rowKey={(n) => n.id}
          empty="No notices yet."
          columns={[
            {
              key: "title",
              header: "Title",
              cell: (n) => `${n.pinned ? "Pinned: " : ""}${n.title}`,
            },
            {
              key: "reach",
              header: "Read",
              numeric: true,
              cell: (n) => `${n.reads} of ${n.recipients}`,
            },
            { key: "date", header: "Posted", cell: (n) => date(n.created_at) },
            {
              key: "status",
              header: "Status",
              cell: (n) => (n.status === "archived" ? "Archived" : "Published"),
            },
            {
              key: "act",
              header: "",
              cell: (n) =>
                n.status === "published" && n.kind === "manual" ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => archive.mutate(n.id)}
                  >
                    Archive
                  </Button>
                ) : null,
            },
          ]}
        />
      )}
    </>
  );
}
