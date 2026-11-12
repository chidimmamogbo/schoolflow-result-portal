// ResponsiveTable: a real table from tablet width up, and a stack of cards on
// phones, so a page never scrolls sideways at 320px (design "Layout").
import type { ReactNode } from "react";

import { EmptyState } from "@/components/ui/layout";
import { cn } from "@/lib/utils";

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  numeric?: boolean;
  // Hidden from the phone card when it only repeats the card title.
  hideOnCard?: boolean;
};

type Props<T> = {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  caption: string;
  empty: string;
  emptyBody?: string;
  cardTitle?: (row: T) => ReactNode;
};

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  caption,
  empty,
  emptyBody,
  cardTitle,
}: Props<T>) {
  if (rows.length === 0) return <EmptyState title={empty} body={emptyBody} />;
  return (
    <>
      <div className="hidden overflow-x-auto rounded-lg border border-border bg-surface md:block">
        <table className="w-full border-collapse text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-surface-2">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={cn(
                    "px-4 py-3 font-semibold",
                    column.numeric && "text-right",
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className="border-t border-border hover:bg-surface-2"
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "px-4 py-3",
                      column.numeric && "tabular text-right",
                    )}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col gap-3 md:hidden" aria-label={caption}>
        {rows.map((row) => (
          <li
            key={rowKey(row)}
            className="rounded-lg border border-border bg-surface p-4"
          >
            {cardTitle ? (
              <div className="mb-2 font-semibold">{cardTitle(row)}</div>
            ) : null}
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              {columns
                .filter((column) => !column.hideOnCard)
                .map((column) => (
                  <div key={column.key} className="contents">
                    <dt className="text-muted">{column.header}</dt>
                    <dd
                      className={cn(
                        "min-w-0 break-words",
                        column.numeric && "tabular",
                      )}
                    >
                      {column.cell(row)}
                    </dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}
