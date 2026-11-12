"use client";

// My class (NAVIGATION "My class"): times school opened, each pupil's comment,
// attendance and trait ratings, then Submit class sections. Assistants save only.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import type { Schemas } from "@/lib/api/types";

type View = Schemas["ClassView"];
type Pupil = View["pupils"][number];

function PupilCard({
  armId,
  pupil,
  view,
  invalidate,
}: {
  armId: string;
  pupil: Pupil;
  view: View;
  invalidate: unknown[];
}) {
  const [comment, setComment] = useState(pupil.comment ?? "");
  const [present, setPresent] = useState(
    pupil.times_present === null ? "" : String(pupil.times_present),
  );
  const [ratings, setRatings] = useState<Record<string, number>>(pupil.ratings);
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/form-class/{arm_id}/students/{enrolment_id}/entry", {
          params: { path: { arm_id: armId, enrolment_id: pupil.enrolment_id } },
          body: {
            comment: comment.trim() || null,
            times_present: present === "" ? null : Number(present),
            ratings,
          },
        }),
      ),
    { invalidate: [invalidate], done: "Saved." },
  );
  const tooMany =
    view.times_school_opened !== null &&
    present !== "" &&
    Number(present) > view.times_school_opened;
  return (
    <Card className="grid gap-3">
      <h3 className="font-semibold">
        {`${pupil.first_name} ${pupil.surname}`}
        {pupil.average ? (
          <span className="ml-2 text-sm font-normal text-muted">{`Average ${pupil.average}`}</span>
        ) : null}
      </h3>
      <Field label="Comment" hint={`${comment.length} of 300 characters`}>
        {(f) => (
          <Textarea
            {...f}
            maxLength={300}
            disabled={!view.can_edit}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        )}
      </Field>
      {pupil.suggested_comments.length && view.can_edit ? (
        <div className="flex flex-wrap gap-2" aria-label="Suggestions">
          {pupil.suggested_comments.map((s) => (
            <Button
              key={s}
              size="sm"
              variant="ghost"
              onClick={() => setComment(s)}
            >
              {s}
            </Button>
          ))}
        </div>
      ) : null}
      <Field
        label="Times present"
        error={
          tooMany ? "Can't be more than the times school opened." : undefined
        }
      >
        {(f) => (
          <Input
            {...f}
            inputMode="numeric"
            disabled={!view.can_edit}
            value={present}
            onChange={(e) => setPresent(e.target.value)}
          />
        )}
      </Field>
      {view.traits.length ? (
        <div className="grid gap-2 md:grid-cols-3">
          {view.traits.map((t) => (
            <Field key={t.id} label={t.name}>
              {(f) => (
                <Select
                  {...f}
                  disabled={!view.can_edit}
                  value={ratings[t.id] ?? ""}
                  onChange={(e) =>
                    setRatings({ ...ratings, [t.id]: Number(e.target.value) })
                  }
                >
                  <option value="">Not yet</option>
                  {[5, 4, 3, 2, 1].map((n) => (
                    <option key={n} value={n}>
                      {view.key[String(n)] ? `${n} ${view.key[String(n)]}` : n}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          ))}
        </div>
      ) : null}
      {view.can_edit ? (
        <div>
          <Button
            disabled={tooMany}
            busy={save.isPending}
            onClick={() => save.mutate(undefined)}
          >
            Save
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

function ClassSections({ armId }: { armId: string }) {
  const key = ["form-class", armId];
  const { data, isPending, isError, refetch } = useApi(key, () =>
    ok(
      api.GET("/api/v1/form-class/{arm_id}", {
        params: { path: { arm_id: armId } },
      }),
    ),
  );
  const sheet = useApi(["broadsheet", armId], () =>
    ok(
      api.GET("/api/v1/form-class/{arm_id}/broadsheet", {
        params: { path: { arm_id: armId } },
      }),
    ),
  );
  const [opened, setOpened] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);
  const saveDays = useAction(
    () =>
      ok(
        api.PUT("/api/v1/form-class/{arm_id}/attendance-days", {
          params: { path: { arm_id: armId } },
          body: { times_school_opened: Number(opened) },
        }),
      ),
    { invalidate: [key], done: "Saved." },
  );
  const submit = useAction(
    () =>
      ok(
        api.POST("/api/v1/form-class/{arm_id}/sections/submit", {
          params: { path: { arm_id: armId } },
        }),
      ),
    {
      invalidate: [key],
      done: "Class sections submitted.",
      onDone: () => setAsk(false),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="your class" onRetry={() => void refetch()} />;
  return (
    <>
      <PageHeader
        title={`My class: ${data.class_name}`}
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
      <Tabs
        label="My class"
        tabs={[
          {
            value: "sections",
            label: "Class sections",
            content: (
              <div className="grid gap-4">
                <Card className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                  <Field label="Times school opened">
                    {(f) => (
                      <Input
                        {...f}
                        inputMode="numeric"
                        disabled={!data.can_edit}
                        value={
                          opened ??
                          (data.times_school_opened === null
                            ? ""
                            : String(data.times_school_opened))
                        }
                        onChange={(e) => setOpened(e.target.value)}
                      />
                    )}
                  </Field>
                  {data.can_edit ? (
                    <Button
                      disabled={opened === null || !/^\d+$/.test(opened)}
                      busy={saveDays.isPending}
                      onClick={() => saveDays.mutate(undefined)}
                    >
                      Save
                    </Button>
                  ) : null}
                </Card>
                <p role="status">{`${data.counts.with_comment} of ${data.counts.pupils} have a comment · ${data.counts.with_attendance} of ${data.counts.pupils} have attendance`}</p>
                {data.pupils.map((p) => (
                  <PupilCard
                    key={p.enrolment_id}
                    armId={armId}
                    pupil={p}
                    view={data}
                    invalidate={key}
                  />
                ))}
                {data.can_submit ? (
                  <div>
                    <Button variant="primary" onClick={() => setAsk(true)}>
                      Submit class sections
                    </Button>
                  </div>
                ) : null}
              </div>
            ),
          },
          {
            value: "subjects",
            label: "All subjects",
            content: sheet.data ? (
              <ul className="grid gap-2">
                {sheet.data.subjects.map((s) => (
                  <li key={s.id} className="flex items-center gap-2">
                    {s.name} <StatusBadge status={s.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <LoadingState />
            ),
          },
        ]}
      />
      <ConfirmDialog
        open={ask}
        onOpenChange={setAsk}
        title={`Submit class sections for ${data.class_name}?`}
        confirmLabel="Submit"
        busy={submit.isPending}
        onConfirm={() => submit.mutate(undefined)}
      />
    </>
  );
}

export default function MyClassPage() {
  const { data, isPending } = useApi(["form-class"], () =>
    ok(api.GET("/api/v1/form-class")),
  );
  if (isPending) return <LoadingState />;
  const first = data?.[0];
  if (!first)
    return (
      <EmptyState title="You are not a form teacher or class teacher this term." />
    );
  return <ClassSections armId={first.arm_id} />;
}
