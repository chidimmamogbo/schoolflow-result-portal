"use client";

// Billing (BillingV5): the plan, amount due and Pay now. The amount always
// comes from the server's invoice; the browser only asks for a checkout link.
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

export default function BillingPage() {
  const card = useApi(["billing", "card"], () =>
    ok(api.GET("/api/v1/school/billing")),
  );
  const invoices = useApi(["billing", "invoices"], () =>
    ok(api.GET("/api/v1/school/invoices")),
  );
  const pay = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/school/invoices/{invoice_id}/pay", {
          params: { path: { invoice_id: id } },
        }),
      ),
    {
      onDone: (checkout) => window.location.assign(checkout.checkout_url),
    },
  );
  if (card.isPending) return <LoadingState />;
  if (card.isError)
    return <ErrorState thing="billing" onRetry={() => void card.refetch()} />;
  const b = card.data;
  if (!b.billing_enabled)
    return (
      <>
        <PageHeader title="Billing" />
        <EmptyState
          title="Your school is on a free pilot."
          body="There is nothing to pay."
        />
      </>
    );
  const unpaid =
    b.current_invoice?.status === "unpaid" ? b.current_invoice : null;
  return (
    <>
      <PageHeader title="Billing" actions={<StatusBadge status={b.status} />} />
      <div className="grid gap-6">
        <Card className="grid gap-2 md:grid-cols-2">
          <div>
            <p className="text-sm text-muted">Amount due</p>
            <p className="tabular text-3xl font-bold">
              {money(b.amount_due_kobo ?? 0)}
            </p>
            {b.due_on ? (
              <p className="text-muted">{`Due ${date(b.due_on)}`}</p>
            ) : null}
            {unpaid ? (
              <Button
                className="mt-3"
                variant="primary"
                busy={pay.isPending}
                onClick={() => pay.mutate(unpaid.id)}
              >
                Pay now
              </Button>
            ) : null}
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted">Plan</dt>
            <dd>
              {b.plan ?? "None"}{" "}
              <span className="ml-1 rounded-full bg-primary-soft px-2 text-primary">
                Your plan
              </span>
            </dd>
            <dt className="text-muted">Billable students</dt>
            <dd className="tabular">{b.billable_students ?? 0}</dd>
            <dt className="text-muted">Price per student</dt>
            <dd className="tabular">
              {b.price_per_student_kobo
                ? money(b.price_per_student_kobo)
                : "None"}
            </dd>
            {b.next_renewal_on ? (
              <>
                <dt className="text-muted">Next term begins</dt>
                <dd>{date(b.next_renewal_on)}</dd>
              </>
            ) : null}
            {b.projected_next_term_kobo ? (
              <>
                <dt className="text-muted">Next term (estimate)</dt>
                <dd className="tabular">{money(b.projected_next_term_kobo)}</dd>
              </>
            ) : null}
          </dl>
        </Card>
        <section>
          <h2 className="mb-3 text-xl font-semibold">Invoices</h2>
          {invoices.data ? (
            <DataTable
              caption="Invoices"
              rows={invoices.data}
              rowKey={(i) => i.id}
              empty="No invoices yet."
              columns={[
                {
                  key: "term",
                  header: "Term",
                  cell: (i) => (
                    <Link
                      className="font-medium text-primary hover:underline"
                      href={`/school/billing/invoices/${i.id}`}
                    >
                      {i.term}
                    </Link>
                  ),
                },
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
                { key: "due", header: "Due", cell: (i) => date(i.due_on) },
                {
                  key: "status",
                  header: "Status",
                  cell: (i) => <StatusBadge status={i.status} />,
                },
              ]}
            />
          ) : (
            <LoadingState />
          )}
        </section>
      </div>
    </>
  );
}
