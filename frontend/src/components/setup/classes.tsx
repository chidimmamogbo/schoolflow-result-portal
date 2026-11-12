"use client";

// Classes by level, only for levels switched on for the school (v0.5).
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Card, LoadingState } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, LEVELS, useClasses, useSchool } from "@/lib/api/school";

type Level = "nursery" | "primary" | "junior_secondary" | "senior_secondary";

export function useLevelsOn() {
  const { data } = useSchool();
  return (data?.levels ?? []).filter((l) => l.enabled);
}

export function ClassesTab() {
  const { data: classes, isPending } = useClasses();
  const levels = useLevelsOn();
  const [v, setV] = useState({ level: "", name: "" });
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/classes", {
          body: { level: v.level as Level, name: v.name.trim() },
        }),
      ),
    {
      invalidate: [[...KEYS.classes]],
      done: "Class added.",
      onDone: () => setV({ ...v, name: "" }),
    },
  );
  if (isPending) return <LoadingState />;
  return (
    <div className="grid gap-4">
      {levels.map((level) => {
        const rows = (classes ?? []).filter((c) => c.level === level.level);
        return (
          <Card key={level.level}>
            <h3 className="mb-3 text-lg font-semibold">
              {LEVELS[level.level]}
            </h3>
            {rows.length ? (
              <ul className="grid gap-2">
                {rows.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-center gap-3">
                    <Link
                      className="font-medium text-primary hover:underline"
                      href={`/school/setup/classes/${c.id}`}
                    >
                      {c.name}
                    </Link>
                    <span className="text-muted">
                      {c.arms.length === 1 && !c.arms[0]?.name
                        ? "One class"
                        : `Arms ${c.arms.map((a) => a.name).join(", ") || "none yet"}`}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted">No classes yet.</p>
            )}
          </Card>
        );
      })}
      <Card className="grid gap-3 md:grid-cols-3 md:items-end">
        <Field label="Level">
          {(f) => (
            <Select
              {...f}
              value={v.level}
              onChange={(e) => setV({ ...v, level: e.target.value })}
            >
              <option value="">Choose</option>
              {levels.map((l) => (
                <option key={l.level} value={l.level}>
                  {LEVELS[l.level]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Class name" hint="For example JSS 1 or Primary 4.">
          {(f) => (
            <Input
              {...f}
              value={v.name}
              onChange={(e) => setV({ ...v, name: e.target.value })}
            />
          )}
        </Field>
        <Button
          variant="primary"
          disabled={!v.level || !v.name.trim()}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add class
        </Button>
      </Card>
    </div>
  );
}
