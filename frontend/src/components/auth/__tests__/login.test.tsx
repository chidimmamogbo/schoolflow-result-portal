// Login: one message for every failure (never which detail was wrong), the
// Student tab sends the school code, and only a path on this site is a "next".
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import {
  LOGIN_FAILED,
  LoginForm,
  safeNext,
} from "@/components/auth/login-form";
import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { navigation, router, server } from "@/test/setup";

test("staff log in and land on their home page", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/login", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ must_change_password: false });
    }),
  );
  signedIn(makeMe());
  renderWithClient(<LoginForm />);
  await userEvent.type(
    screen.getByLabelText("Email or username"),
    " ngozi.okeke ",
  );
  await userEvent.type(
    screen.getByLabelText("Password"),
    "fictional-blue-mango-river",
  );
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/school/dashboard"),
  );
  expect(sent).toEqual({
    identifier: "ngozi.okeke",
    password: "fictional-blue-mango-river",
  });
});

test("any failure shows the same message", async () => {
  for (const status of [401, 403, 429, 500]) {
    server.use(
      http.post("*/api/v1/auth/login", () =>
        HttpResponse.json({ code: "x" }, { status }),
      ),
    );
    const { unmount } = renderWithClient(<LoginForm />);
    await userEvent.type(screen.getByLabelText("Email or username"), "someone");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(LOGIN_FAILED);
    unmount();
  }
  expect(router.replace).not.toHaveBeenCalled();
});

test("a temporary password goes straight to change password", async () => {
  server.use(
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json({ must_change_password: true }),
    ),
  );
  signedIn(makeMe({ must_change_password: true }));
  navigation.search = new URLSearchParams("next=/school/students");
  renderWithClient(<LoginForm />);
  await userEvent.type(
    screen.getByLabelText("Email or username"),
    "ngozi.okeke",
  );
  await userEvent.type(
    screen.getByLabelText("Password"),
    "temp words here now",
  );
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/change-password"),
  );
});

test("a student logs in with the school code filled in", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/login", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ must_change_password: false });
    }),
  );
  signedIn(makeMe({ role: "student", is_primary: false }));
  renderWithClient(<LoginForm studentFirst schoolCode="GMC" />);
  expect(screen.getByLabelText("School code")).toHaveValue("GMC");
  expect(
    screen.getByText(
      "Forgot your password? Ask your school admin for a new one.",
    ),
  ).toBeInTheDocument();
  await userEvent.type(
    screen.getByLabelText("Username or admission number"),
    "GMC/2026/014",
  );
  await userEvent.type(screen.getByLabelText("Password"), "fictional-pupil-words");
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/student"));
  expect(sent).toEqual({
    identifier: "GMC/2026/014",
    password: "fictional-pupil-words",
    school_code: "GMC",
  });
});

test("only a path on this site is followed after login", () => {
  expect(safeNext("/school/students")).toBe("/school/students");
  expect(safeNext("//evil.example/x")).toBeNull();
  expect(safeNext("https://evil.example")).toBeNull();
  expect(safeNext(null)).toBeNull();
});
