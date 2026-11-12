"use client";

// The reviewer's dashboard: the review queue count and their attention count.
import Link from "next/link";

import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";

export default function ReviewHome() {
  const { data, isPending, isError, refetch } = useApi(
    ["dashboard", "staff"],
    () => ok(api.GET("/api/v1/dashboard/staff")),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="your page" onRetry={() => void refetch()} />;
  return (
    <>
      <PageHeader title="Dashboard" caption={data.term ?? undefined} />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Review queue</h2>
          <p className="tabular text-3xl font-bold">
            {data.review_waiting ?? 0}
          </p>
          <Link className="text-primary underline" href="/review/queue">
            Open review queue
          </Link>
        </Card>
        {data.attention ? (
          <Card>
            <h2 className="font-semibold">Students needing attention</h2>
            <p className="tabular text-3xl font-bold">
              {data.attention.subject_results + data.attention.skills}
            </p>
            <Link className="text-primary underline" href="/review/attention">
              View list
            </Link>
          </Card>
        ) : null}
      </div>
    </>
  );
}
