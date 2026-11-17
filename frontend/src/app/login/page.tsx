"use client";

// /login: Find your school (SPEC F02 rule 2, D-182). A device that remembers
// its school goes straight to that school's page (or the platform page after
// a super admin login); "?change=1" stays here to pick another school. There
// is no search by name: the list of schools on SchoolFlow stays private.
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useEffect, useState } from "react";

import { LoginFrame, SCHOOLFLOW } from "@/components/auth/login-frame";
import { safeNext } from "@/components/auth/login-form";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { rememberedCode, usedPlatform } from "@/lib/school-memory";

function FindSchool() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const after = next ? `?next=${encodeURIComponent(next)}` : "";
  const [code, setCode] = useState("");

  useEffect(() => {
    if (params.get("change")) return;
    const remembered = rememberedCode();
    if (usedPlatform()) router.replace(`/platform/login${after}`);
    else if (remembered) router.replace(`/login/${remembered}${after}`);
  }, [after, params, router]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const wanted = code.trim().toUpperCase();
    if (wanted) router.push(`/login/${encodeURIComponent(wanted)}${after}`);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <Field
        label="School code"
        hint="It's on your login slip or welcome email."
      >
        {(field) => (
          <Input
            {...field}
            autoCapitalize="characters"
            autoComplete="organization"
            required
            maxLength={10}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
      </Field>
      <Button type="submit" variant="primary">
        Continue
      </Button>
    </form>
  );
}

export default function FindSchoolPage() {
  return (
    <LoginFrame
      brand={SCHOOLFLOW}
      title="Find your school"
      intro="Enter your school code to go to your school's login page."
    >
      <Suspense>
        <FindSchool />
      </Suspense>
    </LoginFrame>
  );
}
