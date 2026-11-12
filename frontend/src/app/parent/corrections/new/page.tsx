"use client";

// Report a problem on a published result (F12): what looks wrong, in words.
import { useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Suspense, useState } from "react";

import { school } from "@/components/portal/portal";
import { Button } from "@/components/ui/button";
import { Field, FormError, Select, Textarea } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/layout";
import { api, ok } from "@/lib/api/client";
import { useAction } from "@/lib/api/hooks";

function NewCorrection() {
  const router = useRouter();
  const params = useSearchParams();
  const report = params.get("report") ?? "";
  const schoolId = params.get("school");
  const [issue, setIssue] = useState<"score" | "detail" | "other">("score");
  const [explanation, setExplanation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const send = useAction(
    () =>
      ok(
        api.POST("/api/v1/corrections", {
          body: {
            report_id: report,
            issue_type: issue,
            explanation: explanation.trim(),
            subject_id: null,
            learning_area_id: null,
          },
          headers: school(schoolId),
        }),
      ),
    {
      invalidate: [["corrections"]],
      done: "Request sent to the school.",
      onDone: () => router.push("/parent/corrections"),
    },
  );
  function submit(event: FormEvent) {
    event.preventDefault();
    if (!report)
      return setError("Open a report first, then use Report a problem.");
    if (!explanation.trim()) return setError("Say what looks wrong.");
    setError(null);
    send.mutate(undefined);
  }
  return (
    <>
      <PageHeader title="Report a problem" />
      <form
        onSubmit={submit}
        className="grid max-w-[var(--form-max)] gap-4"
        noValidate
      >
        <FormError message={error} />
        <Field label="What is wrong?">
          {(f) => (
            <Select
              {...f}
              value={issue}
              onChange={(e) => setIssue(e.target.value as typeof issue)}
            >
              <option value="score">A score or rating</option>
              <option value="detail">A name or other detail</option>
              <option value="other">Something else</option>
            </Select>
          )}
        </Field>
        <Field label="Explain" hint="Say which subject and what you expected.">
          {(f) => (
            <Textarea
              {...f}
              rows={5}
              maxLength={1000}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
            />
          )}
        </Field>
        <div>
          <Button type="submit" variant="primary" busy={send.isPending}>
            Send request
          </Button>
        </div>
      </form>
    </>
  );
}

export default function Page() {
  return (
    <Suspense>
      <NewCorrection />
    </Suspense>
  );
}
