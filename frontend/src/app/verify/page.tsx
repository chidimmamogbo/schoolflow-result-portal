"use client";

// /verify: type the code printed under the QR on a report card (D-072: 12 characters).
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";

export default function VerifyPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const clean = code.trim();
    if (clean) router.push(`/verify/${encodeURIComponent(clean)}`);
  }
  return (
    <AuthCard
      title="Verify a report card"
      intro="Type the verification code printed on the report card, or scan its QR code."
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <Field label="Verification code" hint="For example 7KQ4-M2XD-P9QA.">
          {(field) => (
            <Input
              {...field}
              autoCapitalize="characters"
              autoComplete="off"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="primary" disabled={!code.trim()}>
          Verify
        </Button>
      </form>
    </AuthCard>
  );
}
