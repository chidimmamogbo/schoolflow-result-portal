"use client";

// A parent: children, contact details and login (link request, pause, remove).
import { useParams } from "next/navigation";
import { useState } from "react";

import { WardPicker } from "@/components/people/ward-picker";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import {
  Card,
  EmptyState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";
import { KEYS, useGuardians } from "@/lib/api/school";

const LOGIN: Record<string, string> = {
  none: "No login",
  waiting: "Link request sent",
  linked: "Linked",
  paused: "Paused",
};

export default function ParentPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isPending } = useGuardians();
  const guardian = data?.find((g) => g.id === id);
  const [phone, setPhone] = useState<string | null>(null);
  const path = { params: { path: { guardian_id: id } } };
  const keys = { invalidate: [[...KEYS.guardians]] };
  const link = useAction(
    (w: { student_id: string; relationship: string }) =>
      ok(
        api.POST("/api/v1/school/guardians/{guardian_id}/wards", {
          ...path,
          body: w,
        }),
      ),
    { ...keys, done: "Child linked." },
  );
  const unlink = useAction(
    (student: string) =>
      ok(
        api.DELETE(
          "/api/v1/school/guardians/{guardian_id}/wards/{student_id}",
          { params: { path: { guardian_id: id, student_id: student } } },
        ),
      ),
    { ...keys, done: "Child unlinked." },
  );
  const save = useAction(
    () =>
      ok(
        api.PATCH("/api/v1/school/guardians/{guardian_id}", {
          ...path,
          body: { phone: (phone ?? "").trim() || null },
        }),
      ),
    { ...keys, done: "Saved." },
  );
  const resend = useAction(
    () =>
      ok(
        api.POST(
          "/api/v1/school/guardians/{guardian_id}/link-request/resend",
          path,
        ),
      ),
    { ...keys, done: "Link request sent again." },
  );
  const cancel = useAction(
    () =>
      ok(
        api.DELETE("/api/v1/school/guardians/{guardian_id}/link-request", path),
      ),
    { ...keys, done: "Link request cancelled." },
  );
  const pause = useAction(
    () => ok(api.POST("/api/v1/school/guardians/{guardian_id}/pause", path)),
    { ...keys, done: "Access paused." },
  );
  const resume = useAction(
    () => ok(api.POST("/api/v1/school/guardians/{guardian_id}/resume", path)),
    { ...keys, done: "Access resumed." },
  );
  const removeLogin = useAction(
    () => ok(api.DELETE("/api/v1/school/guardians/{guardian_id}/login", path)),
    { ...keys, done: "Login removed from this school." },
  );
  if (isPending) return <LoadingState />;
  if (!guardian) return <EmptyState title="We couldn't find that parent." />;
  return (
    <>
      <PageHeader
        title={guardian.full_name}
        caption={LOGIN[guardian.login_status]}
      />
      <div className="grid gap-6">
        <Card>
          <h2 className="mb-3 text-xl font-semibold">Children</h2>
          <ul className="mb-4 grid gap-1">
            {guardian.wards.map((w) => (
              <li
                key={w.student_id}
                className="flex items-center justify-between gap-2"
              >
                <span>
                  {w.name} ({w.relationship})
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => unlink.mutate(w.student_id)}
                >
                  Unlink
                </Button>
              </li>
            ))}
          </ul>
          <WardPicker
            label="Link child"
            busy={link.isPending}
            exclude={guardian.wards.map((w) => w.student_id)}
            onAdd={(w) => link.mutate(w)}
          />
        </Card>
        <Card className="grid max-w-[var(--form-max)] gap-3">
          <h2 className="text-xl font-semibold">Contact</h2>
          <p className="text-muted">{guardian.email ?? "No email"}</p>
          <Field label="Phone">
            {(f) => (
              <Input
                {...f}
                type="tel"
                value={phone ?? guardian.phone ?? ""}
                onChange={(e) => setPhone(e.target.value)}
              />
            )}
          </Field>
          <div>
            <Button
              busy={save.isPending}
              disabled={phone === null}
              onClick={() => save.mutate(undefined)}
            >
              Save changes
            </Button>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 text-xl font-semibold">Login</h2>
          <div className="flex flex-wrap gap-2">
            {guardian.login_status === "waiting" ? (
              <>
                <Button
                  busy={resend.isPending}
                  onClick={() => resend.mutate(undefined)}
                >
                  Resend link request
                </Button>
                <Button
                  busy={cancel.isPending}
                  onClick={() => cancel.mutate(undefined)}
                >
                  Cancel link request
                </Button>
              </>
            ) : null}
            {guardian.login_status === "linked" ? (
              <Button
                busy={pause.isPending}
                onClick={() => pause.mutate(undefined)}
              >
                Pause access
              </Button>
            ) : null}
            {guardian.login_status === "paused" ? (
              <Button
                busy={resume.isPending}
                onClick={() => resume.mutate(undefined)}
              >
                Resume access
              </Button>
            ) : null}
            {guardian.login_status === "linked" ||
            guardian.login_status === "paused" ? (
              <Button
                variant="danger"
                busy={removeLogin.isPending}
                onClick={() => removeLogin.mutate(undefined)}
              >
                Remove login
              </Button>
            ) : null}
            {guardian.login_status === "none" ? (
              <p className="text-muted">This parent has no login.</p>
            ) : null}
          </div>
        </Card>
      </div>
    </>
  );
}
