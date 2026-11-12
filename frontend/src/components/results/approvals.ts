// Which sheets wait for the principal: a sheet a reviewer covers is reviewed
// first; one nobody covers goes straight to approval (D-142).
import type { Schemas } from "@/lib/api/types";

type Sheet = Schemas["SheetSummary"];

export function waitsForApproval(s: Sheet): boolean {
  return (
    s.status === "reviewed" ||
    ((s.status === "submitted" || s.status === "resubmitted") &&
      !s.needs_review)
  );
}
