"use client";

// Profile: who you are, and the two account actions from the header menu.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { CODE_FAILED, RecoveryCodes } from "@/components/auth/two-factor";
import { roleLabel } from "@/components/shell/nav";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FormError, Input } from "@/components/ui/form";
import { Card, PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";
import { useLogout, useMe } from "@/lib/auth";
import { loginPage } from "@/lib/school-memory";

// The super admin's two-factor login (D-043): codes left, and new recovery
// codes after a fresh code from the app (the old ones stop working).
function TwoFactorSection() {
  const left = useApi(["two-factor", "left"], () =>
    ok(api.GET("/api/v1/auth/two-factor/recovery-codes")),
  );
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function renew(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const answer = await ok(
        api.POST("/api/v1/auth/two-factor/recovery-codes", {
          body: { code: code.trim() },
        }),
      );
      setCodes(answer.recovery_codes);
      setCode("");
      void left.refetch();
    } catch {
      setError(CODE_FAILED);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex max-w-xl flex-col gap-4">
      <h2 className="text-xl font-semibold">Two-factor login</h2>
      {left.data ? (
        <p>On. {left.data.codes_left} recovery codes left.</p>
      ) : null}
      {codes ? (
        <RecoveryCodes codes={codes} />
      ) : (
        <form onSubmit={renew} className="flex flex-col gap-4" noValidate>
          <FormError message={error} />
          <Field label="6-digit code">
            {(field) => (
              <Input
                {...field}
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            )}
          </Field>
          <div>
            <Button type="submit" busy={busy} disabled={!code.trim()}>
              Make new recovery codes
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}

export default function ProfilePage() {
  const { data: me } = useMe();
  const logout = useLogout();
  const router = useRouter();
  if (!me) return null;
  return (
    <>
      <PageHeader title="Profile" />
      <Card className="flex max-w-xl flex-col gap-4">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
          <dt className="text-muted">Name</dt>
          <dd>{me.user.full_name}</dd>
          <dt className="text-muted">Username</dt>
          <dd>{me.user.username}</dd>
          {me.user.email ? (
            <>
              <dt className="text-muted">Email</dt>
              <dd className="break-all">{me.user.email}</dd>
            </>
          ) : null}
          <dt className="text-muted">Role</dt>
          <dd>{roleLabel(me)}</dd>
          {me.school ? (
            <>
              <dt className="text-muted">School</dt>
              <dd>{me.school.name}</dd>
            </>
          ) : null}
        </dl>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/change-password"
            className={buttonVariants({ variant: "secondary" })}
          >
            Change password
          </Link>
          <Button
            variant="ghost"
            onClick={async () => {
              const back = loginPage();
              await logout();
              router.replace(back);
            }}
          >
            Log out
          </Button>
        </div>
      </Card>
      {me.is_super_admin ? (
        <div className="mt-6">
          <TwoFactorSection />
        </div>
      ) : null}
    </>
  );
}
