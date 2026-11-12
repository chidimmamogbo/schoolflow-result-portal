"use client";

// The parent and student portal (F14): children grouped by school, each
// school's name and colour; published reports only (the server decides).
// A parent with children in two schools names the school on each request.
import { Download, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui/layout";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError, api, ok } from "@/lib/api/client";
import { useAction, useApi } from "@/lib/api/hooks";
import { date } from "@/lib/format";

export const school = (id: string | null | undefined) =>
  id ? { "X-School-Id": id } : undefined;

export function useChildren() {
  return useApi(["portal", "children"], () =>
    ok(api.GET("/api/v1/me/children")),
  );
}

function LinkRequests() {
  const { data } = useApi(["portal", "link-requests"], () =>
    ok(api.GET("/api/v1/me/link-requests")),
  );
  const accept = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/me/link-requests/{request_id}/accept", {
          params: { path: { request_id: id } },
        }),
      ),
    { invalidate: [["portal"], ["me"]], done: "Linked." },
  );
  const decline = useAction(
    (id: string) =>
      ok(
        api.POST("/api/v1/me/link-requests/{request_id}/decline", {
          params: { path: { request_id: id } },
        }),
      ),
    { invalidate: [["portal"]], done: "Declined." },
  );
  if (!data?.length) return null;
  return (
    <Card className="mb-6 grid gap-3">
      <h2 className="text-xl font-semibold">Link requests</h2>
      {data.map((r) => (
        <div key={r.id} className="flex flex-wrap items-center gap-2">
          <span className="grow">{`${r.school_name} has added you as ${r.guardian_name}.`}</span>
          <Button size="sm" onClick={() => decline.mutate(r.id)}>
            Decline
          </Button>
          <Button
            size="sm"
            variant="primary"
            busy={accept.isPending}
            onClick={() => accept.mutate(r.id)}
          >
            Accept
          </Button>
        </div>
      ))}
    </Card>
  );
}

export function PortalHome({
  base,
  title,
}: {
  base: "/parent" | "/student";
  title: string;
}) {
  const { data, isPending, isError, refetch } = useChildren();
  return (
    <>
      <PageHeader title={title} />
      {base === "/parent" ? <LinkRequests /> : null}
      {isPending ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState thing="your results" onRetry={() => void refetch()} />
      ) : !data.length ? (
        <EmptyState
          title="No children linked yet."
          body="Your school links your children to your account."
        />
      ) : (
        <div className="grid gap-6">
          {data.map((s) => (
            <section key={s.school_id} aria-label={s.school_name}>
              <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold">
                <span
                  aria-hidden="true"
                  className="inline-block size-3 rounded-full"
                  style={{ background: s.colour ?? "var(--primary)" }}
                />
                {s.school_name}
              </h2>
              <div className="grid gap-3 md:grid-cols-2">
                {s.children.map((c) => (
                  <Card key={c.student_id} className="grid gap-2">
                    <p className="font-semibold">{c.name}</p>
                    <p className="text-sm text-muted">{`${c.class_name ?? ""} · ${c.admission_number}`}</p>
                    {c.latest ? (
                      <>
                        <p>
                          {`${c.latest.term} ${c.latest.session}`}
                          {c.latest.average
                            ? ` · Average ${c.latest.average}`
                            : ""}
                          {c.latest.position && c.latest.number_in_class
                            ? ` · Position ${c.latest.position} of ${c.latest.number_in_class}`
                            : ""}
                        </p>
                        <Link
                          className={buttonVariants({ variant: "primary" })}
                          href={`${base}/reports/${c.latest.report_id}?school=${s.school_id}`}
                        >
                          Open report
                        </Link>
                      </>
                    ) : (
                      <p className="text-muted">{`${c.name.split(" ")[0]}'s report is not ready yet.`}</p>
                    )}
                    <Link
                      className="text-primary underline"
                      href={`${base}/children/${c.student_id}?school=${s.school_id}`}
                    >
                      All reports
                    </Link>
                  </Card>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

export function ChildReports({
  base,
  studentId,
  schoolId,
}: {
  base: string;
  studentId: string;
  schoolId: string | null;
}) {
  const { data, isPending, isError, refetch } = useApi(
    ["portal", "reports", studentId],
    () =>
      ok(
        api.GET("/api/v1/me/students/{student_id}/reports", {
          params: { path: { student_id: studentId } },
          headers: school(schoolId),
        }),
      ),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the reports" onRetry={() => void refetch()} />;
  return (
    <>
      <PageHeader title="Reports" />
      {!data.length ? (
        <EmptyState title="No reports yet." />
      ) : (
        <ul className="grid gap-2">
          {data.map((r) => (
            <li key={r.report_id}>
              <Card className="flex flex-wrap items-center gap-3 py-3 md:py-3">
                <span className="grow font-medium">{`${r.term} ${r.session} · ${r.class_name}`}</span>
                <StatusBadge status={r.status} />
                <Link
                  className="text-primary underline"
                  href={`${base}/reports/${r.report_id}?school=${schoolId ?? ""}`}
                >
                  Open
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

async function fetchWithSchool(
  path: string,
  schoolId: string | null,
): Promise<Response> {
  const response = await globalThis.fetch(path, {
    credentials: "same-origin",
    headers: school(schoolId),
  });
  if (!response.ok) throw new ApiError(response.status, null);
  return response;
}

export function ReportPage({
  reportId,
  schoolId,
  base,
}: {
  reportId: string;
  schoolId: string | null;
  base: "/parent" | "/student";
}) {
  const view = useApi(["portal", "report", reportId], () =>
    ok(
      api.GET("/api/v1/me/reports/{report_id}", {
        params: { path: { report_id: reportId } },
        headers: school(schoolId),
      }),
    ),
  );
  const card = useApi(["portal", "card", reportId], async () =>
    (
      await fetchWithSchool(
        `/api/v1/me/reports/${reportId}/card.html`,
        schoolId,
      )
    ).text(),
  );
  const [downloading, setDownloading] = useState(false);
  async function download() {
    setDownloading(true);
    try {
      const blob = await (
        await fetchWithSchool(
          `/api/v1/me/reports/${reportId}/report.pdf`,
          schoolId,
        )
      ).blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${view.data?.report_code ?? "report"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }
  if (view.isPending) return <LoadingState />;
  if (view.isError)
    return (
      <ErrorState thing="the report" onRetry={() => void view.refetch()} />
    );
  const r = view.data;
  return (
    <>
      <PageHeader
        title={`${(r.term as { name?: string }).name ?? "Report"}`}
        caption={`${r.report_code} · revision ${r.revision}${r.published_at ? ` · ${date(r.published_at)}` : ""}`}
        actions={
          <>
            <Button onClick={() => void download()} busy={downloading}>
              <Download aria-hidden="true" />
              Download PDF
            </Button>
            {r.verification_code ? (
              <Link
                className={buttonVariants({ variant: "secondary" })}
                href={`/verify/${r.verification_code}`}
              >
                <ShieldCheck aria-hidden="true" />
                Verify
              </Link>
            ) : null}
          </>
        }
      />
      {r.has_newer_revision ? (
        <p
          role="note"
          className="mb-4 rounded-md bg-warning-soft px-3 py-2 text-warning-ink"
        >
          A newer version of this report exists.
        </p>
      ) : null}
      {card.data ? (
        // The school's own report card HTML, shown without scripts; print is always light.
        <iframe
          title="Report card"
          sandbox=""
          srcDoc={card.data}
          className="h-[80vh] w-full rounded-lg border border-border bg-white"
        />
      ) : card.isError ? (
        <ErrorState
          thing="the report card"
          onRetry={() => void card.refetch()}
        />
      ) : (
        <LoadingState />
      )}
      {base === "/parent" ? (
        <Link
          className="mt-4 inline-block text-primary underline"
          href={`/parent/corrections/new?report=${reportId}&school=${schoolId ?? ""}`}
        >
          Report a problem
        </Link>
      ) : null}
    </>
  );
}
