"use client";

// Change password; forced after a temporary password (NAVIGATION section 5,
// rule text per D-036 and D-134: 15 characters, 10 for students).
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import {
  localProblem,
  minLength,
  serverProblem,
} from "@/components/auth/password-rules";
import { Protected } from "@/components/shell/protected";
import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { api, ok } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { ME_KEY, fetchMe, homeFor, roleOf } from "@/lib/auth";

function ChangePassword({ me }: { me: Me }) {
  const router = useRouter();
  const client = useQueryClient();
  const student = roleOf(me) === "student";
  const forced = me.must_change_password;
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = localProblem(password, confirm, student);
    if (problem) return setError(problem);
    setBusy(true);
    setError(null);
    try {
      await ok(
        api.POST("/api/v1/auth/change-password", {
          body: { current_password: current, new_password: password },
        }),
      );
      client.setQueryData(ME_KEY, await fetchMe());
      setDone(true);
    } catch (failure) {
      setError(serverProblem(failure, student));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    const next = client.getQueryData<Me | null>(ME_KEY);
    return (
      <AuthCard title="Change password">
        <div className="flex flex-col gap-4">
          <p role="status">Your password is changed.</p>
          <Button
            variant="primary"
            onClick={() => router.replace(next ? homeFor(next) : "/login")}
          >
            Continue
          </Button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Change password"
      intro={
        forced
          ? "You logged in with a temporary password. Choose a new one to continue."
          : undefined
      }
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <FormError message={error} />
        <Field label={forced ? "Temporary password" : "Current password"}>
          {(field) => (
            <Input
              {...field}
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          )}
        </Field>
        <Field
          label="New password"
          hint={`At least ${minLength(student)} characters.${forced ? " Different from your temporary password." : ""}`}
        >
          {(field) => (
            <Input
              {...field}
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <Field label="Confirm new password">
          {(field) => (
            <Input
              {...field}
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="primary" busy={busy}>
          Save password
        </Button>
      </form>
    </AuthCard>
  );
}

export default function ChangePasswordPage() {
  return <Protected>{(me) => <ChangePassword me={me} />}</Protected>;
}
