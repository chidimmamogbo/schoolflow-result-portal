"use client";

// Grading (NAVIGATION "Grading"): the pass mark and each Scores level's grade
// bands, which must cover 0 to 100 with no gaps or overlaps.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Card, LoadingState } from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";
import { useLevelsOn } from "@/components/setup/classes";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { KEYS, LEVELS } from "@/lib/api/school";
import type { Schemas } from "@/lib/api/types";

type Band = Schemas["Band"];
type Level = "nursery" | "primary" | "junior_secondary" | "senior_secondary";

export function bandProblem(bands: Band[]): string | null {
  const sorted = [...bands].sort((a, b) => a.min_score - b.min_score);
  const grades = new Set<string>();
  let next = 0;
  for (const band of sorted) {
    if (!band.grade.trim()) return "Every band needs a grade.";
    if (grades.has(band.grade)) return `Grade ${band.grade} is used twice.`;
    grades.add(band.grade);
    if (band.min_score > band.max_score)
      return `${band.grade} starts above where it ends.`;
    if (band.min_score > next)
      return `No grade covers ${next} to ${band.min_score - 1}.`;
    if (band.min_score < next)
      return `${band.grade} overlaps the band below it.`;
    next = band.max_score + 1;
  }
  return next === 101 ? null : `No grade covers ${next} to 100.`;
}

function Bands({ level, initial }: { level: Level; initial: Band[] }) {
  const [bands, setBands] = useState(initial);
  const problem = bandProblem(bands);
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/school/grading/{level}/bands", {
          params: { path: { level } },
          body: { bands },
        }),
      ),
    { invalidate: [[...KEYS.grading]], done: "Grade bands saved." },
  );
  const set = (i: number, key: keyof Band, value: string) =>
    setBands(
      bands.map((b, j) =>
        j === i
          ? {
              ...b,
              [key]:
                key === "grade" || key === "remark" ? value : Number(value),
            }
          : b,
      ),
    );
  return (
    <Card className="grid gap-3">
      <h3 className="text-lg font-semibold">{`Grade bands: ${LEVELS[level]}`}</h3>
      {bands.map((b, i) => (
        <div
          key={i}
          className="grid grid-cols-2 gap-2 md:grid-cols-[1fr_1fr_1fr_2fr_auto] md:items-end"
        >
          <Field label="Grade">
            {(f) => (
              <Input
                {...f}
                value={b.grade}
                onChange={(e) => set(i, "grade", e.target.value)}
              />
            )}
          </Field>
          <Field label="From">
            {(f) => (
              <Input
                {...f}
                type="number"
                min={0}
                max={100}
                value={b.min_score}
                onChange={(e) => set(i, "min_score", e.target.value)}
              />
            )}
          </Field>
          <Field label="To">
            {(f) => (
              <Input
                {...f}
                type="number"
                min={0}
                max={100}
                value={b.max_score}
                onChange={(e) => set(i, "max_score", e.target.value)}
              />
            )}
          </Field>
          <Field label="Remark">
            {(f) => (
              <Input
                {...f}
                value={b.remark}
                onChange={(e) => set(i, "remark", e.target.value)}
              />
            )}
          </Field>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setBands(bands.filter((_, j) => j !== i))}
          >
            Remove
          </Button>
        </div>
      ))}
      <p role="status" className={problem ? "text-danger" : "text-success-ink"}>
        {problem ?? "Covers 0 to 100"}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() =>
            setBands([
              ...bands,
              { grade: "", min_score: 0, max_score: 0, remark: "" },
            ])
          }
        >
          Add band
        </Button>
        <Button
          variant="primary"
          disabled={Boolean(problem)}
          busy={save.isPending}
          onClick={() => save.mutate(undefined)}
        >
          Save
        </Button>
      </div>
    </Card>
  );
}

export function GradingTab() {
  const { data, isPending } = useApi([...KEYS.grading], () =>
    ok(api.GET("/api/v1/school/grading")),
  );
  const levels = useLevelsOn().filter((l) => l.assessment_mode === "scores");
  const [mark, setMark] = useState<string | null>(null);
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/school/grading/pass-mark", {
          body: { pass_mark: Number(mark) },
        }),
      ),
    { invalidate: [[...KEYS.grading]], done: "Pass mark saved." },
  );
  if (isPending || !data) return <LoadingState />;
  const value = mark ?? String(data.pass_mark);
  const bad = !/^\d{1,3}$/.test(value) || Number(value) > 100;
  return (
    <div className="grid gap-4">
      <Card className="grid max-w-md gap-3">
        <Field
          label="Pass mark"
          hint="Results below this mark appear in Students needing attention."
          error={
            bad ? "Pass mark must be a whole number from 0 to 100." : undefined
          }
        >
          {(f) => (
            <Input
              {...f}
              inputMode="numeric"
              value={value}
              onChange={(e) => setMark(e.target.value)}
            />
          )}
        </Field>
        <div>
          <Button
            variant="primary"
            disabled={bad || mark === null}
            busy={save.isPending}
            onClick={() => save.mutate(undefined)}
          >
            Save
          </Button>
        </div>
      </Card>
      {levels.length ? (
        <Tabs
          label="Levels"
          tabs={levels.map((l) => ({
            value: l.level,
            label: LEVELS[l.level] ?? l.level,
            content: (
              <Bands
                level={l.level as Level}
                initial={data.levels[l.level]?.grade_bands ?? []}
              />
            ),
          }))}
        />
      ) : null}
    </div>
  );
}
