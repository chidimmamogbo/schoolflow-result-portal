// Shared pieces: badges always show a word with the icon; tables become cards
// on phones and show an empty state; a reason dialog will not confirm without one.
import "@/test/setup";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { DataTable } from "@/components/ui/data-table";
import { ReasonDialog } from "@/components/ui/dialog";
import { StatusBadge } from "@/components/ui/status-badge";

test("a status badge shows its word, never colour alone", () => {
  render(<StatusBadge status="returned_for_correction" />);
  expect(screen.getByText("Returned for correction")).toBeInTheDocument();
});

test("an unknown status still shows readable words", () => {
  render(<StatusBadge status="something_new" />);
  expect(screen.getByText("something new")).toBeInTheDocument();
});

type Row = { id: string; name: string; total: number };

test("a table shows rows as a table and as phone cards", () => {
  const rows: Row[] = [{ id: "1", name: "Chukwuemeka Obi", total: 78 }];
  render(
    <DataTable
      rows={rows}
      rowKey={(r) => r.id}
      caption="Scores"
      empty="No scores yet."
      columns={[
        { key: "name", header: "Student", cell: (r) => r.name },
        { key: "total", header: "Total", cell: (r) => r.total, numeric: true },
      ]}
    />,
  );
  expect(screen.getByRole("table", { name: "Scores" })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Scores" })).toBeInTheDocument();
  expect(screen.getAllByText("Chukwuemeka Obi")).toHaveLength(2);
});

test("an empty table shows its empty message", () => {
  render(
    <DataTable<Row>
      rows={[]}
      rowKey={(r) => r.id}
      caption="Scores"
      empty="No scores yet."
      columns={[]}
    />,
  );
  expect(screen.getByText("No scores yet.")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

test("a reason dialog needs a reason before it confirms", async () => {
  const onConfirm = vi.fn();
  render(
    <ReasonDialog
      open
      onOpenChange={() => {}}
      title="Return sheet"
      confirmLabel="Return"
      onConfirm={onConfirm}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Return" }));
  expect(onConfirm).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent("Give a reason.");
  await userEvent.type(
    screen.getByLabelText("Reason (required)"),
    "  CA2 looks wrong  ",
  );
  await userEvent.click(screen.getByRole("button", { name: "Return" }));
  expect(onConfirm).toHaveBeenCalledWith("CA2 looks wrong");
});
