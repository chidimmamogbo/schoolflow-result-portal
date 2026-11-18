"use client";

// /login/{code}: the school's own login page (SPEC F02 rules 1, 2 and 12;
// D-182). Its look comes from the school; only its own people can log in
// (the server refuses everyone else with the generic error). An old code
// forwards to the current one; an unknown code is not found.
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { LoginFrame, SCHOOLFLOW } from "@/components/auth/login-frame";
import { LoginForm } from "@/components/auth/login-form";
import { useSchoolLook } from "@/components/auth/school-brand";
import { LoadingState } from "@/components/ui/layout";

function SchoolLogin() {
  const { schoolCode } = useParams<{ schoolCode: string }>();
  const code = decodeURIComponent(schoolCode).toUpperCase();
  const look = useSchoolLook(code);
  const router = useRouter();
  const params = useSearchParams();
  const moved = look.state === "found" && look.code !== code ? look.code : null;

  useEffect(() => {
    if (moved) {
      const query = params.toString();
      router.replace(`/login/${moved}${query ? `?${query}` : ""}`);
    }
  }, [moved, params, router]);

  if (look.state === "missing") {
    return (
      <LoginFrame
        brand={SCHOOLFLOW}
        title="We couldn't find that school"
        intro="Check the code and try again."
      >
        <Link
          href="/login?change=1"
          className="font-medium text-primary hover:underline"
        >
          Find your school
        </Link>
      </LoginFrame>
    );
  }
  if (look.state === "loading" || moved) return <LoadingState />;
  return (
    <LoginFrame brand={look.brand} title="Welcome back">
      <LoginForm schoolCode={look.code} />
      <p className="mt-6 text-sm text-muted">
        Not {look.brand.name}?{" "}
        <Link
          href="/login?change=1"
          className="font-medium text-primary hover:underline"
        >
          Find your school
        </Link>
      </p>
    </LoginFrame>
  );
}

export default function SchoolLoginPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <SchoolLogin />
    </Suspense>
  );
}
