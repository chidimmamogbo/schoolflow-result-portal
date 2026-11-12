// The landing page carries the product name as its one main heading, and the
// browser tab title is the product name. No sign-up link anywhere.
import "@/test/setup";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { metadata } from "@/app/layout";
import Home from "@/app/page";

afterEach(cleanup);

test("home page shows the product name as its only main heading, and no sign-up", () => {
  render(<Home />);

  const headings = screen.getAllByRole("heading", { level: 1 });
  expect(headings).toHaveLength(1);
  expect(headings[0]?.textContent).toBe("SchoolFlow Result Portal");
  expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(screen.queryByText(/sign up|register/i)).not.toBeInTheDocument();
});

test("browser tab title is the product name, not the starter text", () => {
  expect(metadata.title).toBe("SchoolFlow Result Portal");
});
