"use client";

// Setting a password from an emailed link: activation, reset and joining as a
// new parent. The token is after "#token=" in the link, so it is never sent to
// any server in a URL or kept in history (D-081).
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import {
  LINK_INVALID,
  localProblem,
  minLength,
  serverProblem,
} from "@/components/auth/password-rules";
import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { api, ok } from "@/lib/api/client";
import { ME_KEY, fetchMe, homeFor } from "@/lib/auth";

type Endpoint =
  "/api/v1/auth/activate" | "/api/v1/auth/password/reset" | "/api/v1/auth/join";

export function tokenFromHash(hash: string): string | null {
  const match = /(?:^#|&)token=([A-Za-z0-9_-]+)/.exec(hash);
  return match?.[1] ?? null;
}

export function SetPassword({
  endpoint,
  title,
  intro,
}: {
  endpoint: Endpoint;
  title: string;
  intro: string;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const [token, setToken] = useState<string | null | undefined>(undefined);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // The address bar exists only in the browser, so it is read after the first render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(tokenFromHash(window.location.hash));
    // Take the token out of the address bar once it is read.
    window.history.replaceState(null, "", window.location.pathname);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = localProblem(password, confirm, false);
    if (problem) return setError(problem);
    if (!token) return setError(LINK_INVALID);
    setBusy(true);
    setError(null);
    try {
      await ok(api.POST(endpoint, { body: { token, password } }));
      const me = await fetchMe();
      client.setQueryData(ME_KEY, me);
      router.replace(me ? homeFor(me) : "/login");
    } catch (failure) {
      setError(serverProblem(failure, false));
      setBusy(false);
    }
  }

  return (
    <AuthCard title={title} intro={intro}>
      {token === null ? (
        <FormError message={LINK_INVALID} />
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormError message={error} />
          <Field
            label="New password"
            hint={`At least ${minLength(false)} characters.`}
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
          <Button
            type="submit"
            variant="primary"
            busy={busy}
            disabled={token === undefined}
          >
            Save password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
