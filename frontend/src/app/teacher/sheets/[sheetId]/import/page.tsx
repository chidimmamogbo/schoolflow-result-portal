"use client";

// Import scores from a CSV: check first, then save every row in one go.
import { useParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { sendForm } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";

type Preview = {
  rows?: { row: number; errors: string[] }[];
  valid?: number;
  invalid?: number;
  saved?: number;
};

export default function ImportScoresPage() {
  const { sheetId } = useParams<{ sheetId: string }>();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const send = (commit: boolean) => {
    const form = new FormData();
    form.append("file", file as File);
    return sendForm<Preview>(
      `/api/v1/sheets/${sheetId}/import?commit=${commit}`,
      form,
    );
  };
  const check = useAction(() => send(false), { onDone: setPreview });
  const commit = useAction(() => send(true), {
    invalidate: [["sheet", sheetId]],
    done: "Scores imported.",
    onDone: () => setPreview(null),
  });
  return (
    <>
      <PageHeader title="Import scores" />
      <Card className="grid max-w-[var(--form-max)] gap-4">
        <Field
          label="CSV file"
          hint={
            <a
              className="text-primary underline"
              href={`/api/v1/sheets/${sheetId}/template.csv`}
            >
              Download the template
            </a>
          }
        >
          {(f) => (
            <Input
              {...f}
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setPreview(null);
              }}
            />
          )}
        </Field>
        <div>
          <Button
            disabled={!file}
            busy={check.isPending}
            onClick={() => check.mutate(undefined)}
          >
            Check file
          </Button>
        </div>
        {preview ? (
          <>
            <p role="status">{`${preview.valid ?? 0} rows ready, ${preview.invalid ?? 0} with problems.`}</p>
            <ul className="text-danger">
              {(preview.rows ?? [])
                .filter((r) => r.errors.length)
                .map((r) => (
                  <li key={r.row}>{`Row ${r.row}: ${r.errors.join(" ")}`}</li>
                ))}
            </ul>
            <div>
              <Button
                variant="primary"
                disabled={(preview.invalid ?? 0) > 0}
                busy={commit.isPending}
                onClick={() => commit.mutate(undefined)}
              >
                Import scores
              </Button>
            </div>
          </>
        ) : null}
      </Card>
    </>
  );
}
