"use client";

// Login (NAVIGATION "Login"; SPEC F02 rules 1 and 11, D-182). On a school's
// own page: tabs Staff and parents · Student, the school code coming from the
// link. On /platform/login: the super admin's form. One error for every
// failure, so it never says which detail was wrong, nor that an account
// belongs on another page (non-negotiable).
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  type FormEvent,
  type ReactNode,
  useState,
  useSyncExternalStore,
} from "react";

import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { ME_KEY, fetchMe, homeFor } from "@/lib/auth";
import {
  type LoginTab,
  chooseSchoolId,
  rememberCode,
  rememberPlatform,
  rememberTab,
  rememberedTab,
} from "@/lib/school-memory";

export const LOGIN_FAILED =
  "That login didn't work. Check your details and try again.";

// Only a path on this site, never "//elsewhere" (an open redirect).
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

type Result = { must_change_password: boolean; school_id?: string | null };

type Send = (identifier: string, password: string) => Promise<Result>;

function useLogin(send: Send, after: (r: Result) => void) {
  const router = useRouter();
  const params = useSearchParams();
  const client = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(identifier: string, password: string) {
    setBusy(true);
    setError(null);
    try {
      const result = await send(identifier, password);
      after(result);
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

function Credentials({
  idLabel,
  onSubmit,
  error,
  busy,
  footer,
}: {
  idLabel: string;
  onSubmit: (identifier: string, password: string) => void;
  error: string | null;
  busy: boolean;
  footer: ReactNode;
}) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(identifier.trim(), password);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <FormError message={error} />
      <Field label={idLabel}>
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
      {footer}
    </form>
  );
}

function SchoolTab({ schoolCode, tab }: { schoolCode: string; tab: LoginTab }) {
  const { submit, error, busy } = useLogin(
    (identifier, password) =>
      ok(
        api.POST("/api/v1/auth/login", {
          body: { identifier, password, school_code: schoolCode, tab },
        }),
      ),
    (result) => {
      rememberCode(schoolCode);
      rememberTab(tab);
      chooseSchoolId(result.school_id ?? null);
    },
  );
  return (
    <Credentials
      idLabel={
        tab === "staff" ? "Email or username" : "Username or admission number"
      }
      error={error}
      busy={busy}
      onSubmit={(identifier, password) => void submit(identifier, password)}
      footer={
        tab === "staff" ? (
          <Link
            href={`/forgot-password?school=${schoolCode}`}
            className="text-sm font-medium text-primary hover:underline"
          >
            Forgot password?
          </Link>
        ) : (
          <p className="text-sm text-muted">
            Forgot your password? Ask your school admin for a new one.
          </p>
        )
      }
    />
  );
}

const never = () => () => {};

// A school's own login page: Staff and parents · Student (F02 rule 1). The tab
// used last on this device opens first; Student on a first visit.
export function LoginForm({ schoolCode }: { schoolCode: string }) {
  const remembered = useSyncExternalStore(
    never,
    rememberedTab,
    () => "student",
  );
  const [chosen, setChosen] = useState<LoginTab | null>(null);
  const value = chosen ?? remembered;
  return (
    <Tabs
      label="Who is logging in"
      value={value}
      onValueChange={(next) => setChosen(next as LoginTab)}
      tabs={[
        {
          value: "staff",
          label: "Staff and parents",
          content: <SchoolTab schoolCode={schoolCode} tab="staff" />,
        },
        {
          value: "student",
          label: "Student",
          content: <SchoolTab schoolCode={schoolCode} tab="student" />,
        },
      ]}
    />
  );
}

// /platform/login: the super admin only (F02 rule 11).
export function PlatformLoginForm() {
  const { submit, error, busy } = useLogin(
    (identifier, password) =>
      ok(
        api.POST("/api/v1/auth/platform/login", {
          body: { identifier, password },
        }),
      ),
    () => {
      rememberPlatform();
      chooseSchoolId(null);
    },
  );
  return (
    <Credentials
      idLabel="Email or username"
      error={error}
      busy={busy}
      onSubmit={(identifier, password) => void submit(identifier, password)}
      footer={
        <p className="border-t border-border pt-4 text-sm text-muted">
          Looking for your school?{" "}
          <Link
            href="/login?change=1"
            className="font-medium text-primary hover:underline"
          >
            Find your school
          </Link>
        </p>
      }
    />
  );
}
