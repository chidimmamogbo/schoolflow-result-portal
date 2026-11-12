"use client";

// Audit log (platform).
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, LoadingState, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { dateTime } from "@/lib/format";

export default function PlatformAuditPage() {
  const [limit, setLimit] = useState(50);
  const { data, isPending } = useApi(["platform", "audit", limit], () =>
    ok(
      api.GET("/api/v1/platform/audit-log", {
        params: { query: { limit, offset: 0 } },
      }),
    ),
  );
  return (
    <>
      <PageHeader title="Audit log" />
      {isPending ? (
        <LoadingState />
      ) : (
        <ol className="grid gap-2">
          {(data ?? []).map((e) => (
            <li key={e.id}>
              <Card className="py-3 md:py-3">
                <p>
                  <span className="font-medium">
                    {e.actor_name ?? "SchoolFlow (automatic)"}
                  </span>{" "}
                  <span className="text-muted">{e.action}</span>
                </p>
                {e.reason ? <p>{`Reason: ${e.reason}`}</p> : null}
                <p className="text-sm text-muted">{dateTime(e.created_at)}</p>
              </Card>
            </li>
          ))}
        </ol>
      )}
      {data && data.length >= limit ? (
        <Button className="mt-4" onClick={() => setLimit(limit + 50)}>
          Show more
        </Button>
      ) : null}
    </>
  );
}
