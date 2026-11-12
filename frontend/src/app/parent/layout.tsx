import type { ReactNode } from "react";

import { Area } from "@/components/shell/area";

export default function Layout({ children }: { children: ReactNode }) {
  return <Area roles={["parent"]}>{children}</Area>;
}
