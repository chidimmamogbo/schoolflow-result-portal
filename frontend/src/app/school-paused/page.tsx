// Shown when a school's access is paused (NAVIGATION "Login").
import Link from "next/link";

import { AuthCard } from "@/components/auth/auth-card";

export default function SchoolPausedPage() {
  return (
    <AuthCard title="Access paused">
      <p className="mb-6">
        Your school&apos;s access is paused. Contact your school admin.
      </p>
      <Link href="/login" className="font-medium text-primary hover:underline">
        Back to login
      </Link>
    </AuthCard>
  );
}
