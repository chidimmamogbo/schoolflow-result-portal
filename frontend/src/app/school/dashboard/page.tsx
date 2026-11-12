"use client";

// The principal's dashboard (DashboardV5, D-179): what is blocking release.
import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date, money } from "@/lib/format";

function Tile({
  label,
  value,
  of,
  sub,
}: {
  label: string;
  value: number;
  of?: number;
  sub?: string;
}) {
  return (
    <Card className="flex flex-col gap-1">
      <span className="text-sm text-muted">{label}</span>
      <span className="tabular text-3xl font-bold">
        {value}
        {of !== undefined ? (
          <span className="text-base font-medium text-muted">{` of ${of}`}</span>
        ) : null}
      </span>
      {sub ? <span className="text-sm text-muted">{sub}</span> : null}
    </Card>
  );
}

export default function SchoolDashboardPage() {
  const { data, isPending, isError, refetch } = useApi(
    ["dashboard", "school"],
    () => ok(api.GET("/api/v1/dashboard/school")),
  );
  const remind = useAction(
    (audience: "form_teachers" | "teachers") =>
      ok(api.POST("/api/v1/dashboard/reminders", { body: { audience } })),
    {
      done: (r) =>
        r.reminded
          ? `Reminder sent to ${r.reminded}.`
          : "Nobody needed a reminder.",
    },
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the dashboard" onRetry={() => void refetch()} />;
  const r = data.results;
  const billing = data.billing;
  return (
    <>
      <PageHeader
        title="What is blocking release?"
        caption={data.term ? `${data.term} · results week` : undefined}
        actions={
          r && r.sheets.awaiting_approval ? (
            <Link
              className={buttonVariants({ variant: "primary" })}
              href="/school/approvals"
            >{`Review ${r.sheets.awaiting_approval} approvals`}</Link>
          ) : null
        }
      />
      {!r ? (
        <EmptyState
          title="Nothing is blocking release."
          body={
            data.term ? undefined : "Activate a term in School setup to start."
          }
          action={
            <Link
              className={buttonVariants({ variant: "secondary" })}
              href="/school/setup"
            >
              Open school setup
            </Link>
          }
        />
      ) : r.nothing_started ? (
        <EmptyState
          title="Nothing is blocking release."
          body="No score sheets have been started this term. Once teachers start entering scores, anything that holds up results shows here."
          action={
            <Link
              className={buttonVariants({ variant: "secondary" })}
              href="/school/setup"
            >
              Open school setup
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6">
          <section
            aria-label="Sheet pipeline"
            className="grid grid-cols-2 gap-3 lg:grid-cols-4"
          >
            <Tile
              label="Awaiting submission"
              value={r.sheets.awaiting_submission}
              sub="sheets still in draft"
            />
            <Tile label="Awaiting review" value={r.sheets.awaiting_review} />
            <Tile
              label="Awaiting your approval"
              value={r.sheets.awaiting_approval}
            />
            <Tile
              label="Approved"
              value={r.sheets.approved + r.sheets.published}
              of={r.sheets.total}
            />
          </section>
          <Card>
            <h2 className="mb-3 text-xl font-semibold">Needs attention</h2>
            <ul className="grid gap-3">
              {r.missing_scores.count ? (
                <li>
                  <StatusBadge status="draft" className="mr-2" />
                  {`${r.missing_scores.count} missing scores`}{" "}
                  <span className="text-muted">{`Across ${r.missing_scores.sheets?.length ?? 0} sheets`}</span>{" "}
                  <Button size="sm" onClick={() => remind.mutate("teachers")}>
                    Remind teachers
                  </Button>
                </li>
              ) : null}
              {r.missing_ratings.count ? (
                <li>{`${r.missing_ratings.count} skills not rated yet`}</li>
              ) : null}
              {r.invalid_scores.count ? (
                <li className="text-danger">{`${r.invalid_scores.count} invalid scores`}</li>
              ) : null}
              {r.open_sections.length ? (
                <li>
                  {`${r.open_sections.length} form teacher sections still open`}{" "}
                  <span className="text-muted">
                    {r.open_sections.join(", ")}
                  </span>{" "}
                  <Button
                    size="sm"
                    onClick={() => remind.mutate("form_teachers")}
                  >
                    Remind form teachers
                  </Button>
                </li>
              ) : null}
              {data.corrections_open ? (
                <li>
                  {`${data.corrections_open} open corrections`}{" "}
                  <Link
                    className="text-primary underline"
                    href="/school/corrections"
                  >
                    Investigate
                  </Link>
                </li>
              ) : null}
              {r.unusual_changes.map((c) => (
                <li key={`${c.sheet_id}-${c.student_name}-${c.column}`}>
                  {`${c.student_name}, ${c.subject} ${c.column}: ${c.old} to ${c.new}. Reason given.`}{" "}
                  <Link className="text-primary underline" href="/school/audit">
                    See audit trail
                  </Link>
                </li>
              ))}
              {!r.missing_scores.count &&
              !r.invalid_scores.count &&
              !r.open_sections.length &&
              !data.corrections_open &&
              !r.unusual_changes.length ? (
                <li>Nothing is blocking release.</li>
              ) : null}
            </ul>
          </Card>
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Sheets by class</h2>
              <Link className="text-primary underline" href="/school/approvals">
                Open approvals
              </Link>
            </div>
            <DataTable
              caption="Sheets by class"
              rows={r.classes}
              rowKey={(c) => c.class_name}
              empty="No classes yet."
              columns={[
                { key: "class", header: "Class", cell: (c) => c.class_name },
                {
                  key: "draft",
                  header: "Draft",
                  numeric: true,
                  cell: (c) => c.awaiting_submission,
                },
                {
                  key: "review",
                  header: "In review",
                  numeric: true,
                  cell: (c) => c.awaiting_review,
                },
                {
                  key: "wait",
                  header: "Awaiting approval",
                  numeric: true,
                  cell: (c) => c.awaiting_approval,
                },
                {
                  key: "ok",
                  header: "Approved",
                  numeric: true,
                  cell: (c) => c.approved + c.published,
                },
                {
                  key: "progress",
                  header: "Progress",
                  numeric: true,
                  cell: (c) => `${c.approved + c.published}/${c.total}`,
                },
              ]}
            />
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            {r.attention ? (
              <Card>
                <h2 className="mb-1 text-xl font-semibold">
                  Students needing attention
                </h2>
                <p className="tabular text-3xl font-bold">
                  {r.attention.subject_results + r.attention.skills}
                </p>
                <p>{`${r.attention.subject_results} subject results below ${r.attention.pass_mark}% in ${r.attention.term}`}</p>
                <Link
                  className="text-primary underline"
                  href="/school/attention"
                >
                  View list
                </Link>
              </Card>
            ) : null}
            {r.stats.average ? (
              <Card>
                <h2 className="mb-1 text-xl font-semibold">Results so far</h2>
                <p>{`Pass rate ${r.stats.pass_rate}% · Average ${r.stats.average}`}</p>
                <p className="text-sm text-muted">{`From the ${r.stats.sheets_counted} approved sheets only.`}</p>
              </Card>
            ) : null}
            {billing.billing_enabled ? (
              <Card>
                <h2 className="mb-1 text-xl font-semibold">Billing</h2>
                <StatusBadge status={billing.status} />
                {billing.amount_due_kobo ? (
                  <p className="tabular mt-2 text-2xl font-bold">
                    {money(billing.amount_due_kobo)}
                  </p>
                ) : null}
                {billing.plan ? (
                  <p>{`${billing.plan} plan · ${billing.billable_students ?? 0} students`}</p>
                ) : null}
                {billing.due_on ? (
                  <p className="text-muted">{`Due ${date(billing.due_on)}`}</p>
                ) : null}
                <Link className="text-primary underline" href="/school/billing">
                  Open billing
                </Link>
              </Card>
            ) : null}
          </div>
        </div>
      )}
    </>
  );
}
