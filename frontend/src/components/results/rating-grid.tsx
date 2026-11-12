"use client";

// The rating sheet (NAVIGATION "Rating sheet"): code buttons per skill, the
// chosen one shows its word; no totals or averages ever (non-negotiable).
import type { Schemas } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Sheet = Schemas["RatingSheetView"];
export type RatingEdits = Record<string, string | null>; // "enrolment:skill" -> point id

export function RatingGrid({
  sheet,
  edits,
  onEdit,
  readOnly,
}: {
  sheet: Sheet;
  edits: RatingEdits;
  onEdit: (key: string, point: string | null) => void;
  readOnly?: boolean;
}) {
  return (
    <div className="grid gap-4">
      {sheet.rows.map((row) => (
        <section
          key={row.enrolment_id}
          className="rounded-lg border border-border bg-surface p-4"
          aria-label={`${row.first_name} ${row.surname}`}
        >
          <h3 className="mb-2 font-semibold">{`${row.first_name} ${row.surname}`}</h3>
          <div className="grid gap-3">
            {sheet.skills.map((skill) => {
              const key = `${row.enrolment_id}:${skill.id}`;
              const chosen =
                key in edits ? edits[key] : (row.ratings[skill.id] ?? null);
              return (
                <fieldset key={skill.id} className="grid gap-1">
                  <legend className="text-sm">{skill.name}</legend>
                  <div className="flex flex-wrap gap-1">
                    {sheet.scale.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        disabled={readOnly}
                        aria-pressed={chosen === p.id}
                        aria-label={`${p.name} for ${skill.name}`}
                        onClick={() =>
                          onEdit(key, chosen === p.id ? null : p.id)
                        }
                        className={cn(
                          "min-h-11 min-w-11 rounded-md border border-border-strong px-2 text-sm font-semibold",
                          chosen === p.id &&
                            "border-primary bg-primary text-on-primary",
                        )}
                      >
                        {chosen === p.id ? p.name : p.code}
                      </button>
                    ))}
                  </div>
                </fieldset>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
