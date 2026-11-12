"use client";

import { SetPassword } from "@/components/auth/set-password";

export default function JoinPage() {
  return (
    <SetPassword
      endpoint="/api/v1/auth/join"
      title="Set your password"
      intro="Your child's school has added you as a parent or guardian. Set a password to see their results."
    />
  );
}
