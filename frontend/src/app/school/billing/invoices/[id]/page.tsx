"use client";

// One invoice, and its receipt once paid.
import { useParams } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

export default function InvoicePage() {
  const { id } = useParams<{ id: string }>();
  const { data, isPending, isError, refetch } = useApi(
    ["billing", "invoice", id],
    () =>
      ok(
        api.GET("/api/v1/school/invoices/{invoice_id}", {
          params: { path: { invoice_id: id } },
        }),
      ),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the invoice" onRetry={() => void refetch()} />;
  return (
    <>
      <PageHeader
        title={`Invoice, ${data.term}`}
        actions={<StatusBadge status={data.status} />}
      />
      <Card className="grid max-w-xl gap-1">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted">Plan</dt>
          <dd>{data.plan}</dd>
          <dt className="text-muted">Students</dt>
          <dd className="tabular">{`${data.billable_students} × ${money(data.rate_kobo)}`}</dd>
          {data.cliff_cap_applied ? (
            <>
              <dt className="text-muted">Cliff protection</dt>
              <dd>Capped by cliff protection</dd>
            </>
          ) : null}
          <dt className="text-muted">Amount</dt>
          <dd className="tabular font-semibold">{money(data.amount_kobo)}</dd>
          <dt className="text-muted">Due</dt>
          <dd>{date(data.due_on)}</dd>
          {data.paid_at ? (
            <>
              <dt className="text-muted">Paid</dt>
              <dd>{date(data.paid_at)}</dd>
            </>
          ) : null}
          {data.receipt_number ? (
            <>
              <dt className="text-muted">Receipt number</dt>
              <dd>{data.receipt_number}</dd>
            </>
          ) : null}
        </dl>
        {data.receipt_number ? (
          <a
            className={buttonVariants({ variant: "secondary" }) + " mt-3"}
            href={`/api/v1/school/invoices/${id}/receipt.pdf`}
          >
            Download receipt
          </a>
        ) : null}
      </Card>
    </>
  );
}
