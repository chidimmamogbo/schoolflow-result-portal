"use client";

// Report templates: per level, the style and which blocks show; the footer
// (report ID, revision, date and QR) always shows and stays last (D-170).
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/form";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { LEVELS } from "@/lib/api/school";
import type { Schemas } from "@/lib/api/types";

type Template = Schemas["TemplateOut"];
type Level = "nursery" | "primary" | "junior_secondary" | "senior_secondary";
const STYLES = {
  modern: "Modern",
  classic: "Classic",
  compact: "Compact",
  early_years: "Early years",
} as const;

function blockName(block: string): string {
  return block.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
}

function Editor({ template }: { template: Template }) {
  const settings = template.settings as {
    blocks?: string[];
    hidden?: string[];
  };
  const [style, setStyle] = useState(template.style);
  const [hidden, setHidden] = useState<string[]>(settings.hidden ?? []);
  const [version, setVersion] = useState(0);
  const save = useAction(
    () =>
      ok(
        api.PUT("/api/v1/school/report-templates/{level}", {
          params: { path: { level: template.level as Level } },
          body: {
            style: style as keyof typeof STYLES,
            head_title: null,
            settings: { ...template.settings, hidden },
          },
        }),
      ),
    {
      invalidate: [["report-templates"]],
      done: "Template saved as a new version.",
      onDone: () => setVersion(version + 1),
    },
  );
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
      <Card className="grid content-start gap-3">
        <p className="text-sm text-muted">
          {template.version ? `Version ${template.version}` : "Not saved yet"}
        </p>
        <Field label="Style">
          {(f) => (
            <Select
              {...f}
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {Object.entries(STYLES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <fieldset className="grid gap-1">
          <legend className="mb-1 text-sm font-medium">Show block</legend>
          {(settings.blocks ?? []).map((b) => (
            <label key={b} className="flex min-h-11 items-center gap-2">
              <input
                type="checkbox"
                className="size-5"
                disabled={b === "footer"}
                checked={!hidden.includes(b)}
                onChange={(e) =>
                  setHidden(
                    e.target.checked
                      ? hidden.filter((h) => h !== b)
                      : [...hidden, b],
                  )
                }
              />
              {blockName(b)}
              {b === "footer" ? " (always shown)" : ""}
            </label>
          ))}
        </fieldset>
        <div>
          <Button
            variant="primary"
            busy={save.isPending}
            onClick={() => save.mutate(undefined)}
          >
            Save
          </Button>
        </div>
      </Card>
      <Card className="p-0 md:p-0">
        <iframe
          key={version}
          title={`Preview, ${LEVELS[template.level]}`}
          src={`/api/v1/school/report-templates/${template.level}/preview.html`}
          className="h-[70vh] w-full rounded-lg bg-white"
        />
      </Card>
    </div>
  );
}

export default function TemplatesPage() {
  const { data, isPending, isError, refetch } = useApi(
    ["report-templates"],
    () => ok(api.GET("/api/v1/school/report-templates")),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return (
      <ErrorState thing="report templates" onRetry={() => void refetch()} />
    );
  return (
    <>
      <PageHeader title="Report templates" />
      <Tabs
        label="Templates by level"
        tabs={data.map((t) => ({
          value: t.level,
          label: LEVELS[t.level] ?? t.level,
          content: <Editor template={t} />,
        }))}
      />
    </>
  );
}
