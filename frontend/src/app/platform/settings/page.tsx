"use client";

// Platform settings (tabs General, Email, Billing, Security). Only fields the
// server already has are shown and edited.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Card, LoadingState, PageHeader } from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";

type Section = Record<string, string | number | boolean | null>;

const LABELS: Record<string, string> = {
  platform_name: "Platform name",
  support_email: "Support email",
  support_phone: "Support phone",
  sender_name: "Sender name",
  reply_to: "Reply-to email",
  cliff_protection: "Cliff protection",
  fees_paid_by: "Gateway fees paid by",
  grace_period_days: "Grace period (days)",
  invoice_due_days: "Invoice due (days)",
  max_additional_admins: "Additional school admins allowed",
};

function SectionForm({ name, values }: { name: string; values: Section }) {
  const [draft, setDraft] = useState<Section>(values);
  const save = useAction(
    () =>
      ok(api.PATCH("/api/v1/platform/settings", { body: { [name]: draft } })),
    { invalidate: [["platform", "settings"]], done: "Settings saved." },
  );
  return (
    <Card className="grid max-w-[var(--form-max)] gap-3">
      {Object.entries(draft).map(([key, value]) =>
        typeof value === "boolean" ? (
          <label key={key} className="flex min-h-11 items-center gap-2">
            <input
              type="checkbox"
              className="size-5"
              checked={value}
              onChange={(e) => setDraft({ ...draft, [key]: e.target.checked })}
            />
            {LABELS[key] ?? key}
          </label>
        ) : (
          <Field key={key} label={LABELS[key] ?? key}>
            {(f) => (
              <Input
                {...f}
                value={value ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    [key]:
                      typeof value === "number"
                        ? Number(e.target.value)
                        : e.target.value,
                  })
                }
              />
            )}
          </Field>
        ),
      )}
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
  );
}

export default function PlatformSettingsPage() {
  const { data, isPending } = useApi(["platform", "settings"], () =>
    ok(api.GET("/api/v1/platform/settings")),
  );
  if (isPending || !data) return <LoadingState />;
  const all = data as unknown as Record<string, Section>;
  const tabs = [
    ["general", "General"],
    ["email", "Email"],
    ["billing", "Billing"],
    ["security", "Security"],
  ].filter(([k]) => all[k!]);
  return (
    <>
      <PageHeader title="Platform settings" />
      <Tabs
        label="Platform settings"
        tabs={tabs.map(([k, label]) => ({
          value: k!,
          label: label!,
          content: <SectionForm name={k!} values={all[k!]!} />,
        }))}
      />
    </>
  );
}
