"use client";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ChildReports } from "@/components/portal/portal";

function Reports() {
  const { studentId } = useParams<{ studentId: string }>();
  const school = useSearchParams().get("school");
  return (
    <ChildReports
      base="/parent"
      studentId={studentId}
      schoolId={school || null}
    />
  );
}

export default function Page() {
  return (
    <Suspense>
      <Reports />
    </Suspense>
  );
}
