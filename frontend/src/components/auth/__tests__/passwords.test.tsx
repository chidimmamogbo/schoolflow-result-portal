// Setting a password from a link, forgot password and change password.
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import { LINK_INVALID } from "@/components/auth/password-rules";
import { SetPassword, tokenFromHash } from "@/components/auth/set-password";
import ChangePasswordPage from "@/app/change-password/page";
import ForgotPasswordPage from "@/app/forgot-password/page";
import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { navigation, router, server } from "@/test/setup";

const GOOD = "fictional-blue-mango-river";

test("the token is read from after #token= only", () => {
  expect(tokenFromHash("#token=abc_DEF-123")).toBe("abc_DEF-123");
  expect(tokenFromHash("")).toBeNull();
  expect(tokenFromHash("#other=1")).toBeNull();
});

function activate() {
  window.history.replaceState(null, "", "/activate#token=tok123");
  return renderWithClient(
    <SetPassword
      endpoint="/api/v1/auth/activate"
      title="Activate your account"
      intro="Welcome."
    />,
  );
}

test("activation sets the password and goes home", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/activate", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ must_change_password: false });
    }),
  );
  signedIn(makeMe({ role: "teacher", is_primary: false }));
  activate();
  await userEvent.type(screen.getByLabelText("New password"), GOOD);
  await userEvent.type(screen.getByLabelText("Confirm new password"), GOOD);
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/teacher"));
  expect(sent).toEqual({ token: "tok123", password: GOOD });
  expect(window.location.hash).toBe("");
});

test("a short or mismatched password is stopped before it is sent", async () => {
  activate();
  await userEvent.type(screen.getByLabelText("New password"), "too-short");
  await userEvent.type(
    screen.getByLabelText("Confirm new password"),
    "too-short",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Use at least 15 characters.",
  );
  await userEvent.clear(screen.getByLabelText("New password"));
  await userEvent.type(screen.getByLabelText("New password"), GOOD);
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The passwords don't match.",
  );
});

test("a used or expired link says so", async () => {
  server.use(
    http.post("*/api/v1/auth/activate", () =>
      HttpResponse.json({ code: "link_invalid" }, { status: 400 }),
    ),
  );
  activate();
  await userEvent.type(screen.getByLabelText("New password"), GOOD);
  await userEvent.type(screen.getByLabelText("Confirm new password"), GOOD);
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(LINK_INVALID);
  expect(router.replace).not.toHaveBeenCalled();
});

test("a page opened without a token says the link is no good", async () => {
  window.history.replaceState(null, "", "/activate");
  renderWithClient(
    <SetPassword
      endpoint="/api/v1/auth/activate"
      title="Activate your account"
      intro="Welcome."
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(LINK_INVALID);
});

test("forgot password answers the same whatever happens", async () => {
  for (const status of [202, 404, 500]) {
    server.use(
      http.post(
        "*/api/v1/auth/password/forgot",
        () => new HttpResponse(null, { status }),
      ),
    );
    const { unmount } = renderWithClient(<ForgotPasswordPage />);
    await userEvent.type(
      screen.getByLabelText("Email"),
      "someone@home.example",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Send reset link" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "If that email has an account",
    );
    unmount();
  }
});

test("a forced change explains why and then continues home", async () => {
  server.use(
    http.post(
      "*/api/v1/auth/change-password",
      () => new HttpResponse(null, { status: 204 }),
    ),
  );
  signedIn(makeMe({ must_change_password: true }));
  navigation.pathname = "/change-password";
  renderWithClient(<ChangePasswordPage />);
  expect(
    await screen.findByText(
      "You logged in with a temporary password. Choose a new one to continue.",
    ),
  ).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("Temporary password"),
    "four temp words here",
  );
  await userEvent.type(screen.getByLabelText("New password"), GOOD);
  await userEvent.type(screen.getByLabelText("Confirm new password"), GOOD);
  signedIn(makeMe());
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(
    await screen.findByText("Your password is changed."),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(router.replace).toHaveBeenCalledWith("/school/dashboard");
});

test("a wrong current password is reported", async () => {
  server.use(
    http.post("*/api/v1/auth/change-password", () =>
      HttpResponse.json({ code: "current_password_wrong" }, { status: 400 }),
    ),
  );
  signedIn(makeMe());
  navigation.pathname = "/change-password";
  renderWithClient(<ChangePasswordPage />);
  await userEvent.type(
    await screen.findByLabelText("Current password"),
    "not-it",
  );
  await userEvent.type(screen.getByLabelText("New password"), GOOD);
  await userEvent.type(screen.getByLabelText("Confirm new password"), GOOD);
  await userEvent.click(screen.getByRole("button", { name: "Save password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Your current password is not right.",
  );
});
