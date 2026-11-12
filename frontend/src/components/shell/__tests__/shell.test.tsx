// The guard steers people to the right page; the shell remembers the
// collapsed sidebar and shows the unread count in words.
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { AppShell } from "@/components/shell/app-shell";
import { Protected } from "@/components/shell/protected";
import { makeMe, renderWithClient, signedIn } from "@/test/helpers";
import { navigation, router } from "@/test/setup";

test("someone not signed in is sent to log in, then back", async () => {
  signedIn(null);
  navigation.pathname = "/school/students";
  renderWithClient(<Protected>{() => <p>secret</p>}</Protected>);
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith(
      "/login?next=%2Fschool%2Fstudents",
    ),
  );
  expect(screen.queryByText("secret")).not.toBeInTheDocument();
});

test("a temporary password goes to change password first", async () => {
  signedIn(makeMe({ must_change_password: true }));
  navigation.pathname = "/school/dashboard";
  renderWithClient(
    <Protected roles={["school_admin"]}>{() => <p>secret</p>}</Protected>,
  );
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/change-password"),
  );
  expect(screen.queryByText("secret")).not.toBeInTheDocument();
});

test("the wrong role is sent to its own home", async () => {
  signedIn(makeMe({ role: "parent", is_primary: false }));
  navigation.pathname = "/school/dashboard";
  renderWithClient(
    <Protected roles={["school_admin"]}>{() => <p>secret</p>}</Protected>,
  );
  await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/parent"));
  expect(screen.queryByText("secret")).not.toBeInTheDocument();
});

test("the right role sees the page", async () => {
  signedIn(makeMe());
  renderWithClient(
    <Protected roles={["school_admin"]}>
      {(me) => <p>Hello {me.user.full_name}</p>}
    </Protected>,
  );
  expect(await screen.findByText("Hello Ngozi Okeke")).toBeInTheDocument();
  expect(router.replace).not.toHaveBeenCalled();
});

test("the sidebar collapse is remembered and the bell says how many are unread", async () => {
  const me = makeMe();
  signedIn(me);
  renderWithClient(<AppShell me={me}>page</AppShell>);
  expect(
    screen.getByRole("link", { name: "Notices, 3 unread" }),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Collapse sidebar" }),
  );
  expect(window.localStorage.getItem("sf-sidebar-collapsed")).toBe("1");
  expect(
    screen.getByRole("button", { name: "Expand sidebar" }),
  ).toBeInTheDocument();
});

test("the active page is marked in the menu", () => {
  const me = makeMe();
  signedIn(me);
  navigation.pathname = "/school/students/abc";
  renderWithClient(<AppShell me={me}>page</AppShell>);
  expect(screen.getByRole("link", { name: "Students" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
