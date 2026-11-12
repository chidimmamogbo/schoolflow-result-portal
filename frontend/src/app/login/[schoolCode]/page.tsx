"use client";

// /login/{code}: the school's logo and name above the card, the Student tab
// chosen and the school code filled in (NAVIGATION "Login").
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";
import { api, ok } from "@/lib/api/client";

export default function SchoolLoginPage() {
  const { schoolCode } = useParams<{ schoolCode: string }>();
  const code = decodeURIComponent(schoolCode).toUpperCase();
  const { data: school } = useQuery({
    queryKey: ["school-public", code],
    queryFn: () =>
      ok(
        api.GET("/api/v1/auth/schools/{code}/public", {
          params: { path: { code } },
        }),
      ),
  });
  const brand = school ? (
    <div className="flex flex-col items-center gap-2">
      {school.logo_url ? (
        // eslint-disable-next-line @next/next/no-img-element -- a school's own uploaded logo
        <img
          src={school.logo_url}
          alt=""
          className="size-16 rounded-md object-contain"
        />
      ) : (
        <span
          aria-hidden="true"
          className="flex size-16 items-center justify-center rounded-md text-lg font-bold text-white"
          style={{ background: school.colour }}
        >
          {school.code}
        </span>
      )}
      <p className="text-lg font-bold">{school.name}</p>
    </div>
  ) : undefined;
  return (
    <AuthCard title="Welcome back" brand={brand}>
      <Suspense>
        <LoginForm studentFirst schoolCode={code} />
      </Suspense>
    </AuthCard>
  );
}
