import { NOT_ENOUGH_SEASONS } from "@/lib/trends/format";
import type { Trend } from "@/lib/trends/types";

export const TREND_FILE_FAILED = "The trend file for this cell could not be loaded.";

// undefined means the cell file is not on screen because it failed to load
export function calendarLine(trend: Trend | null | undefined): string {
  if (trend === undefined) return TREND_FILE_FAILED;
  if (trend === null) return NOT_ENOUGH_SEASONS;
  if (!trend.significant || trend.direction === "flat") return "No significant shift in the start of the rains: keep the calendar.";
  const days = Math.abs(trend.slope_per_decade).toFixed(1);
  const way = trend.slope_per_decade > 0 ? "later" : "earlier";
  return `The start of the rains is moving ${days} days per decade ${way}: review the pre-positioning date.`;
}
