// The product landing page (public). No sign-up anywhere: schools are set up
// by the platform (non-negotiable).
import { ShieldCheck } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-6 px-4 py-16 text-center">
      <ShieldCheck className="size-12 text-primary" aria-hidden="true" />
      <h1 className="text-3xl font-bold md:text-4xl">
        SchoolFlow Result Portal
      </h1>
      <p className="max-w-xl text-lg text-muted">
        Results your school can trust. Teachers enter scores once, reviewers and
        principals approve, and every published report card can be checked by
        anyone with its code.
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Link href="/login" className={buttonVariants({ variant: "primary" })}>
          Log in
        </Link>
        <Link
          href="/verify"
          className={buttonVariants({ variant: "secondary" })}
        >
          Verify a report card
        </Link>
      </div>
      <Link
        href="/privacy"
        className="text-sm text-muted underline-offset-4 hover:underline"
      >
        Privacy
      </Link>
    </main>
  );
}
