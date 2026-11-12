"use client";

// School settings: contact details, colour and the images used on report
// cards (logo, head's signature, school stamp). The name and code are the
// platform's to change.
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok, sendForm } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, useSchool } from "@/lib/api/school";

const FIELDS = [
  ["email", "School email"],
  ["phone", "Phone"],
  ["address", "Address"],
  ["city", "Town or city"],
  ["state", "State"],
  ["country", "Country"],
] as const;

function Upload({
  purpose,
  label,
}: {
  purpose: "logo" | "signature" | "stamp";
  label: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const upload = useAction(
    () => {
      const form = new FormData();
      form.append("purpose", purpose);
      form.append("file", file as File);
      return sendForm("/api/v1/school/files", form);
    },
    {
      invalidate: [[...KEYS.school]],
      done: `${label} uploaded.`,
    },
  );
  return (
    <div className="grid gap-2 md:grid-cols-[1fr_auto] md:items-end">
      <Field label={label} hint="PNG, JPEG or WebP, up to 1 MB.">
        {(f) => (
          <Input
            {...f}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        )}
      </Field>
      <Button
        disabled={!file}
        busy={upload.isPending}
        onClick={() => upload.mutate(undefined)}
      >
        Upload image
      </Button>
    </div>
  );
}

export default function SchoolSettingsPage() {
  const { data: school, isPending, isError, refetch } = useSchool();
  const [changes, setChanges] = useState<Record<string, string>>({});
  const save = useAction(
    () => ok(api.PATCH("/api/v1/school", { body: changes })),
    {
      invalidate: [[...KEYS.school], ["me"]],
      done: "Saved.",
      onDone: () => setChanges({}),
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return (
      <ErrorState thing="school settings" onRetry={() => void refetch()} />
    );
  const value = (key: string) =>
    changes[key] ?? String(school[key as keyof typeof school] ?? "");
  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(undefined);
  }
  return (
    <>
      <PageHeader
        title="School settings"
        caption={`${school.name} · ${school.code}`}
      />
      <div className="grid gap-6">
        <Card className="max-w-[var(--form-max)]">
          <form onSubmit={submit} className="grid gap-4">
            {FIELDS.map(([key, label]) => (
              <Field key={key} label={label}>
                {(f) => (
                  <Input
                    {...f}
                    value={value(key)}
                    onChange={(e) =>
                      setChanges({ ...changes, [key]: e.target.value })
                    }
                  />
                )}
              </Field>
            ))}
            <Field label="School colour">
              {(f) => (
                <Input
                  {...f}
                  type="color"
                  className="h-11 w-24 p-1"
                  value={value("colour")}
                  onChange={(e) =>
                    setChanges({ ...changes, colour: e.target.value })
                  }
                />
              )}
            </Field>
            <div>
              <Button
                type="submit"
                variant="primary"
                disabled={!Object.keys(changes).length}
                busy={save.isPending}
              >
                Save changes
              </Button>
            </div>
          </form>
        </Card>
        <Card className="grid max-w-[var(--form-max)] gap-4">
          <h2 className="text-xl font-semibold">Report card images</h2>
          <Upload purpose="logo" label="School logo" />
          <Upload purpose="signature" label="Head's signature" />
          <Upload purpose="stamp" label="School stamp" />
        </Card>
      </div>
    </>
  );
}
