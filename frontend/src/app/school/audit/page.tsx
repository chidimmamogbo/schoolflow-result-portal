"use client";

// Audit trail: who changed what, when and why, newest first.
import { useState } from "react";

import { Button } from "@/components/ui/button";
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

const PAGE = 50;

export default function AuditPage() {
  const [limit, setLimit] = useState(PAGE);
  const { data, isPending, isError, refetch } = useApi(["audit", limit], () =>
    ok(
      api.GET("/api/v1/school/audit", {
        params: { query: { limit, offset: 0 } },
      }),
    ),
  );
  return (
    <>
      <PageHeader title="Audit trail" />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="the audit trail" onRetry={() => void refetch()} />
      ) : !data.events.length ? (
        <EmptyState title="Nothing recorded yet." />
      ) : (
        <ol className="grid gap-2">
          {data.events.map((e) => (
            <li key={e.id}>
              <Card className="py-3 md:py-3">
                <p>
                  <span className="font-medium">
                    {e.actor_name ?? "SchoolFlow (automatic)"}
                  </span>{" "}
                  <span className="text-muted">
                    {e.action.replaceAll("_", " ").replace(".", ": ")}
                  </span>
                  {e.revision ? ` · revision ${e.revision}` : ""}
                </p>
                {e.reason ? <p>{`Reason: ${e.reason}`}</p> : null}
                <p className="text-sm text-muted">{dateTime(e.created_at)}</p>
              </Card>
            </li>
          ))}
        </ol>
      )}
      {data?.has_more ? (
        <Button className="mt-4" onClick={() => setLimit(limit + PAGE)}>
          Show more
        </Button>
      ) : null}
    </>
  );
}
