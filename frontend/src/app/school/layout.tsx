import type { ReactNode } from "react";

import { Area } from "@/components/shell/area";

export default function Layout({ children }: { children: ReactNode }) {
  return <Area roles={["school_admin"]}>{children}</Area>;
}
