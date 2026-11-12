import "@/test/setup";

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { expect, test } from "vitest";

import { renderWithClient } from "@/test/helpers";
import { navigation, router, server } from "@/test/setup";

import NewParentPage from "@/app/school/parents/new/page";
import NewStudentPage from "@/app/school/students/new/page";
import StudentsPage from "@/app/school/students/page";
import NewTeacherPage from "@/app/school/teachers/new/page";
import TeacherPage from "@/app/school/teachers/[id]/page";
import { schoolApi } from "@/test/school-fixtures";

test("students can be searched and filtered by class", async () => {
  schoolApi();
  renderWithClient(<StudentsPage />);
  const table = await screen.findByRole("table", { name: "Students" });
  expect(within(table).getByText("Chukwuemeka Obi")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search"), "015");
  expect(within(table).queryByText("Chukwuemeka Obi")).not.toBeInTheDocument();
  expect(within(table).getByText("Musa Ibrahim")).toBeInTheDocument();
  await userEvent.clear(screen.getByLabelText("Search"));
  await userEvent.selectOptions(screen.getByLabelText("Class"), "a1");
  expect(within(table).queryByText("Musa Ibrahim")).not.toBeInTheDocument();
});

test("a new student needs the required fields, then opens their page", async () => {
  schoolApi();
  let sent: unknown;
  server.use(
    http.post("*/api/v1/school/students", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({ ...{ id: "p9" } }, { status: 201 });
    }),
  );
  renderWithClient(<NewStudentPage />);
  await userEvent.click(screen.getByRole("button", { name: "Add student" }));
  expect(screen.getAllByText("This is needed.").length).toBeGreaterThanOrEqual(
    3,
  );
  await userEvent.type(screen.getByLabelText("Surname"), "Yusuf");
  await userEvent.type(screen.getByLabelText("First name"), "Zainab");
  await userEvent.type(
    screen.getByLabelText("Admission number"),
    "GMC/2026/016",
  );
  await userEvent.selectOptions(screen.getByLabelText("Gender"), "female");
  await waitFor(() =>
    expect(screen.getByRole("option", { name: "JSS 1A" })).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Class"), "a1");
  await userEvent.click(screen.getByRole("button", { name: "Add student" }));
  await waitFor(() =>
    expect(router.push).toHaveBeenCalledWith("/school/students/p9"),
  );
  expect(sent).toEqual({
    surname: "Yusuf",
    first_name: "Zainab",
    other_names: null,
    admission_number: "GMC/2026/016",
    gender: "female",
    date_of_birth: null,
    house: null,
    arm_id: "a1",
  });
});

test("a teacher added with a slip sees the temporary password once", async () => {
  schoolApi();
  server.use(
    http.post("*/api/v1/school/staff", () =>
      HttpResponse.json(
        { id: "t9", temporary_password: "apple river cloud lamp" },
        { status: 201 },
      ),
    ),
  );
  renderWithClient(<NewTeacherPage />);
  await userEvent.type(screen.getByLabelText("Full name"), "Grace Etim");
  await userEvent.type(screen.getByLabelText("Username"), "grace.etim");
  await userEvent.click(screen.getByRole("button", { name: "Add teacher" }));
  expect(
    await screen.findByText(
      "This password is shown only once. Print the slip or copy it now.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("apple river cloud lamp")).toBeInTheDocument();
});

test("an activation email needs an email address", async () => {
  schoolApi();
  renderWithClient(<NewTeacherPage />);
  await userEvent.type(screen.getByLabelText("Full name"), "Grace Etim");
  await userEvent.type(screen.getByLabelText("Username"), "grace.etim");
  await userEvent.selectOptions(
    screen.getByLabelText("Login method"),
    "activation",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add teacher" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "An activation email needs an email address.",
  );
});

test("a teacher can be made class teacher teaching all subjects", async () => {
  schoolApi();
  navigation.params = { id: "t1" };
  let sent: unknown;
  server.use(
    http.post("*/api/v1/school/assignments", async ({ request }) => {
      sent = await request.json();
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  renderWithClient(<TeacherPage />);
  await screen.findByText("No assignments yet.");
  await userEvent.selectOptions(screen.getByLabelText("Class"), "a1");
  await userEvent.selectOptions(screen.getByLabelText("Subject"), "__form__");
  await userEvent.click(screen.getByLabelText("Teaches all subjects"));
  await userEvent.click(screen.getByRole("button", { name: "Add assignment" }));
  await waitFor(() =>
    expect(sent).toEqual({
      teacher_id: "t1",
      arm_id: "a1",
      subject_id: null,
      learning_area_id: null,
      is_form_teacher: true,
      teaches_all_subjects: true,
    }),
  );
});

test("a parent with an email gets a link request, and needs a child", async () => {
  schoolApi();
  let sent: { login?: string; username?: string | null } | undefined;
  server.use(
    http.post("*/api/v1/school/guardians", async ({ request }) => {
      sent = (await request.json()) as typeof sent;
      return HttpResponse.json(
        { id: "g1", login_status: "waiting", temporary_password: null },
        { status: 201 },
      );
    }),
  );
  renderWithClient(<NewParentPage />);
  await userEvent.type(screen.getByLabelText("Full name"), "Ikenna Obi");
  await userEvent.type(
    screen.getByLabelText("Email"),
    "ikenna.obi@home.example",
  );
  expect(screen.queryByLabelText("Login method")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add parent" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Add at least one child.",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("option", { name: /Chukwuemeka Obi/ }),
    ).toBeInTheDocument(),
  );
  await userEvent.selectOptions(screen.getByLabelText("Child"), "p1");
  await userEvent.selectOptions(
    screen.getByLabelText("Relationship"),
    "Father",
  );
  await userEvent.click(screen.getByRole("button", { name: "Add child" }));
  await userEvent.click(screen.getByRole("button", { name: "Add parent" }));
  await waitFor(() =>
    expect(router.push).toHaveBeenCalledWith("/school/parents/g1"),
  );
  expect(sent?.login).toBe("link_request");
  expect(sent?.username).toBeNull();
});
