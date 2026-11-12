"use client";

// Class page (NAVIGATION "Class page"): arms, the subjects each arm takes, the
// class teacher's assistants and, for Skill ratings classes, learning areas.
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import {
  KEYS,
  LEVELS,
  type Arm,
  useAssignments,
  useClasses,
  useStaff,
  useSubjects,
} from "@/lib/api/school";

function ArmSubjects({ arm, className }: { arm: Arm; className: string }) {
  const { data: subjects } = useSubjects();
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/school/arms/{arm_id}/subjects", {
          params: { path: { arm_id: arm.id } },
          body: { subject_ids: [...chosen] },
        }),
      ),
    { done: "Subjects saved." },
  );
  return (
    <Card>
      <h3 className="mb-2 font-semibold">{`${className}${arm.name}`}</h3>
      <div className="grid gap-1 md:grid-cols-2">
        {(subjects ?? []).map((s) => (
          <label key={s.id} className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              className="size-5"
              checked={chosen.has(s.id)}
              onChange={(e) => {
                const next = new Set(chosen);
                if (e.target.checked) next.add(s.id);
                else next.delete(s.id);
                setChosen(next);
              }}
            />
            {s.name}
          </label>
        ))}
      </div>
      <p className="my-2 text-sm text-muted">
        Tick every subject this arm takes, then save; it replaces the list.
      </p>
      <Button
        variant="primary"
        busy={save.isPending}
        disabled={!chosen.size}
        onClick={() => save.mutate(undefined)}
      >
        Save subjects
      </Button>
    </Card>
  );
}

function Assistants({ arm, className }: { arm: Arm; className: string }) {
  const key = ["school", "assistants", arm.id];
  const { data } = useApi(key, () =>
    ok(
      api.GET("/api/v1/school/arms/{arm_id}/assistants", {
        params: { path: { arm_id: arm.id } },
      }),
    ),
  );
  const { data: staff } = useStaff();
  const { data: assignments } = useAssignments();
  const [who, setWho] = useState("");
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/arms/{arm_id}/assistants", {
          params: { path: { arm_id: arm.id } },
          body: { user_id: who },
        }),
      ),
    { invalidate: [key], done: "Assistant added.", onDone: () => setWho("") },
  );
  const remove = useAction(
    (user: string) =>
      ok(
        api.DELETE("/api/v1/school/arms/{arm_id}/assistants/{user_id}", {
          params: { path: { arm_id: arm.id, user_id: user } },
        }),
      ),
    { invalidate: [key], done: "Assistant removed." },
  );
  const lead = (assignments ?? []).find(
    (a) => a.arm_id === arm.id && a.is_form_teacher,
  );
  const name = `${className}${arm.name}`;
  return (
    <Card className="grid gap-3">
      <h3 className="font-semibold">{name}</h3>
      <p>
        {lead
          ? `Class teacher: ${lead.teacher_name}${lead.teaches_all_subjects ? " (teaches all subjects)" : ""}`
          : "No class teacher yet. Assign one on the teacher's page."}
      </p>
      <h4 className="font-medium">Class teacher assistants</h4>
      <ul className="grid gap-1">
        {(data ?? []).map((a) => (
          <li
            key={a.user_id}
            className="flex items-center justify-between gap-2"
          >
            {a.full_name}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => remove.mutate(a.user_id)}
            >
              Remove
            </Button>
          </li>
        ))}
      </ul>
      {(data?.length ?? 0) >= 2 ? (
        <p className="text-sm text-muted">{`${name} has 2 assistants. Remove one to add another.`}</p>
      ) : (
        <div className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
          <Field label="Teacher">
            {(f) => (
              <Select
                {...f}
                value={who}
                onChange={(e) => setWho(e.target.value)}
              >
                <option value="">Choose a teacher</option>
                {(staff ?? [])
                  .filter((s) => s.role === "teacher" && s.is_active)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.full_name}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          <Button
            disabled={!who}
            busy={add.isPending}
            onClick={() => add.mutate(undefined)}
          >
            Add assistant
          </Button>
        </div>
      )}
      <p className="text-sm text-muted">
        Assistants can enter scores, ratings and comments for this class. Only
        the class teacher can submit.
      </p>
    </Card>
  );
}

function Areas({ classId, level }: { classId: string; level: string }) {
  const { data } = useApi([...KEYS.areas, level], () =>
    ok(
      api.GET("/api/v1/school/learning-areas", {
        params: { query: { level: level as "nursery" } },
      }),
    ),
  );
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/school/classes/{class_id}/learning-areas", {
          params: { path: { class_id: classId } },
          body: { learning_area_ids: [...chosen] },
        }),
      ),
    { done: "Learning areas saved." },
  );
  return (
    <Card>
      <div className="grid gap-1 md:grid-cols-2">
        {(data ?? []).map((a) => (
          <label key={a.id} className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              className="size-5"
              checked={chosen.has(a.id)}
              onChange={(e) => {
                const next = new Set(chosen);
                if (e.target.checked) next.add(a.id);
                else next.delete(a.id);
                setChosen(next);
              }}
            />
            {a.name}{" "}
            <span className="text-muted">({a.skills.length} skills)</span>
          </label>
        ))}
      </div>
      <Button
        className="mt-3"
        variant="primary"
        disabled={!chosen.size}
        busy={save.isPending}
        onClick={() => save.mutate(undefined)}
      >
        Save learning areas
      </Button>
    </Card>
  );
}

export default function ClassPage() {
  const { id } = useParams<{ id: string }>();
  const { data: classes, isPending } = useClasses();
  const [arm, setArm] = useState("");
  const row = classes?.find((c) => c.id === id);
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/classes/{class_id}/arms", {
          params: { path: { class_id: id } },
          body: { name: arm.trim() },
        }),
      ),
    {
      invalidate: [[...KEYS.classes]],
      done: "Arm added.",
      onDone: () => setArm(""),
    },
  );
  if (isPending) return <LoadingState />;
  if (!row) return <EmptyState title="We couldn't find that class." />;
  const skills = row.level === "nursery";
  return (
    <>
      <PageHeader title={row.name} caption={LEVELS[row.level]} />
      <Tabs
        label="Class"
        tabs={[
          {
            value: "overview",
            label: "Overview",
            content: (
              <div className="grid gap-4">
                {row.arms.map((a) => (
                  <Assistants key={a.id} arm={a} className={row.name} />
                ))}
                <Card className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
                  <Field
                    label="Arm"
                    hint="A letter such as A; leave empty for a class with one arm."
                  >
                    {(f) => (
                      <Input
                        {...f}
                        value={arm}
                        onChange={(e) => setArm(e.target.value)}
                      />
                    )}
                  </Field>
                  <Button
                    busy={add.isPending}
                    onClick={() => add.mutate(undefined)}
                  >
                    Add arm
                  </Button>
                </Card>
              </div>
            ),
          },
          skills
            ? {
                value: "areas",
                label: "Learning areas",
                content: <Areas classId={row.id} level={row.level} />,
              }
            : {
                value: "subjects",
                label: "Subjects",
                content: (
                  <div className="grid gap-4">
                    {row.arms.map((a) => (
                      <ArmSubjects key={a.id} arm={a} className={row.name} />
                    ))}
                  </div>
                ),
              },
        ]}
      />
    </>
  );
}
