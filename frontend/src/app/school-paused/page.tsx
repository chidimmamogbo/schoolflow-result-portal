"use client";

// Shown when a school's access is paused (NAVIGATION "Login"), in the school's look.
import Link from "next/link";

import { SchoolAuthFrame } from "@/components/auth/school-brand";

export default function SchoolPausedPage() {
  return (
    <SchoolAuthFrame title="Access paused">
      <p className="mb-6">
        Your school&apos;s access is paused. Contact your school admin.
      </p>
      <Link href="/login" className="font-medium text-primary hover:underline">
        Back to login
      </Link>
    </SchoolAuthFrame>
  );
}
