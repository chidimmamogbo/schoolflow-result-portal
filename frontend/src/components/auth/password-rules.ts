// Password rules (D-036, D-134): at least 15 characters, 10 for students, at
// most 128, and not a common password. The server checks them too.
import { ApiError } from "@/lib/api/client";

export function minLength(student: boolean): number {
  return student ? 10 : 15;
}

export function localProblem(
  password: string,
  confirm: string,
  student: boolean,
): string | null {
  if (password.length < minLength(student))
    return `Use at least ${minLength(student)} characters.`;
  if (password.length > 128) return "Use at most 128 characters.";
  if (password !== confirm) return "The passwords don't match.";
  return null;
}

export const LINK_INVALID =
  "This link has expired or was already used. Ask your school for a new one.";

export function serverProblem(error: unknown, student: boolean): string {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "password_too_short":
        return `Use at least ${minLength(student)} characters.`;
      case "password_too_long":
        return "Use at most 128 characters.";
      case "password_too_common":
        return "That password is too common. Choose another.";
      case "password_unchanged":
        return "Choose a password different from your current one.";
      case "current_password_wrong":
        return "Your current password is not right.";
      case "link_invalid":
        return LINK_INVALID;
      case "email_has_account":
        return "This email already has an account. Log in to accept the link.";
    }
  }
  return "Something went wrong. Try again.";
}
