// Tests for the placeholder home page and the site-wide page title.
// The real home screen is built from the design handoff in Phase 8; until then
// the page only has to prove the app renders and carries the product name.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { metadata } from "@/app/layout";
import Home from "@/app/page";

afterEach(cleanup);

test("home page shows the product name as its only main heading", () => {
  render(<Home />);

  const headings = screen.getAllByRole("heading", { level: 1 });
  expect(headings).toHaveLength(1);
  expect(headings[0]?.textContent).toBe("SchoolFlow Result Portal");
});

test("browser tab title is the product name, not the starter text", () => {
  expect(metadata.title).toBe("SchoolFlow Result Portal");
});
