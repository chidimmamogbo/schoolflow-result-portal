"use client";

// Pricing table (NAVIGATION "Pricing table"): volume pricing per student per
// term in plans; saving makes a new version; issued invoices never change.
import { useState } from "react";

import { PKEYS } from "@/components/platform/data";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Card, LoadingState, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";
import type { Schemas } from "@/lib/api/types";

type Plan = Schemas["PlanForm"];

export default function PricingPage() {
  const { data, isPending } = useApi([...PKEYS.pricing], () =>
    ok(api.GET("/api/v1/platform/pricing")),
  );
  const versions = useApi([...PKEYS.pricing, "versions"], () =>
    ok(api.GET("/api/v1/platform/pricing/versions")),
  );
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const save = useAction(
    (p: Plan[]) =>
      ok(api.POST("/api/v1/platform/pricing", { body: { plans: p } })),
    {
      invalidate: [[...PKEYS.pricing]],
      done: (r) => `Saved as version ${r.version}.`,
      onDone: () => setPlans(null),
    },
  );
  if (isPending || !data) return <LoadingState />;
  const rows = plans ?? data.plans;
  const set = (i: number, key: keyof Plan, value: string) =>
    setPlans(
      rows.map((p, j) =>
        j === i
          ? {
              ...p,
              [key]:
                key === "name"
                  ? value
                  : key === "price_kobo"
                    ? Math.round(Number(value) * 100)
                    : value === ""
                      ? null
                      : Number(value),
            }
          : p,
      ),
    );
  return (
    <>
      <PageHeader
        title="Pricing table"
        caption={
          data.version ? `Version ${data.version}` : "Defaults, not saved yet"
        }
      />
      <Card className="grid gap-3">
        {rows.map((p, i) => (
          <div
            key={i}
            className="grid grid-cols-2 gap-2 md:grid-cols-4 md:items-end"
          >
            <Field label="Plan">
              {(f) => (
                <Input
                  {...f}
                  value={p.name}
                  onChange={(e) => set(i, "name", e.target.value)}
                />
              )}
            </Field>
            <Field label="From students">
              {(f) => (
                <Input
                  {...f}
                  inputMode="numeric"
                  value={p.min_students}
                  onChange={(e) => set(i, "min_students", e.target.value)}
                />
              )}
            </Field>
            <Field label="To students">
              {(f) => (
                <Input
                  {...f}
                  inputMode="numeric"
                  placeholder="And above"
                  value={p.max_students ?? ""}
                  onChange={(e) => set(i, "max_students", e.target.value)}
                />
              )}
            </Field>
            <Field label="Price per student (₦)">
              {(f) => (
                <Input
                  {...f}
                  inputMode="decimal"
                  value={p.price_kobo / 100}
                  onChange={(e) => set(i, "price_kobo", e.target.value)}
                />
              )}
            </Field>
          </div>
        ))}
        <p className="text-sm text-muted">
          {data.cliff_protection
            ? "Cliff protection is on."
            : "Cliff protection is off."}
        </p>
        {data.price_check.length ? (
          <p
            role="note"
            className="rounded-md bg-warning-soft px-3 py-2 text-warning-ink"
          >{`Price check: a bigger school pays less for ${data.price_check.map((r) => `${r.from_students} to ${r.to_students}`).join(", ")} students.`}</p>
        ) : (
          <p className="text-sm text-success-ink">Price check: no cliffs.</p>
        )}
        <div>
          <Button
            variant="primary"
            disabled={!plans}
            busy={save.isPending}
            onClick={() => plans && save.mutate(plans)}
          >
            Save as new version
          </Button>
        </div>
      </Card>
      <h2 className="mt-8 mb-3 text-xl font-semibold">Version history</h2>
      <ul className="grid gap-2">
        {(versions.data ?? []).map((v) => (
          <li key={v.version}>
            {`Version ${v.version}, ${date(v.created_at)}: `}
            {v.plans.map((p) => `${p.name} ${money(p.price_kobo)}`).join(", ")}
          </li>
        ))}
      </ul>
    </>
  );
}
