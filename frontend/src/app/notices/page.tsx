"use client";

// The notice board for every role, labelled with each notice's school (AC17.3).
import { useQueryClient } from "@tanstack/react-query";
import { Pin } from "lucide-react";

import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { dateTime } from "@/lib/format";

export default function NoticesPage() {
  const client = useQueryClient();
  const { data, isPending, isError, refetch } = useApi(
    ["notices", "board"],
    () => ok(api.GET("/api/v1/notices")),
  );
  async function read(id: string) {
    await api.POST("/api/v1/notices/{notice_id}/read", {
      params: { path: { notice_id: id } },
    });
    await client.invalidateQueries({ queryKey: ["notices"] });
  }
  const many = new Set(data?.notices.map((n) => n.school_id)).size > 1;
  return (
    <>
      <PageHeader title="Notices" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="notices" onRetry={() => void refetch()} />
      ) : !data.notices.length ? (
        <EmptyState title="No notices yet." />
      ) : (
        <ul className="grid gap-3">
          {data.notices.map((n) => (
            <li key={n.id}>
              <Card className={n.read ? "" : "border-primary"}>
                <details
                  onToggle={(e) =>
                    e.currentTarget.open && !n.read
                      ? void read(n.id)
                      : undefined
                  }
                >
                  <summary className="flex min-h-11 cursor-pointer flex-wrap items-center gap-2">
                    {n.pinned ? (
                      <Pin
                        className="size-4 text-primary"
                        aria-label="Pinned"
                      />
                    ) : null}
                    <span className="font-semibold">{n.title}</span>
                    {n.read ? null : (
                      <span className="rounded-full bg-primary-soft px-2 text-sm text-primary">
                        New
                      </span>
                    )}
                    <span className="ml-auto text-sm text-muted">
                      {many ? `${n.school_name} · ` : ""}
                      {dateTime(n.created_at)}
                    </span>
                  </summary>
                  <p className="mt-3 whitespace-pre-line">{n.body}</p>
                </details>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
