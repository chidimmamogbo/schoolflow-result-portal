// The public verification result: the status word in capitals, the masked
// name, a note when a newer version exists, and a plain message when not found.
import "@/test/setup";

import { screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import SchoolLoginPage from "@/app/login/[schoolCode]/page";
import VerifyResultPage from "@/app/verify/[code]/page";
import { renderWithClient } from "@/test/helpers";
import { navigation, server } from "@/test/setup";

const RESULT = {
  status: "valid",
  school: "Greenfield Model College",
  student: "Chuk*** O.",
  session: "2026/2027",
  term: "First Term",
  report_id: "GMC-2627-T1-JSS1A-014",
  revision: 1,
  published_at: "2026-12-12T10:00:00Z",
  has_newer_revision: false,
  newer_revision: null,
  newer_published_at: null,
};

function check(answer: object, status = 200) {
  navigation.params = { code: "7KQ4-M2XD-P9QA" };
  server.use(
    http.get("*/api/v1/verify/:code", () =>
      HttpResponse.json(answer, { status }),
    ),
  );
  renderWithClient(<VerifyResultPage />);
}

test("a valid report shows VALID and the masked name", async () => {
  check(RESULT);
  expect(await screen.findByText("VALID")).toBeInTheDocument();
  expect(screen.getByText("Chuk*** O.")).toBeInTheDocument();
  expect(screen.getByText("12 Dec 2026")).toBeInTheDocument();
});

test("a superseded report points to the newer version", async () => {
  check({
    ...RESULT,
    status: "superseded",
    has_newer_revision: true,
    newer_revision: 2,
    newer_published_at: "2027-01-08T09:00:00Z",
  });
  expect(await screen.findByText("SUPERSEDED")).toBeInTheDocument();
  expect(
    screen.getByText(
      /A newer version exists \(revision 2, published 8 Jan 2027\)/,
    ),
  ).toBeInTheDocument();
});

test("a revoked report says so", async () => {
  check({ ...RESULT, status: "revoked" });
  expect(await screen.findByText("REVOKED")).toBeInTheDocument();
});

test("an unknown code gets a plain message", async () => {
  check({ code: "not_found" }, 404);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "We couldn't find a report card with that code.",
  );
});

test("a school login link shows the school and fills the code", async () => {
  navigation.params = { schoolCode: "gmc" };
  server.use(
    http.get("*/api/v1/auth/schools/:code/public", () =>
      HttpResponse.json({
        code: "GMC",
        name: "Greenfield Model College",
        colour: "#1E6B45",
        logo_url: null,
      }),
    ),
  );
  renderWithClient(<SchoolLoginPage />);
  expect(
    await screen.findByText("Greenfield Model College"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("School code")).toHaveValue("GMC");
});
