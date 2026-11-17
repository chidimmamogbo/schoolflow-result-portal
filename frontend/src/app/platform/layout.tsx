"use client";

// The super admin's area. Its login page, /platform/login, sits outside the
// guard: nobody is signed in there yet (SPEC F02 rule 11, D-182).
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { Area } from "@/components/shell/area";

export default function Layout({ children }: { children: ReactNode }) {
  if (usePathname() === "/platform/login") return <>{children}</>;
  return <Area roles={["super_admin"]}>{children}</Area>;
}
