// Money is "₦321,000" from whole kobo; dates are "5 Jan 2027" in West Africa Time.
import { expect, test } from "vitest";

import { date, dateTime, money } from "@/lib/format";

test("money shows naira with commas and no kobo when whole", () => {
  expect(money(32_100_000)).toBe("₦321,000");
  expect(money(29_000_000)).toBe("₦290,000");
  expect(money(0)).toBe("₦0");
  expect(money(150)).toBe("₦1.50");
});

test("a plain date is shown as it is, never shifted a day", () => {
  expect(date("2027-01-05")).toBe("5 Jan 2027");
});

test("a moment is shown in West Africa Time", () => {
  // 23:30 UTC on 4 Jan is 00:30 on 5 Jan in Lagos.
  expect(date("2027-01-04T23:30:00Z")).toBe("5 Jan 2027");
  expect(dateTime("2027-01-04T23:30:00Z")).toBe("5 Jan 2027, 00:30");
});
