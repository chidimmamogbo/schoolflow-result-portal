"use client";

// The public verification result (F15, D-072): VALID, SUPERSEDED or REVOKED in
// its status colour, the masked name, never a score.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { AuthCard } from "@/components/auth/auth-card";
import { LoadingState } from "@/components/ui/layout";
import { ApiError, api, ok } from "@/lib/api/client";
import { date } from "@/lib/format";
import { cn } from "@/lib/utils";

const WORDS = {
  valid: {
    word: "VALID",
    tone: "text-success-ink",
    note: "This report card is genuine and current.",
  },
  superseded: {
    word: "SUPERSEDED",
    tone: "text-warning-ink",
    note: "This report card was replaced by a newer version.",
  },
  revoked: {
    word: "REVOKED",
    tone: "text-danger",
    note: "The school has withdrawn this report card.",
  },
} as const;

export default function VerifyResultPage() {
  const { code } = useParams<{ code: string }>();
  const raw = decodeURIComponent(code);
  const { data, error, isPending } = useQuery({
    queryKey: ["verify", raw],
    queryFn: () =>
      ok(api.GET("/api/v1/verify/{code}", { params: { path: { code: raw } } })),
  });

  let body;
  if (isPending) body = <LoadingState label="Checking" />;
  else if (error || !data) {
    body = (
      <p role="alert">
        {error instanceof ApiError && error.status === 429
          ? "Too many checks. Wait a minute and try again."
          : "We couldn't find a report card with that code. Check the code and try again."}
      </p>
    );
  } else {
    const look = WORDS[data.status];
    body = (
      <div className="flex flex-col gap-4">
        <p className={cn("text-4xl font-bold tracking-tight", look.tone)}>
          {look.word}
        </p>
        <p>{look.note}</p>
        {data.has_newer_revision && data.newer_revision ? (
          <p className="text-muted">
            A newer version exists (revision {data.newer_revision}
            {data.newer_published_at
              ? `, published ${date(data.newer_published_at)}`
              : ""}
            ).
          </p>
        ) : null}
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted">School</dt>
          <dd>{data.school}</dd>
          <dt className="text-muted">Student</dt>
          <dd>{data.student}</dd>
          <dt className="text-muted">Term</dt>
          <dd>
            {data.term} {data.session}
          </dd>
          <dt className="text-muted">Report ID</dt>
          <dd className="break-all">{data.report_id}</dd>
          <dt className="text-muted">Revision</dt>
          <dd>{data.revision}</dd>
          {data.published_at ? (
            <>
              <dt className="text-muted">Published</dt>
              <dd>{date(data.published_at)}</dd>
            </>
          ) : null}
        </dl>
      </div>
    );
  }
  return (
    <AuthCard title="Verify a report card">
      {body}
      <Link
        href="/verify"
        className="mt-6 inline-block font-medium text-primary hover:underline"
      >
        Check another code
      </Link>
    </AuthCard>
  );
}
