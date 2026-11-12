"use client";

import { SetPassword } from "@/components/auth/set-password";

export default function ResetPasswordPage() {
  return (
    <SetPassword
      endpoint="/api/v1/auth/password/reset"
      title="Choose a new password"
      intro="Choose a new password for your account. The link works once."
    />
  );
}
