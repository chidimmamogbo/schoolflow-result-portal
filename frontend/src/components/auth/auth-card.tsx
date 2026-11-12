// The frame of every page before login: a centred card on the page background,
// with the product name (or the school's name and logo on a school link).
import Link from "next/link";
import type { ReactNode } from "react";

export function AuthCard({
  title,
  intro,
  brand,
  children,
}: {
  title: string;
  intro?: ReactNode;
  brand?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-10">
      {brand ?? (
        <Link href="/" className="text-lg font-bold text-text">
          SchoolFlow Result Portal
        </Link>
      )}
      <section className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-sm md:p-8">
        <h1 className="mb-2 text-2xl font-bold">{title}</h1>
        {intro ? <div className="mb-6 text-muted">{intro}</div> : null}
        {children}
      </section>
    </main>
  );
}
