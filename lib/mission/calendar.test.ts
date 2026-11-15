import { describe, expect, test } from "vitest";
import { trend } from "@/lib/trends/__fixtures__/trends";
import { calendarLine } from "./calendar";

describe("calendar line", () => {
  test("a significant later start asks to review the date", () => {
    expect(calendarLine(trend(2.86, 0.01))).toBe("The start of the rains is moving 2.9 days per decade later: review the pre-positioning date.");
  });

  test("a significant earlier start", () => {
    expect(calendarLine(trend(-4, 0.002))).toBe("The start of the rains is moving 4.0 days per decade earlier: review the pre-positioning date.");
  });

  test("not significant keeps the calendar", () => {
    expect(calendarLine(trend(2.86, 0.232))).toBe("No significant shift in the start of the rains: keep the calendar.");
  });

  test("no trend says there are not enough seasons", () => {
    expect(calendarLine(null)).toBe("Not enough seasons to test (need at least 10)");
  });

  test("a trend file that did not load says so and claims nothing about seasons", () => {
    expect(calendarLine(undefined)).toBe("The trend file for this cell could not be loaded.");
  });
});
