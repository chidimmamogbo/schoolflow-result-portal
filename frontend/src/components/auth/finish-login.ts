"use client";

// After a login (and the super admin's code): load who it is and go to their
// home page, or to change password first. Only a path on this site may be the
// "next" page.
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { ME_KEY, fetchMe, homeFor } from "@/lib/auth";

// Only a path on this site, never "//elsewhere" (an open redirect).
export function safeNext(next: string | null): string | null {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : null;
}

// Signed in: load who it is and go to their home page (or change password).
export function useFinishLogin() {
  const router = useRouter();
  const params = useSearchParams();
  const client = useQueryClient();
  return async () => {
    const me = await fetchMe();
    client.setQueryData(ME_KEY, me);
    if (!me) throw new Error("not signed in");
    router.replace(
      me.must_change_password
        ? "/change-password"
        : (safeNext(params.get("next")) ?? homeFor(me)),
    );
  };
}
