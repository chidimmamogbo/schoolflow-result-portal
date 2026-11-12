"use client";

// One correction: what looks wrong, the timeline, and the school's answer.
// Rejecting or asking for more needs a message (D-174).
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ReasonDialog } from "@/components/ui/dialog";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge, statusLabel } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { dateTime } from "@/lib/format";

type Status =
  "investigating" | "needs_more_information" | "resolved" | "rejected";

export default function CorrectionPage() {
  const { id } = useParams<{ id: string }>();
  const key = ["corrections", id];
  const { data, isPending, isError, refetch } = useApi(key, () =>
    ok(
      api.GET("/api/v1/corrections/{request_id}", {
        params: { path: { request_id: id } },
      }),
    ),
  );
  const [asking, setAsking] = useState<Status | null>(null);
  const move = useAction(
    (v: { status: Status; message: string | null }) =>
      ok(
        api.POST("/api/v1/corrections/{request_id}/move", {
          params: { path: { request_id: id } },
          body: v,
        }),
      ),
    {
      invalidate: [key, ["corrections"]],
      done: "Updated.",
      onDone: () => setAsking(null),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the request" onRetry={() => void refetch()} />;
  const open = !["resolved", "rejected"].includes(data.status);
  return (
    <>
      <PageHeader
        title={`${data.number}: ${data.student_name}`}
        caption={`${data.class_name} · ${data.term} · ${data.subject ?? data.learning_area ?? "Whole report"}`}
        actions={<StatusBadge status={data.status} />}
      />
      <div className="grid gap-4">
        <Card>
          <h2 className="mb-2 font-semibold">What looks wrong</h2>
          <p className="whitespace-pre-line">{data.explanation}</p>
          <p className="mt-2 text-sm text-muted">{`Report ${data.report_code}, revision ${data.revision}`}</p>
        </Card>
        <Card>
          <h2 className="mb-2 font-semibold">Timeline</h2>
          <ol className="grid gap-2">
            {data.events.map((e, i) => (
              <li key={i}>
                <span className="font-medium">{statusLabel(e.to_status)}</span>
                {e.actor_name ? ` by ${e.actor_name}` : ""}{" "}
                <span className="text-sm text-muted">
                  {dateTime(e.created_at)}
                </span>
                {e.message ? <p className="text-muted">{e.message}</p> : null}
              </li>
            ))}
          </ol>
        </Card>
        {open ? (
          <div className="flex flex-wrap gap-2">
            {data.status === "open" ? (
              <Button
                busy={move.isPending}
                onClick={() =>
                  move.mutate({ status: "investigating", message: null })
                }
              >
                Investigate
              </Button>
            ) : null}
            <Button onClick={() => setAsking("needs_more_information")}>
              Ask for more information
            </Button>
            <Link
              className={buttonVariants({ variant: "secondary" })}
              href="/school/publish"
            >
              Open publish results
            </Link>
            <Button onClick={() => setAsking("resolved")}>Mark resolved</Button>
            <Button variant="danger" onClick={() => setAsking("rejected")}>
              Reject
            </Button>
          </div>
        ) : null}
      </div>
      <ReasonDialog
        open={asking !== null}
        onOpenChange={(o) => (o ? null : setAsking(null))}
        title={asking ? statusLabel(asking) : ""}
        label="Message (required)"
        confirmLabel="Send"
        busy={move.isPending}
        onConfirm={(message) =>
          asking && move.mutate({ status: asking, message })
        }
      />
    </>
  );
}
