"use client";

// Students needing attention (F23): published results only, scoped by role on
// the server. Views By subject, By student and (Skill ratings) By learning area.
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { ErrorState, LoadingState, PageHeader } from "@/components/ui/layout";
import { Tabs } from "@/components/ui/tabs";
import { api, ok } from "@/lib/api/client";
import { useApi } from "@/lib/api/hooks";

type View = "by_subject" | "by_student" | "by_learning_area";

function Rows({ view }: { view: View }) {
  const { data, isPending, isError, refetch } = useApi(
    ["attention", view],
    () => ok(api.GET("/api/v1/attention", { params: { query: { view } } })),
  );
  if (isPending) return <LoadingState />;
  if (isError)
    return <ErrorState thing="the list" onRetry={() => void refetch()} />;
  const common = [
    {
      key: "name",
      header: "Student",
      cell: (r: (typeof data.rows)[number]) => r.student_name,
    },
    {
      key: "class",
      header: "Class",
      cell: (r: (typeof data.rows)[number]) => r.class_name,
    },
  ];
  const columns =
    view === "by_subject"
      ? [
          ...common,
          {
            key: "subject",
            header: "Subject",
            cell: (r: (typeof data.rows)[number]) => r.subject,
          },
          {
            key: "score",
            header: "Score",
            numeric: true,
            cell: (r: (typeof data.rows)[number]) => r.score,
          },
          {
            key: "grade",
            header: "Grade",
            cell: (r: (typeof data.rows)[number]) => r.grade,
          },
          {
            key: "teacher",
            header: "Teacher",
            cell: (r: (typeof data.rows)[number]) => r.teacher ?? "",
          },
        ]
      : view === "by_learning_area"
        ? [
            ...common,
            {
              key: "area",
              header: "Learning area",
              cell: (r: (typeof data.rows)[number]) => r.learning_area,
            },
            {
              key: "skill",
              header: "Skill",
              cell: (r: (typeof data.rows)[number]) => r.skill,
            },
            {
              key: "rating",
              header: "Rating",
              cell: (r: (typeof data.rows)[number]) => r.rating,
            },
          ]
        : [
            ...common,
            {
              key: "failed",
              header: "Failed subjects or skills",
              numeric: true,
              cell: (r: (typeof data.rows)[number]) => r.failed_count,
            },
            {
              key: "average",
              header: "Average",
              numeric: true,
              cell: (r: (typeof data.rows)[number]) => r.average ?? "",
            },
            {
              key: "flag",
              header: "",
              cell: (r: (typeof data.rows)[number]) =>
                r.average_below_pass_mark ? (
                  <span className="font-medium text-danger">
                    Average below pass mark
                  </span>
                ) : null,
            },
          ];
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p role="status">
          {`${data.count} results for this selection.`}{" "}
          <span className="text-muted">{`Pass mark ${data.pass_mark}.`}</span>
        </p>
        <a
          className={buttonVariants({ variant: "secondary", size: "sm" })}
          href={`/api/v1/attention/export.csv?view=${view}`}
        >
          Download CSV
        </a>
      </div>
      <DataTable
        caption="Students needing attention"
        rows={data.rows}
        rowKey={(r) => `${r.report_id}-${r.subject ?? r.skill ?? ""}`}
        empty="No students need attention for this selection."
        columns={columns}
      />
    </>
  );
}

export function AttentionView({ skills }: { skills?: boolean }) {
  const [view, setView] = useState<View>("by_subject");
  const tabs = [
    {
      value: "by_subject",
      label: "By subject",
      content: <Rows view="by_subject" />,
    },
    {
      value: "by_student",
      label: "By student",
      content: <Rows view="by_student" />,
    },
    ...(skills
      ? [
          {
            value: "by_learning_area",
            label: "By learning area",
            content: <Rows view="by_learning_area" />,
          },
        ]
      : []),
  ];
  return (
    <>
      <PageHeader title="Students needing attention" />
      <p className="mb-4 text-muted">From published results only.</p>
      <Tabs
        label="View"
        value={view}
        onValueChange={(v) => setView(v as View)}
        tabs={tabs}
      />
    </>
  );
}
