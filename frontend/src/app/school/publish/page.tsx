"use client";

// Publish results (NAVIGATION "Publish results"): the checklist, principal's
// comments, then Publish with the exact warning; a published class reopens
// only with a reason (corrections create a new revision).
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog, ReasonDialog } from "@/components/ui/dialog";
import { Field, Select, Textarea } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { armNames, useClasses } from "@/lib/api/school";

function Comments({
  armId,
  invalidate,
}: {
  armId: string;
  invalidate: unknown[];
}) {
  const { data } = useApi(["form-class", armId], () =>
    ok(
      api.GET("/api/v1/form-class/{arm_id}", {
        params: { path: { arm_id: armId } },
      }),
    ),
  );
  const [all, setAll] = useState("");
  const [each, setEach] = useState<Record<string, string>>({});
  const save = useAction(
    (comments: { enrolment_id: string; comment: string }[]) =>
      ok(
        api.PUT("/api/v1/school/publications/{arm_id}/principal-comments", {
          params: { path: { arm_id: armId } },
          body: { comments },
        }),
      ),
    { invalidate: [invalidate], done: "Comments saved." },
  );
  if (!data) return <LoadingState />;
  const pupils = data.pupils;
  return (
    <Card className="grid gap-3">
      <h2 className="text-xl font-semibold">Principal&apos;s comments</h2>
      <div className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
        <Field
          label="Comment"
          hint="Students who already have a comment keep it."
        >
          {(f) => (
            <Textarea
              {...f}
              placeholder="Write a comment"
              maxLength={300}
              value={all}
              onChange={(e) => setAll(e.target.value)}
            />
          )}
        </Field>
        <Button
          disabled={!all.trim()}
          busy={save.isPending}
          onClick={() =>
            save.mutate(
              pupils
                .filter((p) => !each[p.enrolment_id]?.trim())
                .map((p) => ({
                  enrolment_id: p.enrolment_id,
                  comment: all.trim(),
                })),
            )
          }
        >{`Apply to ${pupils.length} students`}</Button>
      </div>
      {pupils.map((p) => (
        <Field key={p.enrolment_id} label={`${p.first_name} ${p.surname}`}>
          {(f) => (
            <Textarea
              {...f}
              maxLength={300}
              value={each[p.enrolment_id] ?? ""}
              onChange={(e) =>
                setEach({ ...each, [p.enrolment_id]: e.target.value })
              }
            />
          )}
        </Field>
      ))}
      <div>
        <Button
          busy={save.isPending}
          disabled={!Object.values(each).some((v) => v.trim())}
          onClick={() =>
            save.mutate(
              Object.entries(each)
                .filter(([, v]) => v.trim())
                .map(([enrolment_id, comment]) => ({
                  enrolment_id,
                  comment: comment.trim(),
                })),
            )
          }
        >
          Save comments
        </Button>
      </div>
    </Card>
  );
}

export default function PublishPage() {
  const { data: classes } = useClasses();
  const names = armNames(classes);
  const [arm, setArm] = useState("");
  const [ask, setAsk] = useState<"publish" | "reopen" | null>(null);
  const key = ["publication", arm];
  const { data: ready, isPending } = useApi(
    key,
    () =>
      ok(
        api.GET("/api/v1/school/publications/{arm_id}", {
          params: { path: { arm_id: arm } },
        }),
      ),
    Boolean(arm),
  );
  const publish = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/publications/{arm_id}/publish", {
          params: { path: { arm_id: arm } },
        }),
      ),
    {
      invalidate: [key, ["dashboard", "school"]],
      done: (r) => `${r.published} report cards published.`,
      onDone: () => setAsk(null),
    },
  );
  const reopen = useAction(
    (reason: string) =>
      ok(
        api.POST("/api/v1/school/publications/{arm_id}/reopen", {
          params: { path: { arm_id: arm } },
          body: {
            reason,
            sections: true,
            sheet_ids: [],
            correction_request_id: null,
          },
        }),
      ),
    {
      invalidate: [key],
      done: "Class reopened for a correction.",
      onDone: () => setAsk(null),
    },
  );
  const className = names.get(arm) ?? "";
  return (
    <>
      <PageHeader title="Publish results" />
      <Field label="Class">
        {(f) => (
          <Select
            {...f}
            className="max-w-sm"
            value={arm}
            onChange={(e) => setArm(e.target.value)}
          >
            <option value="">Choose a class</option>
            {[...names.entries()]
              .sort((a, b) => a[1].localeCompare(b[1]))
              .map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
          </Select>
        )}
      </Field>
      {!arm ? (
        <EmptyState title="Choose a class to see what it needs." />
      ) : isPending || !ready ? (
        <LoadingState />
      ) : (
        <div className="mt-6 grid gap-6">
          <Card>
            <div className="mb-3 flex items-center gap-2">
              <h2 className="text-xl font-semibold">{ready.class_name}</h2>
              <StatusBadge status={ready.status} />
            </div>
            {ready.status === "published" ? (
              <p>Published. Any change needs a correction with a reason.</p>
            ) : ready.problems.length ? (
              <ul className="list-disc pl-5">
                {ready.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            ) : (
              <p>Ready to publish.</p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              {ready.status === "published" ? (
                <Button onClick={() => setAsk("reopen")}>
                  Reopen for a correction
                </Button>
              ) : (
                <Button
                  variant="primary"
                  disabled={!ready.ready}
                  onClick={() => setAsk("publish")}
                >
                  Publish
                </Button>
              )}
            </div>
          </Card>
          {ready.status === "published" ? null : (
            <Comments armId={arm} invalidate={key} />
          )}
        </div>
      )}
      <ConfirmDialog
        open={ask === "publish"}
        onOpenChange={(o) => setAsk(o ? "publish" : null)}
        title={`Publish ${className} results?`}
        description="Parents and students will be notified and results become final. Any later change needs a correction with a reason."
        confirmLabel="Publish"
        busy={publish.isPending}
        onConfirm={() => publish.mutate(undefined)}
      />
      <ReasonDialog
        open={ask === "reopen"}
        onOpenChange={(o) => setAsk(o ? "reopen" : null)}
        title={`Reopen ${className}?`}
        confirmLabel="Reopen"
        busy={reopen.isPending}
        onConfirm={(r) => reopen.mutate(r)}
      />
    </>
  );
}
