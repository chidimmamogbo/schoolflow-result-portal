"use client";

// Payments: every payment, with Resend receipt.
import { useBillingSchools } from "@/components/platform/data";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { LoadingState, PageHeader } from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

export default function PaymentsPage() {
  const { data, isPending } = useApi(["platform", "payments", "all"], () =>
    ok(
      api.GET("/api/v1/platform/payments", {
        params: { query: { limit: 200 } },
      }),
    ),
  );
  const schools = useBillingSchools();
  const resend = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/platform/payments/{payment_id}/resend-receipt", {
          params: { path: { payment_id: id } },
        }),
      ),
    { done: "Receipt email sent." },
  );
  const names = new Map((schools.data ?? []).map((s) => [s.id, s.name]));
  return (
    <>
      <PageHeader title="Payments" />
      {isPending ? (
        <LoadingState />
      ) : (
        <DataTable
          caption="Payments"
          rows={data ?? []}
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
              key: "receipt",
              header: "Receipt number",
              cell: (p) => p.receipt_number ?? "",
            },
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
            {
              key: "act",
              header: "",
              cell: (p) =>
                p.status === "succeeded" ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => resend.mutate(p.id)}
                  >
                    Resend receipt
                  </Button>
                ) : null,
            },
          ]}
        />
      )}
    </>
  );
}
