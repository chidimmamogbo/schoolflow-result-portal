"use client";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ReportPage } from "@/components/portal/portal";

function Report() {
  const { reportId } = useParams<{ reportId: string }>();
  const school = useSearchParams().get("school");
  return (
    <ReportPage base="/parent" reportId={reportId} schoolId={school || null} />
  );
}

export default function Page() {
  return (
    <Suspense>
      <Report />
    </Suspense>
  );
}
