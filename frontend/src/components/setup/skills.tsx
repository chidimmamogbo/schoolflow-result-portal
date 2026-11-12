"use client";

// Learning areas and skills, the rating scale, and rating traits.
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

type Level = "nursery" | "primary" | "junior_secondary" | "senior_secondary";
type Area = Schemas["AreaOut"];

function AreaCard({ area }: { area: Area }) {
  const [skill, setSkill] = useState("");
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/learning-areas/{area_id}/skills", {
          params: { path: { area_id: area.id } },
          body: { name: skill.trim(), description: null },
        }),
      ),
    {
      invalidate: [[...KEYS.areas]],
      done: "Skill added.",
      onDone: () => setSkill(""),
    },
  );
  return (
    <Card>
      <h4 className="mb-2 font-semibold">{area.name}</h4>
      <ul className="mb-3 list-disc pl-5">
        {area.skills
          .filter((s) => s.is_active)
          .map((s) => (
            <li key={s.id}>{s.name}</li>
          ))}
      </ul>
      <div className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
        <Field label="Skill">
          {(f) => (
            <Input
              {...f}
              value={skill}
              onChange={(e) => setSkill(e.target.value)}
            />
          )}
        </Field>
        <Button
          disabled={!skill.trim()}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add skill
        </Button>
      </div>
    </Card>
  );
}

function Areas({ level }: { level: Level }) {
  const { data, isPending } = useApi([...KEYS.areas, level], () =>
    ok(
      api.GET("/api/v1/school/learning-areas", {
        params: { query: { level } },
      }),
    ),
  );
  const [name, setName] = useState("");
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/learning-areas", {
          body: { level, name: name.trim() },
        }),
      ),
    {
      invalidate: [[...KEYS.areas]],
      done: "Learning area added.",
      onDone: () => setName(""),
    },
  );
  if (isPending) return <LoadingState />;
  return (
    <div className="grid gap-3">
      {(data ?? []).map((area) => (
        <AreaCard key={area.id} area={area} />
      ))}
      <Card className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
        <Field label="Learning area">
          {(f) => (
            <Input
              {...f}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <Button
          variant="primary"
          disabled={!name.trim()}
          busy={add.isPending}
          onClick={() => add.mutate(undefined)}
        >
          Add learning area
        </Button>
      </Card>
    </div>
  );
}

function Scale() {
  const { data } = useApi([...KEYS.scale], () =>
    ok(api.GET("/api/v1/school/rating-scale")),
  );
  if (!data) return null;
  return (
    <Card>
      <h3 className="mb-2 text-lg font-semibold">Rating scale</h3>
      <ul className="grid gap-1">
        {data.points.map((p) => (
          <li key={p.code}>
            {p.name} ({p.code})
            {p.is_attention ? ", flagged in Students needing attention" : ""}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-muted">
        Published reports keep the scale and skills they were published with.
      </p>
    </Card>
  );
}

export function SkillsTab() {
  const levels = useLevelsOn().filter(
    (l) => l.assessment_mode === "skill_ratings",
  );
  return (
    <div className="grid gap-4">
      {levels.length ? (
        <Tabs
          label="Levels"
          tabs={levels.map((l) => ({
            value: l.level,
            label: LEVELS[l.level] ?? l.level,
            content: <Areas level={l.level as Level} />,
          }))}
        />
      ) : (
        <p className="text-muted">
          No level uses Skill ratings. Change it in Assessment.
        </p>
      )}
      <Scale />
    </div>
  );
}

export function TraitsTab() {
  const { data, isPending } = useApi([...KEYS.traits], () =>
    ok(api.GET("/api/v1/school/traits")),
  );
  const [v, setV] = useState({
    name: "",
    domain: "affective" as "affective" | "psychomotor",
  });
  const add = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/traits", {
          body: { name: v.name.trim(), domain: v.domain },
        }),
      ),
    {
      invalidate: [[...KEYS.traits]],
      done: "Trait added.",
      onDone: () => setV({ ...v, name: "" }),
    },
  );
  if (isPending || !data) return <LoadingState />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {(["affective", "psychomotor"] as const).map((domain) => (
        <Card key={domain}>
          <h3 className="mb-2 text-lg font-semibold">
            {domain === "affective" ? "Affective" : "Psychomotor"}
          </h3>
          <ul className="mb-3 list-disc pl-5">
            {data[domain]
              .filter((t) => t.is_active)
              .map((t) => (
                <li key={t.id}>{t.name}</li>
              ))}
          </ul>
          <div className="grid gap-2 md:grid-cols-[2fr_auto] md:items-end">
            <Field label="New trait">
              {(f) => (
                <Input
                  {...f}
                  value={v.domain === domain ? v.name : ""}
                  onChange={(e) => setV({ domain, name: e.target.value })}
                />
              )}
            </Field>
            <Button
              disabled={v.domain !== domain || !v.name.trim()}
              busy={add.isPending}
              onClick={() => add.mutate(undefined)}
            >
              Add trait
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}
