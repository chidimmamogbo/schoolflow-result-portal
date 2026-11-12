"use client";

import { useRouter } from "next/navigation";

import { PupilForm, type PupilDetails } from "@/components/people/pupil-form";
import { PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS } from "@/lib/api/school";

export default function NewStudentPage() {
  const router = useRouter();
  const create = useAction(
    (body: PupilDetails) => ok(api.POST("/api/v1/school/students", { body })),
    {
      invalidate: [[...KEYS.students]],
      done: "Student added.",
      onDone: (pupil) => router.push(`/school/students/${pupil.id}`),
    },
  );
  return (
    <>
      <PageHeader title="Add student" />
      <PupilForm
        withClass
        busy={create.isPending}
        submitLabel="Add student"
        onSubmit={(d) => create.mutate(d)}
      />
    </>
  );
}
