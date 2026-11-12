"use client";

import { SetPassword } from "@/components/auth/set-password";

export default function ActivatePage() {
  return (
    <SetPassword
      endpoint="/api/v1/auth/activate"
      title="Activate your account"
      intro="Welcome. Choose a password to finish setting up your account."
    />
  );
}
