"use client";

// Assessment structure (NAVIGATION "Assessment structure"): per level, Scores
// or Skill ratings, and the components that add up to 100 (locked once scores exist).
import Link from "next/link";
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

type Component = Schemas["Component"];
type Level = "nursery" | "primary" | "junior_secondary" | "senior_secondary";

export function totalMessage(components: Component[]): string {
  const total = components.reduce(
    (sum, c) => sum + (Number(c.max_score) || 0),
    0,
  );
  if (total === 100) return "Total 100";
  return total < 100
    ? `Total ${total}. Add ${100 - total} more to reach 100.`
    : `Total ${total}. Remove ${total - 100} to get back to 100.`;
}

function Structure({ level, mode }: { level: Level; mode: string }) {
  const key = ["school", "structure", level];
  const { data, isPending } = useApi(key, () =>
    ok(
      api.GET("/api/v1/school/assessment-structures/{level}", {
        params: { path: { level } },
      }),
    ),
  );
  const [rows, setRows] = useState<Component[] | null>(null);
  const switchMode = useAction(
    (to: "scores" | "skill_ratings") =>
      ok(
        api.PUT("/api/v1/school/levels/{level}", {
          params: { path: { level } },
          body: { assessment_mode: to, head_title: null },
        }),
      ),
    {
      invalidate: [[...KEYS.school], key],
      done: (r) =>
        r.applies_from === "next_term"
          ? "Saved. It applies from next term."
          : "Saved.",
    },
  );
  const save = useAction(
    (components: Component[]) =>
      ok(
        api.PUT("/api/v1/school/assessment-structures/{level}", {
          params: { path: { level } },
          body: { components },
        }),
      ),
    { invalidate: [key], done: "Assessment structure saved." },
  );
  if (isPending || !data) return <LoadingState />;
  const components = rows ?? data.components;
  const total = components.reduce(
    (sum, c) => sum + (Number(c.max_score) || 0),
    0,
  );
  const labels = components.map((c) => c.label.trim());
  const problem = components.some((c) => !c.name.trim())
    ? "Name is missing."
    : components.some((c) => !c.label.trim())
      ? "Short label is missing."
      : new Set(labels).size !== labels.length
        ? "Short labels must be different."
        : null;
  const set = (i: number, key: keyof Component, value: string) =>
    setRows(
      components.map((c, j) =>
        j === i
          ? { ...c, [key]: key === "max_score" ? Number(value) : value }
          : c,
      ),
    );
  return (
    <Card className="grid gap-4">
      <fieldset className="flex flex-wrap gap-2">
        <legend className="mb-2 text-sm font-medium">Assessment mode</legend>
        <Button
          variant={mode === "scores" ? "primary" : "secondary"}
          aria-pressed={mode === "scores"}
          onClick={() => mode !== "scores" && switchMode.mutate("scores")}
        >
          Scores
        </Button>
        <Button
          variant={mode === "skill_ratings" ? "primary" : "secondary"}
          aria-pressed={mode === "skill_ratings"}
          onClick={() =>
            mode !== "skill_ratings" && switchMode.mutate("skill_ratings")
          }
        >
          Skill ratings
        </Button>
      </fieldset>
      {mode === "skill_ratings" ? (
        <p>
          {`${LEVELS[level]} uses Skill ratings.`}{" "}
          <Link
            className="text-primary underline"
            href="/school/setup?tab=skills"
          >
            Set up learning areas and skills
          </Link>
        </p>
      ) : (
        <>
          {data.locked ? (
            <p
              role="note"
              className="rounded-md bg-warning-soft px-3 py-2 text-warning-ink"
            >
              Scores have been entered for this term, so this structure is
              locked. Changes you save will apply from next term.
            </p>
          ) : null}
          {components.map((c, i) => (
            <div
              key={i}
              className="grid grid-cols-2 gap-2 md:grid-cols-[2fr_1fr_1fr_auto] md:items-end"
            >
              <Field label="Name">
                {(f) => (
                  <Input
                    {...f}
                    value={c.name}
                    onChange={(e) => set(i, "name", e.target.value)}
                  />
                )}
              </Field>
              <Field label="Short label">
                {(f) => (
                  <Input
                    {...f}
                    value={c.label}
                    onChange={(e) => set(i, "label", e.target.value)}
                  />
                )}
              </Field>
              <Field label="Max score">
                {(f) => (
                  <Input
                    {...f}
                    type="number"
                    min={1}
                    max={100}
                    value={c.max_score}
                    onChange={(e) => set(i, "max_score", e.target.value)}
                  />
                )}
              </Field>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setRows(components.filter((_, j) => j !== i))}
              >
                Remove
              </Button>
            </div>
          ))}
          <p
            role="status"
            className={total === 100 ? "text-success-ink" : "text-warning-ink"}
          >
            {totalMessage(components)}
          </p>
          {problem ? (
            <p role="alert" className="text-danger">
              {problem}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              disabled={components.length >= 8}
              onClick={() =>
                setRows([...components, { name: "", label: "", max_score: 10 }])
              }
            >
              Add component
            </Button>
            <Button
              variant="primary"
              disabled={total !== 100 || Boolean(problem)}
              busy={save.isPending}
              onClick={() => save.mutate(components)}
            >
              Save
            </Button>
          </div>
          {components.length >= 8 ? (
            <p className="text-sm text-muted">
              You can have up to 8 components.
            </p>
          ) : null}
        </>
      )}
    </Card>
  );
}

export function AssessmentTab() {
  const levels = useLevelsOn();
  if (!levels.length) return <LoadingState />;
  return (
    <Tabs
      label="Levels"
      tabs={levels.map((l) => ({
        value: l.level,
        label: LEVELS[l.level] ?? l.level,
        content: (
          <Structure level={l.level as Level} mode={l.assessment_mode} />
        ),
      }))}
    />
  );
}
