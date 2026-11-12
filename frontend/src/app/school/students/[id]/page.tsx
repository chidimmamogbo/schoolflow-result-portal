"use client";

// A student: details, class, login and guardians.
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ArmSelect } from "@/components/people/arm-select";
import {
  CredentialSlip,
  LoginSupport,
} from "@/components/people/login-support";
import { PupilForm, type PupilDetails } from "@/components/people/pupil-form";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import {
  KEYS,
  armNames,
  fullName,
  useClasses,
  useGuardians,
  useSchool,
  useStudents,
} from "@/lib/api/school";

function PupilSubjects({ studentId }: { studentId: string }) {
  const { data } = useApi(["school", "pupil-subjects", studentId], () =>
    ok(
      api.GET("/api/v1/school/students/{student_id}/subjects", {
        params: { path: { student_id: studentId } },
      }),
    ),
  );
  if (!data) return <LoadingState />;
  return data.length ? (
    <Card>
      <ul className="grid gap-1 md:grid-cols-2">
        {data.map((s) => (
          <li key={s.id}>{s.name}</li>
        ))}
      </ul>
    </Card>
  ) : (
    <EmptyState title="Not enrolled in a class this session." />
  );
}

export default function StudentPage() {
  const { id } = useParams<{ id: string }>();
  const { data: pupils, isPending } = useStudents();
  const { data: classes } = useClasses();
  const { data: guardians } = useGuardians();
  const { data: school } = useSchool();
  const [arm, setArm] = useState("");
  const [username, setUsername] = useState("");
  const [slip, setSlip] = useState<string | null>(null);
  const pupil = pupils?.find((p) => p.id === id);
  const path = { params: { path: { student_id: id } } };
  const save = useAction(
    (body: PupilDetails) =>
      ok(api.PATCH("/api/v1/school/students/{student_id}", { ...path, body })),
    {
      invalidate: [[...KEYS.students]],
      done: "Saved.",
    },
  );
  const move = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/students/{student_id}/move", {
          ...path,
          body: { arm_id: arm },
        }),
      ),
    {
      invalidate: [[...KEYS.students]],
      done: "Class changed.",
    },
  );
  const login = useAction(
    () =>
      ok(
        api.POST("/api/v1/school/students/{student_id}/login", {
          ...path,
          body: { username: username.trim() },
        }),
      ),
    {
      invalidate: [[...KEYS.students]],
      onDone: (result) => setSlip(result.temporary_password),
    },
  );
  if (isPending) return <LoadingState />;
  if (!pupil)
    return (
      <EmptyState
        title="We couldn't find that student."
        action={
          <Link className="text-primary underline" href="/school/students">
            Back to students
          </Link>
        }
      />
    );
  const names = armNames(classes);
  const theirs = (guardians ?? []).filter((g) =>
    g.wards.some((w) => w.student_id === id),
  );
  return (
    <>
      <PageHeader
        title={fullName(pupil)}
        caption={`${pupil.admission_number} · ${(pupil.arm_id && names.get(pupil.arm_id)) || "Not in a class"}`}
        actions={<StatusBadge status={pupil.status} />}
      />
      <Tabs
        label="Student"
        tabs={[
          {
            value: "details",
            label: "Details",
            content: (
              <Card>
                <PupilForm
                  pupil={pupil}
                  busy={save.isPending}
                  submitLabel="Save changes"
                  onSubmit={(d) => save.mutate(d)}
                />
              </Card>
            ),
          },
          {
            value: "subjects",
            label: "Subjects",
            content: <PupilSubjects studentId={id} />,
          },
          {
            value: "class",
            label: "Class",
            content: (
              <Card className="grid max-w-[var(--form-max)] gap-4">
                <Field label="Move to class">
                  {(f) => (
                    <ArmSelect
                      {...f}
                      value={arm}
                      onChange={(e) => setArm(e.target.value)}
                    />
                  )}
                </Field>
                <div>
                  <Button
                    variant="primary"
                    disabled={!arm}
                    busy={move.isPending}
                    onClick={() => move.mutate(undefined)}
                  >
                    Move
                  </Button>
                </div>
              </Card>
            ),
          },
          {
            value: "login",
            label: "Login",
            content: (
              <Card className="grid max-w-[var(--form-max)] gap-4">
                {pupil.has_login && pupil.user_id ? (
                  <>
                    <p>
                      This student has a login. Students can&apos;t reset their
                      own password; issue a temporary password here instead.
                    </p>
                    <LoginSupport
                      person={{
                        id: pupil.user_id,
                        full_name: fullName(pupil),
                        username: pupil.admission_number,
                        email: null,
                        is_active: true,
                        activated: true,
                      }}
                      invalidate={[[...KEYS.students]]}
                    />
                  </>
                ) : (
                  <>
                    <Field
                      label="Username"
                      hint="The student logs in with this or their admission number, and the school code."
                    >
                      {(f) => (
                        <Input
                          {...f}
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                        />
                      )}
                    </Field>
                    <div>
                      <Button
                        variant="primary"
                        disabled={!username.trim()}
                        busy={login.isPending}
                        onClick={() => login.mutate(undefined)}
                      >
                        Give login
                      </Button>
                    </div>
                  </>
                )}
              </Card>
            ),
          },
          {
            value: "guardians",
            label: "Guardians",
            content: theirs.length ? (
              <ul className="grid gap-2">
                {theirs.map((g) => (
                  <li key={g.id}>
                    <Link
                      className="font-medium text-primary hover:underline"
                      href={`/school/parents/${g.id}`}
                    >
                      {g.full_name}
                    </Link>{" "}
                    <span className="text-muted">
                      ({g.wards.find((w) => w.student_id === id)?.relationship})
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                title="No guardians linked yet."
                action={
                  <Link
                    className="text-primary underline"
                    href="/school/parents/new"
                  >
                    Add a parent
                  </Link>
                }
              />
            ),
          },
        ]}
      />
      <CredentialSlip
        title="Student login slip"
        password={slip}
        name={fullName(pupil)}
        username={username.trim()}
        schoolCode={school?.code}
        onClose={() => setSlip(null)}
      />
    </>
  );
}
