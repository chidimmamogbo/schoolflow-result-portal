// Portal and billing: children grouped by school; Pay now sends no amount (the
// invoice decides) and goes to the checkout; the return page waits for the
// server to confirm; super admin prices are typed in naira and sent in kobo;
// voiding needs a reason.
import "@/test/setup";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test, vi } from "vitest";

import PlatformBillingPage from "@/app/platform/billing/page";
import PricingPage from "@/app/platform/pricing/page";
import CallbackPage from "@/app/school/billing/callback/page";
import BillingPage from "@/app/school/billing/page";
import { PortalHome } from "@/components/portal/portal";
import { renderWithClient } from "@/test/helpers";
import { navigation, server } from "@/test/setup";

const INVOICE = {
  id: "i1",
  school_id: "s1",
  term: "Second Term 2026/2027",
  kind: "term",
  billable_students: 580,
  plan: "Standard",
  rate_kobo: 50_000,
  amount_kobo: 29_000_000,
  cliff_cap_applied: false,
  due_on: "2027-01-05",
  status: "unpaid",
  paid_at: null,
  void_reason: null,
  reference: null,
  receipt_number: null,
  created_at: "2026-12-12T10:00:00Z",
};

test("a parent sees each school's children and can accept a link request", async () => {
  let accepted = false;
  server.use(
    http.get("*/api/v1/me/children", () =>
      HttpResponse.json([
        {
          school_id: "s1",
          school_name: "Greenfield Model College",
          school_code: "GMC",
          colour: "#1E6B45",
          logo_url: null,
          children: [
            {
              student_id: "p1",
              name: "Chukwuemeka Obi",
              admission_number: "GMC/2026/014",
              class_name: "JSS 1A",
              latest: null,
            },
          ],
        },
        {
          school_id: "s2",
          school_name: "Bright Stars Academy",
          school_code: "BSA",
          colour: "#7A1F2B",
          logo_url: null,
          children: [
            {
              student_id: "p2",
              name: "Kosi Obi",
              admission_number: "BSA/2026/007",
              class_name: "Primary 4A",
              latest: null,
            },
          ],
        },
      ]),
    ),
    http.get("*/api/v1/me/link-requests", () =>
      HttpResponse.json(
        accepted
          ? []
          : [
              {
                id: "lr1",
                school_id: "s3",
                school_name: "Royal Crest Schools",
                school_code: "RCS",
                guardian_name: "Ikenna Obi",
                created_at: "2026-12-01T10:00:00Z",
                expires_at: "2026-12-15T10:00:00Z",
              },
            ],
      ),
    ),
    http.post("*/api/v1/me/link-requests/lr1/accept", () => {
      accepted = true;
      return HttpResponse.json({ detail: "Linked." });
    }),
  );
  renderWithClient(<PortalHome base="/parent" title="Home" />);
  expect(
    await screen.findByRole("region", { name: "Greenfield Model College" }),
  ).toHaveTextContent("Chukwuemeka Obi");
  expect(
    screen.getByRole("region", { name: "Bright Stars Academy" }),
  ).toHaveTextContent("Kosi Obi");
  expect(
    screen.getByText("Chukwuemeka's report is not ready yet."),
  ).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: "Accept" }));
  await waitFor(() => expect(accepted).toBe(true));
});

test("Pay now sends no amount and goes to the checkout page", async () => {
  let body: unknown = "untouched";
  const assign = vi.fn();
  Object.defineProperty(window, "location", {
    value: { ...window.location, assign, origin: window.location.origin },
    writable: true,
  });
  server.use(
    http.get("*/api/v1/school/billing", () =>
      HttpResponse.json({
        billing_enabled: true,
        status: "due",
        plan: "Standard",
        billable_students: 580,
        price_per_student_kobo: 50_000,
        amount_due_kobo: 29_000_000,
        due_on: "2027-01-05",
        next_renewal_on: null,
        projected_next_term_kobo: null,
        current_invoice: INVOICE,
      }),
    ),
    http.get("*/api/v1/school/invoices", () => HttpResponse.json([INVOICE])),
    http.post("*/api/v1/school/invoices/i1/pay", async ({ request }) => {
      body = await request.text();
      return HttpResponse.json({
        checkout_url: "https://checkout.paystack.example/abc",
        reference: "SF-1",
      });
    }),
  );
  renderWithClient(<BillingPage />);
  expect(await screen.findAllByText("₦290,000")).not.toHaveLength(0);
  await userEvent.click(screen.getByRole("button", { name: "Pay now" }));
  await waitFor(() =>
    expect(assign).toHaveBeenCalledWith(
      "https://checkout.paystack.example/abc",
    ),
  );
  expect(body).toBe("");
});

test("billing off shows no invoices or payment prompts", async () => {
  server.use(
    http.get("*/api/v1/school/billing", () =>
      HttpResponse.json({ billing_enabled: false, status: "free_pilot" }),
    ),
    http.get("*/api/v1/school/invoices", () => HttpResponse.json([])),
  );
  renderWithClient(<BillingPage />);
  expect(
    await screen.findByText("Your school is on a free pilot."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Pay now" }),
  ).not.toBeInTheDocument();
});

test("the return page waits for the server, then shows the receipt", async () => {
  navigation.search = new URLSearchParams("reference=SF-1");
  let calls = 0;
  server.use(
    http.get("*/api/v1/school/payments/verify", () => {
      calls += 1;
      return HttpResponse.json({
        reference: "SF-1",
        invoice_id: "i1",
        invoice_status: calls > 1 ? "paid" : "unpaid",
        receipt_number: calls > 1 ? "RCT-0001" : null,
        status: calls > 1 ? "succeeded" : "pending",
      });
    }),
  );
  renderWithClient(<CallbackPage />);
  expect(
    await screen.findByText(
      "Confirming your payment. This usually takes a few seconds.",
    ),
  ).toBeInTheDocument();
  // While the server still says pending, nothing claims the payment went through.
  await waitFor(() => expect(calls).toBe(1));
  await new Promise((resolve) => setTimeout(resolve, 300));
  expect(screen.queryByText(/Payment received/)).not.toBeInTheDocument();
  expect(
    await screen.findByText(
      "Payment received. Receipt RCT-0001.",
      {},
      { timeout: 10_000 },
    ),
  ).toBeInTheDocument();
});

test("prices are typed in naira and saved in kobo", async () => {
  let sent: unknown;
  server.use(
    http.get("*/api/v1/platform/pricing", () =>
      HttpResponse.json({
        version: 1,
        cliff_protection: true,
        price_check: [],
        plans: [
          {
            name: "Basic",
            min_students: 1,
            max_students: 499,
            price_kobo: 100_000,
          },
        ],
      }),
    ),
    http.get("*/api/v1/platform/pricing/versions", () => HttpResponse.json([])),
    http.post("*/api/v1/platform/pricing", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json(
        { version: 2, cliff_protection: true, price_check: [], plans: [] },
        { status: 201 },
      );
    }),
  );
  renderWithClient(<PricingPage />);
  const price = await screen.findByLabelText("Price per student (₦)");
  await userEvent.clear(price);
  await userEvent.type(price, "1200");
  await userEvent.click(
    screen.getByRole("button", { name: "Save as new version" }),
  );
  await waitFor(() =>
    expect(sent).toEqual({
      plans: [
        {
          name: "Basic",
          min_students: 1,
          max_students: 499,
          price_kobo: 120_000,
        },
      ],
    }),
  );
});

test("voiding an invoice needs a reason", async () => {
  let voided: unknown;
  server.use(
    http.get("*/api/v1/platform/billing/schools", () =>
      HttpResponse.json([
        {
          id: "s1",
          name: "Greenfield Model College",
          code: "GMC",
          billing_enabled: true,
          status: "due",
          grace_period_days: 14,
          students: 580,
          current_invoice: INVOICE,
        },
      ]),
    ),
    http.get("*/api/v1/platform/invoices", () => HttpResponse.json([INVOICE])),
    http.post("*/api/v1/platform/invoices/i1/void", async ({ request }) => {
      voided = await request.json();
      return HttpResponse.json({ ...INVOICE, status: "void" });
    }),
  );
  renderWithClient(<PlatformBillingPage />);
  const table = await screen.findByRole("table", { name: "Invoices" });
  await userEvent.click(within(table).getByRole("button", { name: "Void" }));
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Void invoice",
    }),
  );
  expect(voided).toBeUndefined();
  await userEvent.type(
    screen.getByLabelText("Reason (required)"),
    "Billed twice.",
  );
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Void invoice",
    }),
  );
  await waitFor(() => expect(voided).toEqual({ reason: "Billed twice." }));
});
