"use client";

// The same answer for every address, so it never reveals who has an account (AC02.8).
import Link from "next/link";
import { type FormEvent, useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api/client";

const SENT =
  "If that email has an account, we've sent a link to reset your password. It works for 1 hour.";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    // Whatever the answer, the page says the same thing.
    await api
      .POST("/api/v1/auth/password/forgot", { body: { email: email.trim() } })
      .catch(() => undefined);
    setSent(true);
    setBusy(false);
  }

  return (
    <AuthCard
      title="Forgot password?"
      intro="No email on your account? Ask your school admin to reset your password."
    >
      {sent ? (
        <div className="flex flex-col gap-4">
          <p role="status">{SENT}</p>
          <Link
            href="/login"
            className="font-medium text-primary hover:underline"
          >
            Back to login
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <Field label="Email">
            {(field) => (
              <Input
                {...field}
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            )}
          </Field>
          <Button
            type="submit"
            variant="primary"
            busy={busy}
            disabled={!email.trim()}
          >
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
