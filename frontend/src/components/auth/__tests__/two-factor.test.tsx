// The super admin's code step after the password (SPEC F02 rule 11, D-043):
// first-time set-up with a QR code and recovery codes, later a code from the
// app or one recovery code, the same message for every wrong code, and new
// recovery codes on the profile page.
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import ProfilePage from "@/app/profile/page";
import { PlatformLoginForm } from "@/components/auth/login-form";
import { CODE_FAILED } from "@/components/auth/two-factor";
import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { router, server } from "@/test/setup";

const CODES = Array.from({ length: 10 }, (_, i) => `ABCDE-${10000 + i}`);

function passwordStep(next: "setup" | "code") {
  server.use(
    http.post("*/api/v1/auth/platform/login", () =>
      HttpResponse.json({
        must_change_password: false,
        school_id: null,
        two_factor: next,
      }),
    ),
  );
}

async function typePassword() {
  await userEvent.type(
    screen.getByLabelText("Email or username"),
    "platform.admin",
  );
  await userEvent.type(
    screen.getByLabelText("Password"),
    "fictional-blue-mango-river",
  );
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
}

const owner = () =>
  makeMe({ is_super_admin: true, role: "super_admin", school: null });

test("the first login sets up the app and shows the recovery codes once", async () => {
  passwordStep("setup");
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/two-factor/setup", () =>
      HttpResponse.json({
        secret: "JBSWY3DPEHPK3PXP",
        qr_svg: "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
      }),
    ),
    http.post("*/api/v1/auth/two-factor/setup/confirm", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({
        recovery_codes: CODES,
        must_change_password: false,
      });
    }),
  );
  signedIn(owner());
  renderWithClient(<PlatformLoginForm />);
  await typePassword();
  expect(
    await screen.findByRole("heading", { name: "Set up two-factor login" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("img", {
      name: "QR code for your authenticator app",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("JBSWY3DPEHPK3PXP")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("6-digit code"), "123456");
  await userEvent.click(
    screen.getByRole("button", { name: "Turn on two-factor login" }),
  );
  expect(sent).toEqual({ code: "123456" });
  expect(
    await screen.findByRole("heading", { name: "Save your recovery codes" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("list", { name: "Recovery codes" }),
  ).toHaveTextContent("ABCDE-10009");
  // Nothing moves on until the codes are saved.
  expect(router.replace).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "I've saved them" }),
  );
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/platform"));
});

test("later logins take a code, with one message for every wrong code", async () => {
  passwordStep("code");
  let good = false;
  server.use(
    http.post("*/api/v1/auth/two-factor/verify", () =>
      good
        ? HttpResponse.json({ must_change_password: false })
        : HttpResponse.json({ code: "code_failed" }, { status: 401 }),
    ),
  );
  signedIn(owner());
  renderWithClient(<PlatformLoginForm />);
  await typePassword();
  expect(
    await screen.findByRole("heading", { name: "Enter your code" }),
  ).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("6-digit code"), "000000");
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(CODE_FAILED);
  expect(router.replace).not.toHaveBeenCalled();
  good = true;
  await userEvent.clear(screen.getByLabelText("6-digit code"));
  await userEvent.type(screen.getByLabelText("6-digit code"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/platform"));
});

test("a recovery code instead, then how many are left", async () => {
  passwordStep("code");
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/two-factor/recovery", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ codes_left: 9, must_change_password: false });
    }),
  );
  signedIn(owner());
  renderWithClient(<PlatformLoginForm />);
  await typePassword();
  await userEvent.click(
    await screen.findByRole("button", { name: "Use a recovery code instead" }),
  );
  expect(
    screen.getByRole("heading", { name: "Use a recovery code" }),
  ).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Recovery code"), "ABCDE-10000");
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(sent).toEqual({ code: "ABCDE-10000" });
  expect(
    await screen.findByText("You have 9 recovery codes left."),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/platform"));
  expect(
    screen.queryByRole("button", {
      name: "Use your authenticator app instead",
    }),
  ).not.toBeInTheDocument();
});

test("a server without the key says so", async () => {
  passwordStep("setup");
  server.use(
    http.post("*/api/v1/auth/two-factor/setup", () =>
      HttpResponse.json({ code: "two_factor_unavailable" }, { status: 503 }),
    ),
  );
  renderWithClient(<PlatformLoginForm />);
  await typePassword();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Two-factor login is not set up on this server.",
  );
});

test("the super admin makes new recovery codes on the profile page", async () => {
  let sent: unknown;
  server.use(
    http.get("*/api/v1/auth/two-factor/recovery-codes", () =>
      HttpResponse.json({ codes_left: 7, must_change_password: false }),
    ),
    http.post(
      "*/api/v1/auth/two-factor/recovery-codes",
      async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({
          recovery_codes: CODES,
          must_change_password: false,
        });
      },
    ),
  );
  signedIn(owner());
  renderWithClient(<ProfilePage />);
  expect(
    await screen.findByText("On. 7 recovery codes left."),
  ).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("6-digit code"), "654321");
  await userEvent.click(
    screen.getByRole("button", { name: "Make new recovery codes" }),
  );
  expect(sent).toEqual({ code: "654321" });
  expect(
    await screen.findByRole("list", { name: "Recovery codes" }),
  ).toHaveTextContent("ABCDE-10000");
});

test("other people's profile pages have no two-factor section", async () => {
  signedIn(makeMe());
  renderWithClient(<ProfilePage />);
  expect(await screen.findByText("Username")).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Two-factor login" }),
  ).not.toBeInTheDocument();
});
