// The results flow: the score grid catches a score above its column before it
// is sent; a change after submission needs a reason; approvals list only what
// waits for the principal; publishing warns that results become final;
// corrections need a message to reject; the attention list is published-only.
import "@/test/setup";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import ApprovalsPage from "@/app/school/approvals/page";
import { waitsForApproval } from "@/components/results/approvals";
import SheetPage from "@/app/teacher/sheets/[sheetId]/page";
import CorrectionPage from "@/app/school/corrections/[id]/page";
import SchoolDashboardPage from "@/app/school/dashboard/page";
import { cellProblem } from "@/components/results/score-grid";
import { renderWithClient } from "@/test/helpers";
import { navigation, server } from "@/test/setup";

const SHEET = {
  id: "sh1",
  class_name: "JSS 1A",
  subject_name: "Mathematics",
  level: "junior_secondary",
  term_id: "t1",
  status: "draft",
  revision: 1,
  status_comment: null,
  can_edit: true,
  columns: [
    { id: "ca1", label: "CA1", name: "Continuous assessment 1", max_score: 20 },
    { id: "ex", label: "Exam", name: "Examination", max_score: 60 },
  ],
  rows: [
    {
      enrolment_id: "e1",
      admission_number: "GMC/2026/014",
      surname: "Obi",
      first_name: "Chukwuemeka",
      scores: { ca1: 16 },
      total: null,
      grade: null,
      missing: ["ex"],
      out_of_range: [],
    },
  ],
  counts: { complete: 0, missing: 1, errors: 0 },
};

test("a cell above its maximum is caught before it is sent", () => {
  expect(cellProblem("61", 60)).toBe("Can't be more than 60.");
  expect(cellProblem("4.5", 60)).toBe("Whole numbers only.");
  expect(cellProblem("", 60)).toBeNull();
  expect(cellProblem("60", 60)).toBeNull();
});

test("a draft saves the typed scores; Submit waits until nothing is missing", async () => {
  navigation.params = { sheetId: "sh1" };
  let sent: unknown;
  server.use(
    http.get("*/api/v1/sheets/sh1", () => HttpResponse.json(SHEET)),
    http.put("*/api/v1/sheets/sh1/scores", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json(SHEET);
    }),
  );
  renderWithClient(<SheetPage />);
  const exam = await screen.findByLabelText("Exam for Chukwuemeka Obi");
  expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  await userEvent.type(exam, "61");
  expect(screen.getByRole("button", { name: "Save draft" })).toBeDisabled();
  await userEvent.clear(exam);
  await userEvent.type(exam, "47");
  await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(sent).toEqual({
      scores: [{ enrolment_id: "e1", component_id: "ex", value: 47 }],
      reason: null,
    }),
  );
});

test("a change to a returned sheet asks for a reason", async () => {
  navigation.params = { sheetId: "sh1" };
  let sent: { reason?: string } | undefined;
  server.use(
    http.get("*/api/v1/sheets/sh1", () =>
      HttpResponse.json({
        ...SHEET,
        status: "returned_for_correction",
        status_comment: "Please check CA1.",
      }),
    ),
    http.put("*/api/v1/sheets/sh1/scores", async ({ request }) => {
      sent = (await request.json()) as typeof sent;
      return HttpResponse.json(SHEET);
    }),
  );
  renderWithClient(<SheetPage />);
  expect(await screen.findByText("Please check CA1.")).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("CA1 for Chukwuemeka Obi"));
  await userEvent.type(screen.getByLabelText("CA1 for Chukwuemeka Obi"), "14");
  await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect(sent).toBeUndefined();
  await userEvent.type(
    await screen.findByLabelText("Reason (required)"),
    "Paper shows 14.",
  );
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Save draft",
    }),
  );
  await waitFor(() => expect(sent?.reason).toBe("Paper shows 14."));
});

test("approvals list only sheets waiting for the principal", async () => {
  const s = (id: string, status: string, needs_review: boolean) => ({
    id,
    status,
    needs_review,
    class_name: "JSS 1A",
    name: id,
    kind: "scores" as const,
    revision: 1,
  });
  expect(waitsForApproval(s("a", "submitted", true))).toBe(false);
  expect(waitsForApproval(s("b", "submitted", false))).toBe(true);
  expect(waitsForApproval(s("c", "reviewed", true))).toBe(true);
  server.use(
    http.get("*/api/v1/school/sheets", () =>
      HttpResponse.json([
        s("Mathematics", "submitted", true),
        s("English Language", "reviewed", true),
      ]),
    ),
  );
  renderWithClient(<ApprovalsPage />);
  const waiting = await screen.findByRole("table", {
    name: "Waiting for approval",
  });
  expect(within(waiting).getByText("English Language")).toBeInTheDocument();
  expect(within(waiting).queryByText("Mathematics")).not.toBeInTheDocument();
});

test("rejecting a correction needs a message", async () => {
  navigation.params = { id: "cr1" };
  let sent: unknown;
  server.use(
    http.get("*/api/v1/corrections/cr1", () =>
      HttpResponse.json({
        id: "cr1",
        number: "CR-0001",
        student_name: "Chukwuemeka Obi",
        class_name: "JSS 1A",
        term: "First Term 2026/2027",
        subject: "Mathematics",
        learning_area: null,
        issue_type: "score",
        explanation: "My CA2 looks wrong.",
        status: "investigating",
        status_message: null,
        report_code: "GMC-2627-T1-JSS1A-014",
        revision: 1,
        requested_by: "Ikenna Obi",
        created_at: "2026-12-12T10:00:00Z",
        events: [],
        attachment: null,
        change: null,
        corrected_report: null,
      }),
    ),
    http.post("*/api/v1/corrections/cr1/move", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({});
    }),
  );
  renderWithClient(<CorrectionPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Reject" }));
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Send" }),
  );
  expect(sent).toBeUndefined();
  await userEvent.type(
    screen.getByLabelText("Message (required)"),
    "The mark is correct.",
  );
  await userEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Send" }),
  );
  await waitFor(() =>
    expect(sent).toEqual({
      status: "rejected",
      message: "The mark is correct.",
    }),
  );
});

test("the dashboard shows what is blocking release", async () => {
  server.use(
    http.get("*/api/v1/dashboard/school", () =>
      HttpResponse.json({
        term: "First Term 2026/2027",
        corrections_open: 1,
        billing: { billing_enabled: false, status: "free_pilot" },
        results: {
          nothing_started: false,
          sheets: {
            awaiting_submission: 6,
            awaiting_review: 5,
            awaiting_approval: 4,
            approved: 11,
            published: 0,
            total: 26,
          },
          classes: [],
          missing_scores: { count: 14, sheets: [] },
          missing_ratings: { count: 0, sheets: [] },
          invalid_scores: { count: 0, sheets: [] },
          open_sections: ["JSS 1A", "JSS 1B"],
          unusual_changes: [],
          stats: {
            sheets_counted: 11,
            average: "64.2",
            pass_rate: "86",
            by_subject: [],
            by_class: [],
            trend: [],
          },
          attention: null,
        },
      }),
    ),
  );
  renderWithClient(<SchoolDashboardPage />);
  expect(
    await screen.findByRole("heading", { name: "What is blocking release?" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Review 4 approvals" }),
  ).toHaveAttribute("href", "/school/approvals");
  expect(
    screen.getByText("2 form teacher sections still open"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Remind form teachers" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Billing")).not.toBeInTheDocument();
});
