// Each school's own login page, Find your school and the Login page settings
// (SPEC F02 rules 1, 2, 12 and 14; AC24.4; D-182).
import "@/test/setup";

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import FindSchoolPage from "@/app/login/page";
import SchoolLoginPage from "@/app/login/[schoolCode]/page";
import {
  LoginPageEditor,
  PHOTO_WARNING,
} from "@/components/setup/login-page-editor";
import { renderWithClient } from "@/test/helpers";
import { navigation, router, server } from "@/test/setup";

const GMC = {
  code: "GMC",
  name: "Greenfield Model College",
  colour: "#1f6f43",
  logo_url: null,
  layout: "half",
  picture: "people",
  message: null,
  photo_url: null,
};

function publicSchool(answer: Record<string, unknown> | null) {
  server.use(
    http.get("*/api/v1/auth/schools/:code/public", () =>
      answer
        ? HttpResponse.json(answer)
        : HttpResponse.json({ code: "school_not_found" }, { status: 404 }),
    ),
  );
}

test("a school's page shows its own look and the default message", async () => {
  publicSchool(GMC);
  navigation.params = { schoolCode: "gmc" };
  renderWithClient(<SchoolLoginPage />);
  expect(
    await screen.findByRole("heading", { name: "Welcome back" }),
  ).toBeInTheDocument();
  expect(
    screen.getAllByText("Greenfield Model College").length,
  ).toBeGreaterThan(0);
  expect(
    screen.getByText("Welcome to Greenfield Model College"),
  ).toBeInTheDocument();
  expect(screen.getByText("Powered by SchoolFlow")).toBeInTheDocument();
  expect(
    screen.getByText(/Not Greenfield Model College\?/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("tab", { name: "Staff and parents" }),
  ).toBeInTheDocument();
});

test("the school's own message and the Picture behind layout", async () => {
  publicSchool({
    ...GMC,
    layout: "behind",
    message: "Knowledge, Discipline and Service",
  });
  navigation.params = { schoolCode: "GMC" };
  renderWithClient(<SchoolLoginPage />);
  expect(
    await screen.findByText("Knowledge, Discipline and Service"),
  ).toBeInTheDocument();
});

test("an unknown code is not found", async () => {
  publicSchool(null);
  navigation.params = { schoolCode: "XYZ" };
  renderWithClient(<SchoolLoginPage />);
  expect(
    await screen.findByRole("heading", {
      name: "We couldn't find that school",
    }),
  ).toBeInTheDocument();
  expect(screen.getByText("Check the code and try again.")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Find your school" }),
  ).toHaveAttribute("href", "/login?change=1");
});

test("an old code forwards to the school's current page", async () => {
  publicSchool({ ...GMC, code: "GMCE" });
  navigation.params = { schoolCode: "GMC" };
  renderWithClient(<SchoolLoginPage />);
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith("/login/GMCE"),
  );
});

test("Find your school goes to the school's page by code", async () => {
  renderWithClient(<FindSchoolPage />);
  expect(
    screen.getByRole("heading", { name: "Find your school" }),
  ).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("School code"), "gmc");
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(router.push).toHaveBeenCalledWith("/login/GMC");
  expect(router.replace).not.toHaveBeenCalled();
});

test("a device that remembers its school goes straight there", async () => {
  window.localStorage.setItem("sf:school-code", "GMC");
  navigation.search = new URLSearchParams("next=/school/students");
  renderWithClient(<FindSchoolPage />);
  await waitFor(() =>
    expect(router.replace).toHaveBeenCalledWith(
      "/login/GMC?next=%2Fschool%2Fstudents",
    ),
  );
});

test("Not your school? stays on Find your school", () => {
  window.localStorage.setItem("sf:school-code", "GMC");
  navigation.search = new URLSearchParams("change=1");
  renderWithClient(<FindSchoolPage />);
  expect(router.replace).not.toHaveBeenCalled();
});

test("the Login page settings save the choices and warn before a photo", async () => {
  publicSchool(GMC);
  const saved: unknown[] = [];
  const page = {
    layout: "half" as const,
    picture: "pattern" as const,
    message: null,
    photo_url: null,
    link: "/login/GMC",
  };
  renderWithClient(
    <LoginPageEditor
      page={page}
      code="GMC"
      busy={false}
      onSave={(change) => saved.push(change)}
      upload={{ busy: false, send: () => undefined }}
    />,
  );
  expect(screen.getByText(PHOTO_WARNING)).toBeInTheDocument();
  // "Your own photo" waits for a photo.
  expect(screen.getByRole("radio", { name: "Your own photo" })).toBeDisabled();
  await userEvent.click(screen.getByRole("radio", { name: "Picture behind" }));
  await userEvent.click(screen.getByRole("radio", { name: "People" }));
  await userEvent.type(
    screen.getByLabelText("Login page message"),
    "Knowledge, Discipline and Service",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(saved).toEqual([
    {
      layout: "behind",
      picture: "people",
      message: "Knowledge, Discipline and Service",
    },
  ]);
  expect(screen.getByRole("link", { name: "Open login page" })).toHaveAttribute(
    "href",
    "/login/GMC",
  );
});

test("the super admin's editor has no photo upload", () => {
  renderWithClient(
    <LoginPageEditor
      page={{
        layout: "half",
        picture: "pattern",
        message: null,
        photo_url: null,
        link: "/login/GMC",
      }}
      code="GMC"
      busy={false}
      onSave={() => undefined}
    />,
  );
  expect(screen.queryByText(PHOTO_WARNING)).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Upload a photo" }),
  ).not.toBeInTheDocument();
});
