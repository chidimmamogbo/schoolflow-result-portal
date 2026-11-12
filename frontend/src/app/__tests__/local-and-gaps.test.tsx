// CHANGE 2026-11-12: /api reaches the local backend only in development; the
// Emails page lists real statuses; a student with a login gets login support;
// the class page starts from each arm's current subjects.
import "@/test/setup";

import { screen, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import EmailsPage from "@/app/school/emails/page";
import StudentPage from "@/app/school/students/[id]/page";
import ClassPage from "@/app/school/setup/classes/[id]/page";
import { renderWithClient } from "@/test/helpers";
import { navigation, server } from "@/test/setup";
import { CLASSES, PUPILS, schoolApi } from "@/test/school-fixtures";
import { devRewrites } from "../../../next.config";

test("only development sends /api to the local backend", async () => {
  expect(await devRewrites("development")).toEqual([
    { source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" },
  ]);
  expect(await devRewrites("production")).toEqual([]);
  expect(await devRewrites(undefined)).toEqual([]);
});

test("the Emails page lists statuses without content", async () => {
  server.use(
    http.get("*/api/v1/school/emails", () =>
      HttpResponse.json([
        {
          id: "e1",
          type: "results_published",
          to_address: "ikenna.obi@home.example",
          status: "sent",
          attempts: 1,
          created_at: "2026-12-12T10:00:00Z",
          sent_at: "2026-12-12T10:01:00Z",
        },
      ]),
    ),
  );
  renderWithClient(<EmailsPage />);
  const table = await screen.findByRole("table", { name: "Emails" });
  expect(
    within(table).getByText("ikenna.obi@home.example"),
  ).toBeInTheDocument();
  expect(within(table).getByText("results published")).toBeInTheDocument();
});

test("a student with a login gets login support", async () => {
  schoolApi();
  server.use(
    http.get("*/api/v1/school/students", () =>
      HttpResponse.json([{ ...PUPILS[0], user_id: "u-chuk" }]),
    ),
    http.get("*/api/v1/school", () => HttpResponse.json({ code: "GMC" })),
  );
  navigation.params = { id: "p1" };
  renderWithClient(<StudentPage />);
  await screen.findByRole("heading", { name: "Chukwuemeka Obi" });
  screen.getByRole("tab", { name: "Login" }).focus();
  await (
    await import("@testing-library/user-event")
  ).default.click(screen.getByRole("tab", { name: "Login" }));
  expect(
    await screen.findByRole("button", { name: "Issue temporary password" }),
  ).toBeInTheDocument();
});

test("the class page starts from each arm's current subjects", async () => {
  schoolApi();
  server.use(
    http.get("*/api/v1/school/arms/:arm/subjects", () =>
      HttpResponse.json([
        { id: "m", name: "Mathematics", department_id: "d1", category: null },
      ]),
    ),
  );
  navigation.params = { id: CLASSES[0]!.id };
  renderWithClient(<ClassPage />);
  const userEvent = (await import("@testing-library/user-event")).default;
  await userEvent.click(await screen.findByRole("tab", { name: "Subjects" }));
  const boxes = await screen.findAllByRole("checkbox", { name: "Mathematics" });
  expect(boxes.every((b) => (b as HTMLInputElement).checked)).toBe(true);
});
