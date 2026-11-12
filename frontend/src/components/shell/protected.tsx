"use client";

// Steers people to the right page: not signed in goes to /login, a temporary
// password goes to /change-password, the wrong role goes home. This is only
// for the user's sake; the API refuses anything the person may not do.
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { ErrorState, LoadingState } from "@/components/ui/layout";
import type { Me } from "@/lib/api/types";
import { type Role, homeFor, roleOf, useMe } from "@/lib/auth";

type Props = { roles?: Role[]; children: (me: Me) => ReactNode };

function whereTo(
  me: Me | null | undefined,
  roles: Role[] | undefined,
  path: string,
): string | null {
  if (me === undefined) return null;
  if (me === null) return `/login?next=${encodeURIComponent(path)}`;
  if (me.must_change_password && path !== "/change-password")
    return "/change-password";
  if (roles && !roles.includes(roleOf(me))) return homeFor(me);
  return null;
}

export function Protected({ roles, children }: Props) {
  const { data: me, isError, refetch } = useMe();
  const router = useRouter();
  const path = usePathname();
  const target = whereTo(me, roles, path);

  useEffect(() => {
    if (target) router.replace(target);
  }, [router, target]);

  if (isError)
    return <ErrorState thing="your account" onRetry={() => void refetch()} />;
  if (!me || target) return <LoadingState />;
  return <>{children(me)}</>;
}
