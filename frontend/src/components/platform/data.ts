"use client";

// Lists the super admin pages share.
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";

export const PKEYS = {
  schools: ["platform", "schools"],
  billing: ["platform", "billing"],
  invoices: ["platform", "invoices"],
  payments: ["platform", "payments"],
  pricing: ["platform", "pricing"],
} as const;

export const FEATURES: [keyof FeatureSet, string][] = [
  ["results", "Results"],
  ["report_cards", "Report cards"],
  ["parent_portal", "Parent portal"],
  ["correction_queue", "Correction queue"],
  ["notice_board", "Notice board"],
  ["email_notifications", "Email notifications"],
];

export type FeatureSet = {
  results: boolean;
  report_cards: boolean;
  parent_portal: boolean;
  correction_queue: boolean;
  notice_board: boolean;
  email_notifications: boolean;
};

export function useBillingSchools() {
  return useApi([...PKEYS.billing, "schools"], () =>
    ok(api.GET("/api/v1/platform/billing/schools")),
  );
}
export function usePlatformSchools(q = "") {
  return useApi([...PKEYS.schools, q], () =>
    ok(
      api.GET("/api/v1/platform/schools", {
        params: { query: q ? { q } : {} },
      }),
    ),
  );
}
