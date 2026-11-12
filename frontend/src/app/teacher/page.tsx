"use client";

// The teacher's home: their sheets, their form class and their attention count (D-179).
import Link from "next/link";

import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";

export default function TeacherHome() {
  const { data, isPending, isError, refetch } = useApi(
    ["dashboard", "staff"],
    () => ok(api.GET("/api/v1/dashboard/staff")),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="your page" onRetry={() => void refetch()} />;
  const s = data.sheets;
  return (
    <>
      <PageHeader title="Home" caption={data.term ?? undefined} />
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h2 className="font-semibold">My sheets</h2>
          <p className="tabular text-3xl font-bold">{s.to_do + s.returned}</p>
          <p className="text-muted">
            {`to do, of ${s.total}`}
            {s.returned ? ` · ${s.returned} returned` : ""}
          </p>
          <Link className="text-primary underline" href="/teacher/sheets">
            Open sheets
          </Link>
        </Card>
        {data.my_class.map((c) => (
          <Card key={c.arm_id}>
            <h2 className="font-semibold">{`My class: ${c.class_name}`}</h2>
            <p className="my-2">
              <StatusBadge status={c.status} />
            </p>
            <Link className="text-primary underline" href="/teacher/my-class">
              Open My class
            </Link>
          </Card>
        ))}
        {data.attention ? (
          <Card>
            <h2 className="font-semibold">Students needing attention</h2>
            <p className="tabular text-3xl font-bold">
              {data.attention.subject_results + data.attention.skills}
            </p>
            <Link className="text-primary underline" href="/teacher/attention">
              View list
            </Link>
          </Card>
        ) : null}
      </div>
    </>
  );
}
