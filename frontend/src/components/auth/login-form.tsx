"use client";

// Login (NAVIGATION "Login"): tabs Staff and parents · Student. One error for
// every failure, so it never says which detail was wrong (non-negotiable).
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { ME_KEY, fetchMe, homeFor } from "@/lib/auth";

export const LOGIN_FAILED =
  "That login didn't work. Check your details and try again.";

// Only a path on this site, never "//elsewhere" (an open redirect).
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

function useLogin() {
  const router = useRouter();
  const params = useSearchParams();
  const client = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(body: {
    identifier: string;
    password: string;
    school_code?: string;
  }) {
    setBusy(true);
    setError(null);
    try {
      await ok(api.POST("/api/v1/auth/login", { body }));
      const me = await fetchMe();
      client.setQueryData(ME_KEY, me);
      if (!me) throw new Error("not signed in");
      router.replace(
        me.must_change_password
          ? "/change-password"
          : (safeNext(params.get("next")) ?? homeFor(me)),
      );
    } catch {
      setError(LOGIN_FAILED);
      setBusy(false);
    }
  }
  return { submit, error, busy };
}

function StaffForm() {
  const { submit, error, busy } = useLogin();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit({ identifier: identifier.trim(), password });
  };
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <FormError message={error} />
      <Field label="Email or username">
        {(field) => (
          <Input
            {...field}
            autoComplete="username"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
          />
        )}
      </Field>
      <Field label="Password">
        {(field) => (
          <Input
            {...field}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" variant="primary" busy={busy}>
        Log in
      </Button>
      <Link
        href="/forgot-password"
        className="text-sm font-medium text-primary hover:underline"
      >
        Forgot password?
      </Link>
    </form>
  );
}

function StudentForm({ schoolCode }: { schoolCode?: string }) {
  const { submit, error, busy } = useLogin();
  const [code, setCode] = useState(schoolCode ?? "");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit({
      identifier: identifier.trim(),
      password,
      school_code: code.trim().toUpperCase(),
    });
  };
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <FormError message={error} />
      <Field label="School code">
        {(field) => (
          <Input
            {...field}
            autoCapitalize="characters"
            required
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
      </Field>
      <Field label="Username or admission number">
        {(field) => (
          <Input
            {...field}
            autoComplete="username"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
          />
        )}
      </Field>
      <Field label="Password">
        {(field) => (
          <Input
            {...field}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" variant="primary" busy={busy}>
        Log in
      </Button>
      <p className="text-sm text-muted">
        Forgot your password? Ask your school admin for a new one.
      </p>
    </form>
  );
}

export function LoginForm({
  studentFirst,
  schoolCode,
}: {
  studentFirst?: boolean;
  schoolCode?: string;
}) {
  return (
    <Tabs
      label="Who is logging in"
      value={undefined}
      tabs={
        studentFirst
          ? [
              {
                value: "student",
                label: "Student",
                content: <StudentForm schoolCode={schoolCode} />,
              },
              {
                value: "staff",
                label: "Staff and parents",
                content: <StaffForm />,
              },
            ]
          : [
              {
                value: "staff",
                label: "Staff and parents",
                content: <StaffForm />,
              },
              {
                value: "student",
                label: "Student",
                content: <StudentForm schoolCode={schoolCode} />,
              },
            ]
      }
    />
  );
}
