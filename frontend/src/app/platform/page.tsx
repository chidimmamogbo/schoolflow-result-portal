"use client";

// Platform overview (SuperDashboard): schools, billable students, the term's
// money, subscriptions and recent payments.
import Link from "next/link";

import {
  usePlatformSchools,
  useBillingSchools,
} from "@/components/platform/data";
import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Card, LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

export default function PlatformHome() {
  const billing = useBillingSchools();
  const schools = usePlatformSchools();
  const summary = useApi(["platform", "billing", "summary"], () =>
    ok(api.GET("/api/v1/platform/billing/summary")),
  );
  const payments = useApi(["platform", "payments", "recent"], () =>
    ok(
      api.GET("/api/v1/platform/payments", { params: { query: { limit: 5 } } }),
    ),
  );
  if (billing.isPending || schools.isPending) return <LoadingState />;
  const rows = billing.data ?? [];
  const term = summary.data?.[0];
  const names = new Map(rows.map((s) => [s.id, s.name]));
  return (
    <>
      <PageHeader
        title="Platform overview"
        actions={
          <>
            <Link
              className={buttonVariants({ variant: "secondary" })}
              href="/platform/billing"
            >
              Generate invoices
            </Link>
            <Link
              className={buttonVariants({ variant: "primary" })}
              href="/platform/schools/new"
            >
              Create school
            </Link>
          </>
        }
      />
      <section
        aria-label="Totals"
        className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4"
      >
        <Card>
          <p className="text-sm text-muted">Schools</p>
          <p className="tabular text-3xl font-bold">
            {schools.data?.length ?? 0}
          </p>
          <p className="text-sm text-muted">{`${rows.filter((s) => s.billing_enabled).length} billed · ${rows.filter((s) => !s.billing_enabled).length} free pilot`}</p>
        </Card>
        <Card>
          <p className="text-sm text-muted">Billable students</p>
          <p className="tabular text-3xl font-bold">
            {rows.reduce((n, s) => n + s.students, 0).toLocaleString("en-NG")}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-muted">
            {term ? `${term.term} paid` : "Paid"}
          </p>
          <p className="tabular text-3xl font-bold">
            {money(term?.paid_kobo ?? 0)}
          </p>
          <p className="text-sm text-muted">{`of ${money(term?.invoiced_kobo ?? 0)} invoiced`}</p>
        </Card>
        <Card>
          <p className="text-sm text-muted">Outstanding</p>
          <p className="tabular text-3xl font-bold">
            {money(term?.outstanding_kobo ?? 0)}
          </p>
        </Card>
      </section>
      <h2 className="mb-3 text-xl font-semibold">Subscriptions</h2>
      <DataTable
        caption="Subscriptions"
        rows={rows}
        rowKey={(s) => s.id}
        empty="No schools yet."
        columns={[
          {
            key: "name",
            header: "School",
            cell: (s) => (
              <Link
                className="font-medium text-primary hover:underline"
                href={`/platform/schools/${s.id}`}
              >
                {s.name}
              </Link>
            ),
          },
          {
            key: "plan",
            header: "Plan",
            cell: (s) => s.current_invoice?.plan ?? "None",
          },
          {
            key: "students",
            header: "Students",
            numeric: true,
            cell: (s) => s.students,
          },
          {
            key: "amount",
            header: "This term",
            numeric: true,
            cell: (s) =>
              s.current_invoice
                ? money(s.current_invoice.amount_kobo)
                : "Not billed",
          },
          {
            key: "status",
            header: "Status",
            cell: (s) => <StatusBadge status={s.status} />,
          },
        ]}
      />
      <h2 className="mt-8 mb-3 text-xl font-semibold">Recent payments</h2>
      <DataTable
        caption="Recent payments"
        rows={payments.data ?? []}
        rowKey={(p) => p.id}
        empty="No payments yet."
        columns={[
          {
            key: "school",
            header: "School",
            cell: (p) => names.get(p.school_id) ?? "School",
          },
          { key: "date", header: "Date", cell: (p) => date(p.created_at) },
          { key: "ref", header: "Reference", cell: (p) => p.reference },
          {
            key: "amount",
            header: "Amount",
            numeric: true,
            cell: (p) => money(p.amount_kobo),
          },
          {
            key: "status",
            header: "Status",
            cell: (p) => (
              <StatusBadge
                status={p.status === "succeeded" ? "paid" : p.status}
              />
            ),
          },
        ]}
      />
    </>
  );
}
