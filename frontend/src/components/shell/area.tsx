"use client";

// A signed-in area: the guard, then the app shell around the page.
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { Protected } from "@/components/shell/protected";
import type { Role } from "@/lib/auth";

export function Area({
  roles,
  children,
}: {
  roles?: Role[];
  children: ReactNode;
}) {
  return (
    <Protected roles={roles}>
      {(me) => <AppShell me={me}>{children}</AppShell>}
    </Protected>
  );
}
