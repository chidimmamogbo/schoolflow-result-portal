// Tests for the banner that marks staging (D-121). Wording approved by
// Chidimma on 2026-10-12: "Staging site: test data only".
// It must never appear in production, or when the environment is unknown.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { StagingBanner } from "@/components/staging-banner";

afterEach(cleanup);

const BANNER_TEXT = "Staging site: test data only";

test("staging shows the banner with its approved wording", () => {
  render(<StagingBanner appEnv="staging" />);

  const banner = screen.getByRole("note");
  expect(banner.textContent).toBe(BANNER_TEXT);
});

test("the banner has an icon, so the warning is not colour alone", () => {
  render(<StagingBanner appEnv="staging" />);

  const icon = screen.getByRole("note").querySelector("svg");
  expect(icon).not.toBeNull();
  // Decorative: the words already say it, so screen readers skip the icon.
  expect(icon?.getAttribute("aria-hidden")).toBe("true");
});

test("production never shows the banner", () => {
  render(<StagingBanner appEnv="production" />);

  expect(screen.queryByText(BANNER_TEXT)).toBeNull();
});

test("an unset or unknown environment does not show the banner", () => {
  const { rerender } = render(<StagingBanner appEnv={undefined} />);
  expect(screen.queryByText(BANNER_TEXT)).toBeNull();

  rerender(<StagingBanner appEnv="local" />);
  expect(screen.queryByText(BANNER_TEXT)).toBeNull();
});
