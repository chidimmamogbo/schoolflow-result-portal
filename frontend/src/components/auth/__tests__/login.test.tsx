// Login on a school's own page and on the platform page (SPEC F02 rules 1 and
// 11, D-182): one message for every failure (never which detail was wrong, nor
// that the account belongs elsewhere), the school code comes from the page,
// the device remembers the school and the tab, and only a path on this site
// is a "next".
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { beforeEach, expect, test } from "vitest";

import {
  LOGIN_FAILED,
  LoginForm,
  PlatformLoginForm,
  safeNext,
} from "@/components/auth/login-form";
import { chosenSchoolId, loginPage, rememberedCode } from "@/lib/school-memory";
import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { navigation, router, server } from "@/test/setup";

beforeEach(() => window.sessionStorage.clear());

async function fillIn(idLabel: string, identifier: string, password: string) {
  await userEvent.type(screen.getByLabelText(idLabel), identifier);
  await userEvent.type(screen.getByLabelText("Password"), password);
  await userEvent.click(screen.getByRole("button", { name: "Log in" }));
}

test("staff log in on their school's page and land on their home page", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/login", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({
        must_change_password: false,
        school_id: "s-gmc",
      });
    }),
  );
  signedIn(makeMe());
  window.localStorage.setItem("sf:login-tab", "staff");
  renderWithClient(<LoginForm schoolCode="GMC" />);
  await fillIn(
    "Email or username",
    " ngozi.okeke ",
    "fictional-blue-mango-river",
  );
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/school/dashboard"),
  );
  expect(sent).toEqual({
    identifier: "ngozi.okeke",
    password: "fictional-blue-mango-river",
    school_code: "GMC",
    tab: "staff",
  });
  // The device remembers the school (only its code) and the tab; this browser
  // tab starts in the school whose page was used.
  expect(rememberedCode()).toBe("GMC");
  expect(window.localStorage.getItem("sf:login-tab")).toBe("staff");
  expect(chosenSchoolId()).toBe("s-gmc");
  expect(loginPage()).toBe("/login/GMC");
});

test("a student logs in on the Student tab, which opens first on a new device", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/login", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({
        must_change_password: false,
        school_id: "s-gmc",
      });
    }),
  );
  signedIn(makeMe({ role: "student", is_primary: false }));
  renderWithClient(<LoginForm schoolCode="GMC" />);
  expect(screen.getByRole("tab", { name: "Student" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // The school code comes from the page's link: there is no box for it.
  expect(screen.queryByLabelText("School code")).not.toBeInTheDocument();
  expect(
    screen.getByText(
      "Forgot your password? Ask your school admin for a new one.",
    ),
  ).toBeInTheDocument();
  await fillIn(
    "Username or admission number",
    "GMC/2026/014",
    "fictional-pupil-words",
  );
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/student"));
  expect(sent).toEqual({
    identifier: "GMC/2026/014",
    password: "fictional-pupil-words",
    school_code: "GMC",
    tab: "student",
  });
});

test("any failure, including the wrong school's page, shows the same message", async () => {
  for (const status of [401, 403, 429, 500]) {
    server.use(
      http.post("*/api/v1/auth/login", () =>
        HttpResponse.json({ code: "x" }, { status }),
      ),
    );
    window.localStorage.setItem("sf:login-tab", "staff");
    const { unmount } = renderWithClient(<LoginForm schoolCode="BSA" />);
    await fillIn("Email or username", "someone", "wrong");
    expect(await screen.findByRole("alert")).toHaveTextContent(LOGIN_FAILED);
    unmount();
  }
  expect(router.replace).not.toHaveBeenCalled();
  expect(rememberedCode()).toBeNull();
});

test("a temporary password goes straight to change password", async () => {
  server.use(
    http.post("*/api/v1/auth/login", () =>
      HttpResponse.json({ must_change_password: true, school_id: "s-gmc" }),
    ),
  );
  signedIn(makeMe({ must_change_password: true }));
  navigation.search = new URLSearchParams("next=/school/students");
  window.localStorage.setItem("sf:login-tab", "staff");
  renderWithClient(<LoginForm schoolCode="GMC" />);
  await fillIn("Email or username", "ngozi.okeke", "temp words here now");
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/change-password"),
  );
});

test("the super admin logs in on the platform page", async () => {
  let sent: unknown;
  server.use(
    http.post("*/api/v1/auth/platform/login", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({
        must_change_password: false,
        school_id: null,
      });
    }),
  );
  signedIn(makeMe({ is_super_admin: true, role: "super_admin", school: null }));
  renderWithClient(<PlatformLoginForm />);
  expect(
    screen.getByRole("link", { name: "Find your school" }),
  ).toHaveAttribute("href", "/login?change=1");
  await fillIn(
    "Email or username",
    "platform.admin",
    "fictional-blue-mango-river",
  );
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/platform"));
  expect(sent).toEqual({
    identifier: "platform.admin",
    password: "fictional-blue-mango-river",
  });
  expect(loginPage()).toBe("/platform/login");
});

test("only a path on this site is followed after login", () => {
  expect(safeNext("/school/students")).toBe("/school/students");
  expect(safeNext("//evil.example/x")).toBeNull();
  expect(safeNext("https://evil.example")).toBeNull();
  expect(safeNext(null)).toBeNull();
});
