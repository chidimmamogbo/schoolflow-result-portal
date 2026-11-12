"use client";

// The score grid (design "Score grid"): one row per student, a cell per column,
// errors before embarrassment: a value above the column's maximum is caught here
// and by the server. Scores use tabular figures, 16px at least.
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/form";
import type { Schemas } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Sheet = Schemas["SheetView"];
export type Edits = Record<string, string>; // "enrolment:component" -> typed text

export function cellKey(enrolment: string, component: string): string {
  return `${enrolment}:${component}`;
}

export function cellProblem(text: string, max: number): string | null {
  if (text.trim() === "") return null;
  if (!/^\d+$/.test(text.trim())) return "Whole numbers only.";
  return Number(text) > max ? `Can't be more than ${max}.` : null;
}

export function ScoreGrid({
  sheet,
  edits,
  onEdit,
  readOnly,
}: {
  sheet: Sheet;
  edits: Edits;
  onEdit: (key: string, value: string) => void;
  readOnly?: boolean;
}) {
  const [search, setSearch] = useState("");
  const rows = useMemo(() => {
    const text = search.trim().toLowerCase();
    return sheet.rows.filter(
      (r) =>
        !text ||
        `${r.first_name} ${r.surname} ${r.admission_number}`
          .toLowerCase()
          .includes(text),
    );
  }, [sheet.rows, search]);
  return (
    <div className="grid gap-3">
      <Input
        aria-label="Find a student"
        placeholder="Find a student"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">{`${sheet.subject_name}, ${sheet.class_name}`}</caption>
          <thead className="bg-surface-2 text-sm">
            <tr>
              <th scope="col" className="sticky left-0 bg-surface-2 px-3 py-2">
                Student
              </th>
              {sheet.columns.map((c) => (
                <th
                  key={c.id}
                  scope="col"
                  className="px-2 py-2 text-right"
                >{`${c.label} /${c.max_score}`}</th>
              ))}
              <th scope="col" className="px-3 py-2 text-right">
                Total
              </th>
              <th scope="col" className="px-3 py-2">
                Grade
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.enrolment_id} className="border-t border-border">
                <th
                  scope="row"
                  className="sticky left-0 bg-surface px-3 py-2 text-sm font-medium"
                >
                  {`${row.first_name} ${row.surname}`}
                  <span className="block text-xs text-muted">
                    {row.admission_number}
                  </span>
                </th>
                {sheet.columns.map((c) => {
                  const key = cellKey(row.enrolment_id, c.id);
                  const text =
                    edits[key] ??
                    (row.scores[c.id] !== undefined
                      ? String(row.scores[c.id])
                      : "");
                  const problem = cellProblem(text, c.max_score);
                  return (
                    <td key={c.id} className="px-1 py-1 text-right">
                      <input
                        aria-label={`${c.label} for ${row.first_name} ${row.surname}`}
                        aria-invalid={Boolean(problem)}
                        title={problem ?? undefined}
                        inputMode="numeric"
                        disabled={readOnly}
                        value={text}
                        onChange={(e) => onEdit(key, e.target.value)}
                        className={cn(
                          "tabular min-h-11 w-16 rounded-sm border border-border-strong bg-surface px-2 text-right text-base disabled:bg-surface-2",
                          problem && "border-danger bg-danger-soft",
                        )}
                      />
                    </td>
                  );
                })}
                <td className="tabular px-3 text-right">{row.total ?? ""}</td>
                <td className="px-3">{row.grade ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length ? (
        <p>
          {sheet.rows.length
            ? `No student matches "${search}".`
            : `No students in ${sheet.class_name} yet.`}
        </p>
      ) : null}
    </div>
  );
}
