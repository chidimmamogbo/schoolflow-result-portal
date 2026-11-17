"use client";

// /platform/login: the super admin's own login page (SPEC F02 rule 11, D-182).
// Every other account gets the generic error from the server.
import { Suspense } from "react";

import { LoginFrame, SCHOOLFLOW } from "@/components/auth/login-frame";
import { PlatformLoginForm } from "@/components/auth/login-form";

export default function PlatformLoginPage() {
  return (
    <LoginFrame
      brand={SCHOOLFLOW}
      title="Platform login"
      intro="For the SchoolFlow team only."
    >
      <Suspense>
        <PlatformLoginForm />
      </Suspense>
    </LoginFrame>
  );
}
