"use client";

// A school's look for the pages before login (SPEC F02 rules 2, 12 and 13,
// D-182), from GET /auth/schools/{code}/public. The server answers with the
// school's current code: when it differs from the one asked for (an old code
// within 30 days), the login page forwards.
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { type ReactNode, Suspense, useSyncExternalStore } from "react";

import { ApiError, api, ok } from "@/lib/api/client";
import { rememberedCode } from "@/lib/school-memory";

import { type LoginBrand, LoginFrame, SCHOOLFLOW } from "./login-frame";

export type SchoolLook =
  | { state: "loading" }
  | { state: "missing" }
  | { state: "found"; code: string; brand: LoginBrand };

export function useSchoolLook(code: string | null): SchoolLook {
  const query = useQuery({
    queryKey: ["school-public", code],
    enabled: code !== null,
    retry: (count, error) =>
      !(error instanceof ApiError && error.status === 404) && count < 2,
    queryFn: () =>
      ok(
        api.GET("/api/v1/auth/schools/{code}/public", {
          params: { path: { code: code ?? "" } },
        }),
      ),
  });
  if (code === null || query.isError) return { state: "missing" };
  if (!query.data) return { state: "loading" };
  const school = query.data;
  return {
    state: "found",
    code: school.code,
    brand: {
      name: school.name,
      code: school.code,
      colour: school.colour,
      logoUrl: school.logo_url,
      message: school.message,
      layout: school.layout,
      picture: school.picture,
      photoUrl: school.photo_url,
    },
  };
}

const never = () => () => {};

// The device's remembered school code, read only in the browser (none while
// the server renders the page, so both renders agree).
export function useRememberedCode(): string | null {
  return useSyncExternalStore(never, rememberedCode, () => null);
}

function Branded(props: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  const params = useSearchParams();
  const remembered = useRememberedCode();
  const asked = params.get("school");
  const code = asked && /^[A-Za-z0-9]{3,10}$/.test(asked) ? asked : remembered;
  const look = useSchoolLook(code);
  return (
    <LoginFrame
      brand={look.state === "found" ? look.brand : SCHOOLFLOW}
      {...props}
    />
  );
}

// Forgot password, Reset password, Activate account, Change password and the
// paused page: the school from the email link (?school=) or this device, else
// SchoolFlow's own look (F02 rule 13).
export function SchoolAuthFrame(props: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Suspense fallback={<LoginFrame brand={SCHOOLFLOW} {...props} />}>
      <Branded {...props} />
    </Suspense>
  );
}
