"use client";

// Profile: who you are, and the two account actions from the header menu.
import Link from "next/link";
import { useRouter } from "next/navigation";

import { roleLabel } from "@/components/shell/nav";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/layout";
import { useLogout, useMe } from "@/lib/auth";

export default function ProfilePage() {
  const { data: me } = useMe();
  const logout = useLogout();
  const router = useRouter();
  if (!me) return null;
  return (
    <>
      <PageHeader title="Profile" />
      <Card className="flex max-w-xl flex-col gap-4">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
          <dt className="text-muted">Name</dt>
          <dd>{me.user.full_name}</dd>
          <dt className="text-muted">Username</dt>
          <dd>{me.user.username}</dd>
          {me.user.email ? (
            <>
              <dt className="text-muted">Email</dt>
              <dd className="break-all">{me.user.email}</dd>
            </>
          ) : null}
          <dt className="text-muted">Role</dt>
          <dd>{roleLabel(me)}</dd>
          {me.school ? (
            <>
              <dt className="text-muted">School</dt>
              <dd>{me.school.name}</dd>
            </>
          ) : null}
        </dl>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/change-password"
            className={buttonVariants({ variant: "secondary" })}
          >
            Change password
          </Link>
          <Button
            variant="ghost"
            onClick={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            Log out
          </Button>
        </div>
      </Card>
    </>
  );
}
