"use client";

// Lists many school admin pages share, with one cache key each, so a change on
// one page refreshes the others.
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import type { Schemas } from "@/lib/api/types";

export const KEYS = {
  school: ["school"],
  sessions: ["school", "sessions"],
  classes: ["school", "classes"],
  subjects: ["school", "subjects"],
  departments: ["school", "departments"],
  staff: ["school", "staff"],
  students: ["school", "students"],
  guardians: ["school", "guardians"],
  assignments: ["school", "assignments"],
  admins: ["school", "admins"],
  grading: ["school", "grading"],
  traits: ["school", "traits"],
  scale: ["school", "scale"],
  areas: ["school", "areas"],
} as const;

export type Arm = Schemas["ArmRow"];
export type ClassRow = Schemas["ClassRow"];
export type Pupil = Schemas["app__src__students__schemas__PupilRow"];
export type Staff = Schemas["StaffRow"];
export type Guardian = Schemas["GuardianRow"];
export type Assignment = Schemas["AssignmentRow"];

export const LEVELS: Record<string, string> = {
  nursery: "Nursery",
  primary: "Primary",
  junior_secondary: "Junior Secondary",
  senior_secondary: "Senior Secondary",
};

export function useSchool() {
  return useApi([...KEYS.school], () => ok(api.GET("/api/v1/school")));
}
export function useClasses() {
  return useApi([...KEYS.classes], () => ok(api.GET("/api/v1/school/classes")));
}
export function useSubjects() {
  return useApi([...KEYS.subjects], () =>
    ok(api.GET("/api/v1/school/subjects")),
  );
}
export function useDepartments() {
  return useApi([...KEYS.departments], () =>
    ok(api.GET("/api/v1/school/departments")),
  );
}
export function useStaff() {
  return useApi([...KEYS.staff], () => ok(api.GET("/api/v1/school/staff")));
}
export function useStudents() {
  return useApi([...KEYS.students], () =>
    ok(api.GET("/api/v1/school/students")),
  );
}
export function useGuardians() {
  return useApi([...KEYS.guardians], () =>
    ok(api.GET("/api/v1/school/guardians")),
  );
}
export function useAssignments() {
  return useApi([...KEYS.assignments], () =>
    ok(api.GET("/api/v1/school/assignments")),
  );
}

// "JSS 1A" for an arm, "Nursery 2" when the class has one unnamed arm.
export function armNames(classes: ClassRow[] | undefined): Map<string, string> {
  const names = new Map<string, string>();
  for (const row of classes ?? []) {
    for (const arm of row.arms) names.set(arm.id, `${row.name}${arm.name}`);
  }
  return names;
}

export function fullName(
  pupil: Pick<Pupil, "first_name" | "surname" | "other_names">,
): string {
  return [pupil.first_name, pupil.other_names, pupil.surname]
    .filter(Boolean)
    .join(" ");
}
