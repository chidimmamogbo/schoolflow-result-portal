"use client";

// Back from Paystack: only the signature-checked webhook marks an invoice paid
// (D-178), so this page reads our own record every 3 seconds, for up to two
// minutes, until it says so.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Card, LoadingState, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";

const POLL_MS = 3000;
const GIVE_UP_MS = 120_000;

function Confirming() {
  const params = useSearchParams();
  const reference = params.get("reference") ?? params.get("trxref") ?? "";
  const [gaveUp, setGaveUp] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setGaveUp(true), GIVE_UP_MS);
    return () => clearTimeout(timer);
  }, []);
  const { data, isError } = useQuery({
    queryKey: ["billing", "verify", reference],
    queryFn: () =>
      ok(
        api.GET("/api/v1/school/payments/verify", {
          params: { query: { reference } },
        }),
      ),
    enabled: Boolean(reference) && !gaveUp,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "succeeded" || status === "failed") return false;
      return POLL_MS;
    },
  });
  if (data?.status === "succeeded") {
    return (
      <div className="grid gap-4">
        <p role="status">{`Payment received.${data.receipt_number ? ` Receipt ${data.receipt_number}.` : ""}`}</p>
        <Link
          className={buttonVariants({ variant: "primary" })}
          href={`/school/billing/invoices/${data.invoice_id}`}
        >
          View receipt
        </Link>
      </div>
    );
  }
  if (data?.status === "failed" || isError || !reference || gaveUp) {
    return (
      <div className="grid gap-4">
        <p role="alert">
          {
            "We couldn't confirm this payment yet. If money left your account, it will show on the billing page once Paystack tells us."
          }
        </p>
        <Link
          className={buttonVariants({ variant: "secondary" })}
          href="/school/billing"
        >
          Back to billing
        </Link>
      </div>
    );
  }
  return (
    <LoadingState label="Confirming your payment. This usually takes a few seconds." />
  );
}

export default function CallbackPage() {
  return (
    <>
      <PageHeader title="Billing" />
      <Card className="max-w-lg">
        <Suspense>
          <Confirming />
        </Suspense>
      </Card>
    </>
  );
}
