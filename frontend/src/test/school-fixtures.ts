// Fictional GMC data for school admin page tests.
import { HttpResponse, http } from "msw";

import { server } from "@/test/setup";

export const CLASSES = [
  {
    id: "c1",
    level: "junior_secondary",
    name: "JSS 1",
    arms: [
      { id: "a1", name: "A" },
      { id: "a2", name: "B" },
    ],
  },
];
export const PUPILS = [
  {
    id: "p1",
    surname: "Obi",
    first_name: "Chukwuemeka",
    other_names: null,
    admission_number: "GMC/2026/014",
    gender: "male",
    date_of_birth: null,
    house: null,
    department_id: null,
    status: "active",
    arm_id: "a1",
    has_login: true,
  },
  {
    id: "p2",
    surname: "Ibrahim",
    first_name: "Musa",
    other_names: null,
    admission_number: "GMC/2026/015",
    gender: "male",
    date_of_birth: null,
    house: null,
    department_id: null,
    status: "active",
    arm_id: "a2",
    has_login: false,
  },
];
export const STAFF = [
  {
    id: "t1",
    full_name: "Tunde Adebayo",
    username: "tunde.adebayo",
    email: null,
    role: "teacher",
    is_active: true,
    activated: true,
  },
  {
    id: "r1",
    full_name: "Emeka Nwosu",
    username: "emeka.nwosu",
    email: "emeka@gmc.example",
    role: "reviewer",
    is_active: true,
    activated: false,
  },
];
export const SUBJECTS = [
  { id: "m", name: "Mathematics", department_id: "d1", category: null },
];

export function schoolApi() {
  server.use(
    http.get("*/api/v1/school/classes", () => HttpResponse.json(CLASSES)),
    http.get("*/api/v1/school/students", () => HttpResponse.json(PUPILS)),
    http.get("*/api/v1/school/staff", () => HttpResponse.json(STAFF)),
    http.get("*/api/v1/school/subjects", () => HttpResponse.json(SUBJECTS)),
    http.get("*/api/v1/school/departments", () =>
      HttpResponse.json([{ id: "d1", name: "Sciences" }]),
    ),
    http.get("*/api/v1/school/guardians", () => HttpResponse.json([])),
    http.get("*/api/v1/school/assignments", () => HttpResponse.json([])),
  );
}
