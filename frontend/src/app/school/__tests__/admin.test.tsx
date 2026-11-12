import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { server } from "@/test/setup";

import SchoolAdminsPage from "@/app/school/admins/page";
import SchoolSettingsPage from "@/app/school/settings/page";
import { LoginSupport } from "@/components/people/login-support";
import { bandProblem } from "@/components/setup/grading";
import { totalMessage } from "@/components/setup/assessment";

test("only the principal manages school admins", async () => {
  signedIn(makeMe({ is_primary: false }));
  renderWithClient(<SchoolAdminsPage />);
  expect(
    await screen.findByText("Only the principal can manage school admins."),
  ).toBeInTheDocument();
});

test("the principal sees the places left and the list", async () => {
  signedIn(makeMe());
  server.use(
    http.get("*/api/v1/school/admins", () =>
      HttpResponse.json({
        places_left: 1,
        admins: [
          {
            id: "u1",
            full_name: "Ngozi Okeke",
            username: "ngozi.okeke",
            email: null,
            is_primary: true,
            is_active: true,
            activated: true,
          },
          {
            id: "u2",
            full_name: "Chukwudi Eze",
            username: "chukwudi.eze",
            email: null,
            is_primary: false,
            is_active: true,
            activated: true,
          },
        ],
      }),
    ),
  );
  renderWithClient(<SchoolAdminsPage />);
  expect(
    await screen.findByText("1 of 2 school admin places left."),
  ).toBeInTheDocument();
  expect(screen.getAllByText("Ngozi Okeke (You)").length).toBeGreaterThan(0);
});

test("settings send only what changed", async () => {
  let sent: unknown;
  server.use(
    http.get("*/api/v1/school", () =>
      HttpResponse.json({
        id: "s1",
        code: "GMC",
        name: "Greenfield Model College",
        email: "office@gmc.example",
        phone: "08030001122",
        address: "14 Chime Avenue",
        city: "Enugu",
        state: "Enugu",
        country: "Nigeria",
        colour: "#1E6B45",
        features: {},
        levels: [],
      }),
    ),
    http.patch("*/api/v1/school", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({});
    }),
  );
  signedIn(makeMe());
  renderWithClient(<SchoolSettingsPage />);
  const phone = await screen.findByLabelText("Phone");
  await userEvent.clear(phone);
  await userEvent.type(phone, "08030009999");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(sent).toEqual({ phone: "08030009999" }));
});

test("issuing a temporary password shows the slip; deactivating asks first", async () => {
  server.use(
    http.post("*/api/v1/school/people/:id/temporary-password", () =>
      HttpResponse.json(
        { temporary_password: "river lamp stone cloud" },
        { status: 201 },
      ),
    ),
  );
  renderWithClient(
    <LoginSupport
      person={{
        id: "t1",
        full_name: "Tunde Adebayo",
        username: "tunde.adebayo",
        email: null,
        is_active: true,
        activated: true,
      }}
      invalidate={[["school", "staff"]]}
    />,
  );
  expect(
    screen.queryByRole("button", { name: "Send reset link" }),
  ).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Issue temporary password" }),
  );
  expect(await screen.findByText("river lamp stone cloud")).toBeInTheDocument();
  await userEvent.keyboard("{Escape}");
  await userEvent.click(
    screen.getByRole("button", { name: "Deactivate account" }),
  );
  expect(
    await screen.findByText("Deactivate Tunde Adebayo?"),
  ).toBeInTheDocument();
});

test("grade bands must cover 0 to 100 once each", () => {
  const ok = [
    { grade: "F", min_score: 0, max_score: 39, remark: "Fail" },
    { grade: "A", min_score: 40, max_score: 100, remark: "Pass" },
  ];
  expect(bandProblem(ok)).toBeNull();
  expect(bandProblem([ok[1]!])).toBe("No grade covers 0 to 39.");
  expect(bandProblem([ok[0]!, { ...ok[1]!, min_score: 35 }])).toBe(
    "A overlaps the band below it.",
  );
  expect(bandProblem([ok[0]!, { ...ok[1]!, grade: "F" }])).toBe(
    "Grade F is used twice.",
  );
});

test("the assessment total says what is missing or extra", () => {
  const c = (n: number) => ({ name: "x", label: `L${n}`, max_score: n });
  expect(totalMessage([c(20), c(20), c(60)])).toBe("Total 100");
  expect(totalMessage([c(20), c(60)])).toBe(
    "Total 80. Add 20 more to reach 100.",
  );
  expect(totalMessage([c(50), c(60)])).toBe(
    "Total 110. Remove 10 to get back to 100.",
  );
});
