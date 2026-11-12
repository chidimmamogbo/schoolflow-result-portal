"use client";

// One result sheet: the score grid or the rating grid, Save draft and Submit.
// A change after submission needs a reason (D-143); assistants only save (D-145).
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import {
  type Edits,
  ScoreGrid,
  cellProblem,
} from "@/components/results/score-grid";
import { RatingGrid, type RatingEdits } from "@/components/results/rating-grid";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConfirmDialog, ReasonDialog } from "@/components/ui/dialog";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";

function ScoreSheet({ id }: { id: string }) {
  const key = ["sheet", id];
  const { data, isPending, isError, refetch } = useApi(key, () =>
    ok(
      api.GET("/api/v1/sheets/{sheet_id}", {
        params: { path: { sheet_id: id } },
      }),
    ),
  );
  const [edits, setEdits] = useState<Edits>({});
  const [ask, setAsk] = useState<"reason" | "submit" | null>(null);
  const save = useAction(
    (reason: string | null) => {
      const scores = Object.entries(edits).map(([k, text]) => {
        const [enrolment_id, component_id] = k.split(":") as [string, string];
        return {
          enrolment_id,
          component_id,
          value: text.trim() === "" ? null : Number(text),
        };
      });
      return ok(
        api.PUT("/api/v1/sheets/{sheet_id}/scores", {
          params: { path: { sheet_id: id } },
          body: { scores, reason },
        }),
      );
    },
    {
      invalidate: [key],
      done: "Saved.",
      onDone: () => {
        setEdits({});
        setAsk(null);
      },
    },
  );
  const submit = useAction(
    () =>
      ok(
        api.POST("/api/v1/sheets/{sheet_id}/submit", {
          params: { path: { sheet_id: id } },
        }),
      ),
    {
      invalidate: [key, ["sheets", "mine"]],
      done: "Sheet submitted",
      onDone: () => setAsk(null),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the sheet" onRetry={() => void refetch()} />;
  const max = new Map(data.columns.map((c) => [c.id, c.max_score]));
  const bad = Object.entries(edits).some(([k, v]) =>
    cellProblem(v, max.get(k.split(":")[1] ?? "") ?? 100),
  );
  const changed = Object.keys(edits).length > 0;
  const afterSubmit =
    data.revision > 1 || data.status === "returned_for_correction";
  return (
    <>
      <PageHeader
        title={`${data.subject_name}, ${data.class_name}`}
        actions={<StatusBadge status={data.status} />}
      />
      {data.status_comment ? (
        <p
          role="note"
          className="mb-4 rounded-md bg-warning-soft px-3 py-2 text-warning-ink"
        >
          {data.status_comment}
        </p>
      ) : null}
      <p className="mb-3" role="status">
        {data.counts.missing
          ? `${data.counts.missing} students still need scores.`
          : "No missing scores."}{" "}
        {data.counts.errors ? `${data.counts.errors} errors.` : ""}
      </p>
      <ScoreGrid
        sheet={data}
        edits={edits}
        readOnly={!data.can_edit}
        onEdit={(k, v) => setEdits({ ...edits, [k]: v })}
      />
      {data.can_edit ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            disabled={!changed || bad}
            busy={save.isPending}
            onClick={() => (afterSubmit ? setAsk("reason") : save.mutate(null))}
          >
            Save draft
          </Button>
          <Button
            variant="primary"
            disabled={changed || data.counts.missing > 0}
            onClick={() => setAsk("submit")}
          >
            Submit
          </Button>
          <a
            className={buttonVariants({ variant: "ghost" })}
            href={`/api/v1/sheets/${id}/export.csv`}
          >
            Download CSV
          </a>
          <Link
            className={buttonVariants({ variant: "ghost" })}
            href={`/teacher/sheets/${id}/import`}
          >
            Import CSV
          </Link>
        </div>
      ) : null}
      <ReasonDialog
        open={ask === "reason"}
        onOpenChange={(o) => setAsk(o ? "reason" : null)}
        title="Why are these scores changing?"
        confirmLabel="Save draft"
        busy={save.isPending}
        onConfirm={(reason) => save.mutate(reason)}
      />
      <ConfirmDialog
        open={ask === "submit"}
        onOpenChange={(o) => setAsk(o ? "submit" : null)}
        title={`Submit ${data.subject_name}, ${data.class_name}?`}
        description="You can't change scores after submitting unless the sheet is returned to you."
        confirmLabel="Submit"
        busy={submit.isPending}
        onConfirm={() => submit.mutate(undefined)}
      />
    </>
  );
}

function RatingSheet({ id }: { id: string }) {
  const key = ["rating-sheet", id];
  const { data, isPending, isError, refetch } = useApi(key, () =>
    ok(
      api.GET("/api/v1/rating-sheets/{sheet_id}", {
        params: { path: { sheet_id: id } },
      }),
    ),
  );
  const [edits, setEdits] = useState<RatingEdits>({});
  const [ask, setAsk] = useState(false);
  const save = useAction(
    () => {
      const ratings = Object.entries(edits).map(([k, point_id]) => {
        const [enrolment_id, skill_id] = k.split(":") as [string, string];
        return { enrolment_id, skill_id, point_id };
      });
      return ok(
        api.PUT("/api/v1/rating-sheets/{sheet_id}/ratings", {
          params: { path: { sheet_id: id } },
          body: { ratings, comments: [] },
        }),
      );
    },
    { invalidate: [key], done: "Saved.", onDone: () => setEdits({}) },
  );
  const submit = useAction(
    () =>
      ok(
        api.POST("/api/v1/sheets/{sheet_id}/submit", {
          params: { path: { sheet_id: id } },
        }),
      ),
    {
      invalidate: [key, ["rating-sheets", "mine"]],
      done: "Sheet submitted",
      onDone: () => setAsk(false),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the sheet" onRetry={() => void refetch()} />;
  const changed = Object.keys(edits).length > 0;
  return (
    <>
      <PageHeader
        title={`${data.learning_area_name}, ${data.class_name}`}
        actions={<StatusBadge status={data.status} />}
      />
      <p className="mb-3" role="status">
        {data.counts.missing
          ? `${data.counts.missing} skills not rated yet.`
          : "Every skill is rated."}
      </p>
      <RatingGrid
        sheet={data}
        edits={edits}
        readOnly={!data.can_edit}
        onEdit={(k, p) => setEdits({ ...edits, [k]: p })}
      />
      {data.can_edit ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            disabled={!changed}
            busy={save.isPending}
            onClick={() => save.mutate(undefined)}
          >
            Save draft
          </Button>
          <Button
            variant="primary"
            disabled={changed || data.counts.missing > 0}
            onClick={() => setAsk(true)}
          >
            Submit
          </Button>
        </div>
      ) : null}
      <ConfirmDialog
        open={ask}
        onOpenChange={setAsk}
        title={`Submit ${data.learning_area_name}, ${data.class_name}?`}
        confirmLabel="Submit"
        busy={submit.isPending}
        onConfirm={() => submit.mutate(undefined)}
      />
    </>
  );
}

function Sheet() {
  const { sheetId } = useParams<{ sheetId: string }>();
  const kind = useSearchParams().get("kind");
  return (
    <>
      <Link
        href="/teacher/sheets"
        className="mb-2 inline-block text-primary underline"
      >
        Back to my result sheets
      </Link>
      {kind === "ratings" ? (
        <RatingSheet id={sheetId} />
      ) : (
        <ScoreSheet id={sheetId} />
      )}
    </>
  );
}

export default function SheetPage() {
  return (
    <Suspense>
      <Sheet />
    </Suspense>
  );
}
