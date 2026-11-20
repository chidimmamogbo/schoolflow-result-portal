"use client";

// The super admin's code step after the password on /platform/login (SPEC F02
// rule 11, D-043; labels approved by Chidimma 2026-11-20). First time: scan a
// QR code, type the first code, save ten recovery codes. Later: a code from the
// app, or one recovery code. The server keeps the session "half signed in"
// until then and refuses everything else.
import { type FormEvent, useEffect, useState } from "react";

import { useFinishLogin } from "@/components/auth/finish-login";
import { Button } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { ApiError, api, ok } from "@/lib/api/client";

export const CODE_FAILED =
  "That code didn't work. Check the app and try again.";
const NOT_SET_UP = "Two-factor login is not set up on this server.";

function problemText(error: unknown): string {
  return error instanceof ApiError && error.status === 503
    ? NOT_SET_UP
    : CODE_FAILED;
}

function CodeForm({
  label,
  button,
  busy,
  error,
  onSubmit,
  autoComplete = "one-time-code",
  numeric = true,
}: {
  label: string;
  button: string;
  busy: boolean;
  error: string | null;
  onSubmit: (code: string) => void;
  autoComplete?: string;
  numeric?: boolean;
}) {
  const [code, setCode] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (code.trim()) onSubmit(code.trim());
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <FormError message={error} />
      <Field label={label}>
        {(field) => (
          <Input
            {...field}
            autoComplete={autoComplete}
            inputMode={numeric ? "numeric" : "text"}
            maxLength={numeric ? 6 : 20}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" variant="primary" busy={busy}>
        {button}
      </Button>
    </form>
  );
}

// Shown once: each works once if the phone is lost.
export function RecoveryCodes({
  codes,
  onDone,
}: {
  codes: string[];
  onDone?: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">Save your recovery codes</h2>
      <p className="text-muted">
        Each code works once, if you lose your phone. Keep them somewhere safe
        and private. You won&apos;t see them again.
      </p>
      <ul
        aria-label="Recovery codes"
        className="grid grid-cols-2 gap-2 rounded-md border border-border bg-surface-2 p-4 font-mono text-sm"
      >
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() =>
            void navigator.clipboard
              ?.writeText(codes.join("\n"))
              .catch(() => undefined)
          }
        >
          Copy codes
        </Button>
        <Button variant="ghost" onClick={() => window.print()}>
          Print
        </Button>
      </div>
      {onDone ? (
        <Button variant="primary" onClick={onDone}>
          I&apos;ve saved them
        </Button>
      ) : null}
    </div>
  );
}

function SetUpStep() {
  const finish = useFinishLogin();
  const [shown, setShown] = useState<{ secret: string; qr_svg: string } | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);

  useEffect(() => {
    let live = true;
    ok(api.POST("/api/v1/auth/two-factor/setup"))
      .then((answer) => live && setShown(answer))
      .catch((failure: unknown) => live && setLoadError(problemText(failure)));
    return () => {
      live = false;
    };
  }, []);

  async function confirm(code: string) {
    setBusy(true);
    setError(null);
    try {
      const done = await ok(
        api.POST("/api/v1/auth/two-factor/setup/confirm", { body: { code } }),
      );
      setCodes(done.recovery_codes);
    } catch (failure) {
      setError(problemText(failure));
    } finally {
      setBusy(false);
    }
  }

  if (codes) {
    return <RecoveryCodes codes={codes} onDone={() => void finish()} />;
  }
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">Set up two-factor login</h2>
      <p className="text-muted">
        Scan this QR code with an authenticator app, such as Google
        Authenticator or Microsoft Authenticator, then enter the 6-digit code it
        shows.
      </p>
      <FormError message={loadError} />
      {shown ? (
        <>
          {/* The QR code is an SVG image made by our own server; shown as an image, never as markup. */}
          {/* eslint-disable-next-line @next/next/no-img-element -- a data URL, not a remote image */}
          <img
            src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(shown.qr_svg)}`}
            alt="QR code for your authenticator app"
            className="size-48 self-center rounded-md bg-white p-2"
          />
          <p className="text-sm">
            Can&apos;t scan? Enter this key instead:{" "}
            <code className="font-mono break-all">{shown.secret}</code>
          </p>
          <CodeForm
            label="6-digit code"
            button="Turn on two-factor login"
            busy={busy}
            error={error}
            onSubmit={(code) => void confirm(code)}
          />
        </>
      ) : null}
    </div>
  );
}

function CodeStep() {
  const finish = useFinishLogin();
  const [recovery, setRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState<number | null>(null);

  async function send(code: string) {
    setBusy(true);
    setError(null);
    try {
      if (recovery) {
        const answer = await ok(
          api.POST("/api/v1/auth/two-factor/recovery", { body: { code } }),
        );
        setLeft(answer.codes_left);
      } else {
        await ok(
          api.POST("/api/v1/auth/two-factor/verify", { body: { code } }),
        );
        await finish();
      }
    } catch (failure) {
      setError(problemText(failure));
      setBusy(false);
    }
  }

  if (left !== null) {
    return (
      <div className="flex flex-col gap-4">
        <p role="status">You have {left} recovery codes left.</p>
        <Button variant="primary" onClick={() => void finish()}>
          Continue
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-semibold">
        {recovery ? "Use a recovery code" : "Enter your code"}
      </h2>
      {recovery ? null : (
        <p className="text-muted">
          Open your authenticator app and enter the 6-digit code for SchoolFlow.
        </p>
      )}
      <CodeForm
        key={recovery ? "recovery" : "app"}
        label={recovery ? "Recovery code" : "6-digit code"}
        button="Continue"
        busy={busy}
        error={error}
        numeric={!recovery}
        autoComplete={recovery ? "off" : "one-time-code"}
        onSubmit={(code) => void send(code)}
      />
      <button
        type="button"
        className="min-h-11 self-start text-sm font-medium text-primary hover:underline"
        onClick={() => {
          setRecovery(!recovery);
          setError(null);
        }}
      >
        {recovery
          ? "Use your authenticator app instead"
          : "Use a recovery code instead"}
      </button>
    </div>
  );
}

export function TwoFactor({ first }: { first: "setup" | "code" }) {
  return first === "setup" ? <SetUpStep /> : <CodeStep />;
}
