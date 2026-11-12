// /login: Staff and parents · Student (NAVIGATION "Login").
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";
import { LoginForm } from "@/components/auth/login-form";

export default function LoginPage() {
  return (
    <AuthCard title="Welcome back">
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
