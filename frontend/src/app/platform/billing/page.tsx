"use client";

// Billing (super admin): generate the term's invoices, void with a reason,
// record a manual payment. Amounts are the server's, in kobo.
import { useState } from "react";

import { PKEYS, useBillingSchools } from "@/components/platform/data";
import { Button } from "@/components/ui/button";
import { Dialog, ReasonDialog } from "@/components/ui/dialog";
import { DataTable } from "@/components/ui/data-table";
import { Field, Input } from "@/components/ui/form";
import { LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

export default function PlatformBillingPage() {
  const schools = useBillingSchools();
  const invoices = useApi([...PKEYS.invoices], () =>
    ok(api.GET("/api/v1/platform/invoices")),
  );
  const [voiding, setVoiding] = useState<string | null>(null);
  const [manual, setManual] = useState<string | null>(null);
  const [ref, setRef] = useState({ reference: "", note: "" });
  const [skipped, setSkipped] = useState<{ name: string; reason: string }[]>(
    [],
  );
  const keys = [[...PKEYS.invoices], [...PKEYS.billing]];
  const generate = useAction(
    () =>
      ok(
        api.POST("/api/v1/platform/invoices/generate", {
          body: { school_id: null, adjustment_students: null },
        }),
      ),
    {
      invalidate: keys,
      done: (r) => `${r.created.length} invoices made.`,
      onDone: (r) => setSkipped(r.skipped),
    },
  );
  const voidIt = useAction(
    (reason: string) =>
      ok(
        api.POST("/api/v1/platform/invoices/{invoice_id}/void", {
          params: { path: { invoice_id: voiding ?? "" } },
          body: { reason },
        }),
      ),
    {
      invalidate: keys,
      done: "Invoice voided.",
      onDone: () => setVoiding(null),
    },
  );
  const record = useAction(
    () =>
      ok(
        api.POST("/api/v1/platform/invoices/{invoice_id}/manual-payment", {
          params: { path: { invoice_id: manual ?? "" } },
          body: { reference: ref.reference.trim(), note: ref.note.trim() },
        }),
      ),
    {
      invalidate: keys,
      done: "Payment recorded.",
      onDone: () => setManual(null),
    },
  );
  const names = new Map((schools.data ?? []).map((s) => [s.id, s.name]));
  return (
    <>
      <PageHeader
        title="Billing"
        actions={
          <Button
            variant="primary"
            busy={generate.isPending}
            onClick={() => generate.mutate(undefined)}
          >
            Generate invoices for the term
          </Button>
        }
      />
      {skipped.length ? (
        <ul className="mb-4 text-muted">
          {skipped.map((s) => (
            <li key={s.name}>{`${s.name}: ${s.reason}`}</li>
          ))}
        </ul>
      ) : null}
      {invoices.isPending ? (
        <LoadingState />
      ) : (
        <DataTable
          caption="Invoices"
          rows={invoices.data ?? []}
          rowKey={(i) => i.id}
          empty="No schools to bill yet."
          columns={[
            {
              key: "school",
              header: "School",
              cell: (i) => names.get(i.school_id) ?? "School",
            },
            { key: "term", header: "Term", cell: (i) => i.term },
            {
              key: "students",
              header: "Students",
              numeric: true,
              cell: (i) => i.billable_students,
            },
            {
              key: "amount",
              header: "Amount",
              numeric: true,
              cell: (i) => money(i.amount_kobo),
            },
            {
              key: "cliff",
              header: "Cliff protection",
              cell: (i) => (i.cliff_cap_applied ? "Capped" : "Not applied"),
            },
            { key: "due", header: "Due", cell: (i) => date(i.due_on) },
            {
              key: "status",
              header: "Status",
              cell: (i) => <StatusBadge status={i.status} />,
            },
            {
              key: "act",
              header: "",
              cell: (i) =>
                i.status === "unpaid" ? (
                  <span className="flex gap-1">
                    <Button size="sm" onClick={() => setManual(i.id)}>
                      Record payment
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setVoiding(i.id)}
                    >
                      Void
                    </Button>
                  </span>
                ) : null,
            },
          ]}
        />
      )}
      <ReasonDialog
        open={voiding !== null}
        onOpenChange={(o) => (o ? null : setVoiding(null))}
        title="Void this invoice?"
        confirmLabel="Void invoice"
        danger
        busy={voidIt.isPending}
        onConfirm={(r) => voidIt.mutate(r)}
      />
      <Dialog
        open={manual !== null}
        onOpenChange={(o) => (o ? null : setManual(null))}
        title="Record a manual payment"
        footer={
          <>
            <Button onClick={() => setManual(null)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!ref.reference.trim() || !ref.note.trim()}
              busy={record.isPending}
              onClick={() => record.mutate(undefined)}
            >
              Record payment
            </Button>
          </>
        }
      >
        <Field label="Bank reference">
          {(f) => (
            <Input
              {...f}
              value={ref.reference}
              onChange={(e) => setRef({ ...ref, reference: e.target.value })}
            />
          )}
        </Field>
        <Field label="Note">
          {(f) => (
            <Input
              {...f}
              value={ref.note}
              onChange={(e) => setRef({ ...ref, note: e.target.value })}
            />
          )}
        </Field>
      </Dialog>
    </>
  );
}
