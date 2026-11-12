"use client";

// Parents and guardians, with their linked children and login state (D-138, D-140).
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { useGuardians } from "@/lib/api/school";

const LOGIN: Record<string, string> = {
  none: "No login",
  waiting: "Link request sent",
  linked: "Linked",
  paused: "Paused",
};

export default function ParentsPage() {
  const { data, isPending, isError, refetch } = useGuardians();
  return (
    <>
      <PageHeader
        title="Parents"
        actions={
          <Link
            href="/school/parents/new"
            className={buttonVariants({ variant: "primary" })}
          >
            Add parent
          </Link>
        }
      />
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="parents" onRetry={() => void refetch()} />
      ) : (
        <DataTable
          caption="Parents"
          rows={data}
          rowKey={(g) => g.id}
          empty="No parents yet."
          cardTitle={(g) => (
            <Link
              className="text-primary hover:underline"
              href={`/school/parents/${g.id}`}
            >
              {g.full_name}
            </Link>
          )}
          columns={[
            {
              key: "name",
              header: "Name",
              hideOnCard: true,
              cell: (g) => (
                <Link
                  className="font-medium text-primary hover:underline"
                  href={`/school/parents/${g.id}`}
                >
                  {g.full_name}
                </Link>
              ),
            },
            {
              key: "children",
              header: "Children",
              cell: (g) =>
                g.wards.map((w) => `${w.name} (${w.relationship})`).join(", "),
            },
            {
              key: "contact",
              header: "Contact",
              cell: (g) =>
                [g.phone, g.email].filter(Boolean).join(" · ") || "None",
            },
            {
              key: "login",
              header: "Login",
              cell: (g) => LOGIN[g.login_status],
            },
          ]}
        />
      )}
    </>
  );
}
