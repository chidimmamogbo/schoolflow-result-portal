"use client";

// Reviewing a sheet: read only; Mark reviewed, or Return with a comment (required).
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ScoreGrid } from "@/components/results/score-grid";
import { RatingGrid } from "@/components/results/rating-grid";
import { Button } from "@/components/ui/button";
import { ReasonDialog } from "@/components/ui/dialog";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import type { Schemas } from "@/lib/api/types";

type View = Schemas["SheetView"] | Schemas["RatingSheetView"];

export default function ReviewSheetPage() {
  const { sheetId } = useParams<{ sheetId: string }>();
  const router = useRouter();
  const [returning, setReturning] = useState(false);
  const { data, isPending, isError, refetch } = useApi(
    ["review", sheetId],
    async () =>
      (await ok(
        api.GET("/api/v1/reviews/{sheet_id}", {
          params: { path: { sheet_id: sheetId } },
        }),
      )) as View,
  );
  const review = useAction(
    () =>
      ok(
        api.POST("/api/v1/sheets/{sheet_id}/review", {
          params: { path: { sheet_id: sheetId } },
        }),
      ),
    {
      invalidate: [["reviews"]],
      done: "Marked reviewed.",
      onDone: () => router.push("/review/queue"),
    },
  );
  const back = useAction(
    (comment: string) =>
      ok(
        api.POST("/api/v1/sheets/{sheet_id}/return", {
          params: { path: { sheet_id: sheetId } },
          body: { comment },
        }),
      ),
    {
      invalidate: [["reviews"]],
      done: "Sheet returned.",
      onDone: () => router.push("/review/queue"),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the sheet" onRetry={() => void refetch()} />;
  const name =
    "subject_name" in data ? data.subject_name : data.learning_area_name;
  return (
    <>
      <PageHeader
        title={`${name}, ${data.class_name}`}
        actions={<StatusBadge status={data.status} />}
      />
      {"columns" in data ? (
        <ScoreGrid sheet={data} edits={{}} readOnly onEdit={() => {}} />
      ) : (
        <RatingGrid sheet={data} edits={{}} readOnly onEdit={() => {}} />
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={() => setReturning(true)}>
          Return for correction
        </Button>
        <Button
          variant="primary"
          busy={review.isPending}
          onClick={() => review.mutate(undefined)}
        >
          Mark reviewed
        </Button>
      </div>
      <ReasonDialog
        open={returning}
        onOpenChange={setReturning}
        title="Return this sheet"
        label="Comment (required)"
        confirmLabel="Return"
        busy={back.isPending}
        onConfirm={(c) => back.mutate(c)}
      />
    </>
  );
}
