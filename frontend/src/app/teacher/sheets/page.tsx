"use client";

// My result sheets: score and rating sheets grouped by class (UI_REVIEW teacher fixes).
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";

type Item = {
  key: string;
  id: string | null;
  kind: "scores" | "ratings";
  className: string;
  name: string;
  status: string;
  armId: string;
  whatId: string;
};

export default function SheetsPage() {
  const router = useRouter();
  const scores = useApi(["sheets", "mine"], () =>
    ok(api.GET("/api/v1/sheets")),
  );
  const ratings = useApi(["rating-sheets", "mine"], () =>
    ok(api.GET("/api/v1/rating-sheets")),
  );
  const [search, setSearch] = useState("");
  const open = useAction(
    async (item: Item) => {
      if (item.id) return { id: item.id, kind: item.kind };
      if (item.kind === "scores")
        return {
          id: (
            await ok(
              api.POST("/api/v1/sheets", {
                body: { arm_id: item.armId, subject_id: item.whatId },
              }),
            )
          ).id,
          kind: item.kind,
        };
      return {
        id: (
          await ok(
            api.POST("/api/v1/rating-sheets", {
              body: { arm_id: item.armId, learning_area_id: item.whatId },
            }),
          )
        ).id,
        kind: item.kind,
      };
    },
    { onDone: (r) => router.push(`/teacher/sheets/${r.id}?kind=${r.kind}`) },
  );
  const items = useMemo<Item[]>(() => {
    const all: Item[] = [
      ...(scores.data ?? []).map((s) => ({
        key: `s${s.arm_id}${s.subject_id}`,
        id: s.id,
        kind: "scores" as const,
        className: s.class_name,
        name: s.subject_name,
        status: s.status,
        armId: s.arm_id,
        whatId: s.subject_id,
      })),
      ...(ratings.data ?? []).map((s) => ({
        key: `r${s.arm_id}${s.learning_area_id}`,
        id: s.id,
        kind: "ratings" as const,
        className: s.class_name,
        name: s.learning_area_name,
        status: s.status,
        armId: s.arm_id,
        whatId: s.learning_area_id,
      })),
    ];
    const text = search.trim().toLowerCase();
    return all.filter(
      (i) => !text || `${i.name} ${i.className}`.toLowerCase().includes(text),
    );
  }, [scores.data, ratings.data, search]);
  if (scores.isPending || ratings.isPending) return <LoadingState />;
  if (scores.isError || ratings.isError)
    return (
      <ErrorState
        thing="your sheets"
        onRetry={() => {
          void scores.refetch();
          void ratings.refetch();
        }}
      />
    );
  const classes = [...new Set(items.map((i) => i.className))];
  return (
    <>
      <PageHeader title="My result sheets" />
      <Input
        aria-label="Search by subject or class"
        placeholder="Search by subject or class"
        className="mb-4 max-w-sm"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {!items.length ? (
        <EmptyState
          title={search ? "No sheets match." : "No result sheets yet."}
          body={
            search ? undefined : "Your principal will assign your subjects."
          }
        />
      ) : null}
      <div className="grid gap-4">
        {classes.map((name) => (
          <section key={name} aria-label={name}>
            <h2 className="mb-2 text-lg font-semibold">{name}</h2>
            <div className="grid gap-2 md:grid-cols-2">
              {items
                .filter((i) => i.className === name)
                .map((i) => (
                  <Card
                    key={i.key}
                    className="flex items-center justify-between gap-2"
                  >
                    <div>
                      <p className="font-semibold">{i.name}</p>
                      <p className="text-sm text-muted">
                        {i.kind === "scores" ? "Score sheet" : "Rating sheet"}
                      </p>
                      <StatusBadge status={i.status} />
                    </div>
                    <Button
                      variant={
                        i.status === "returned_for_correction"
                          ? "primary"
                          : "secondary"
                      }
                      busy={open.isPending && open.variables?.key === i.key}
                      onClick={() => open.mutate(i)}
                    >
                      Open
                    </Button>
                  </Card>
                ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
