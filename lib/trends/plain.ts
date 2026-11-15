import { changeWords, rateUnit } from "./cellLayer";
import { num } from "./format";
import type { IndicatorKey, Trend } from "./types";

const decimals = (x: number) => (Math.abs(x) >= 10 ? 0 : Math.abs(x) >= 1 ? 1 : 2);

// one sentence a reader with no statistics can follow: which way, how fast, and whether to believe it
export function plainVerdict(key: IndicatorKey, label: string, trend: Trend | null | undefined, placeName: string): string | null {
  if (!trend) return null;
  const where = placeName ? ` around ${placeName}` : "";
  const over = `over ${trend.n} seasons`;
  if (trend.direction === "flat") return `${label}${where} shows no change ${over}.`;
  const size = Math.abs(trend.slope_per_decade);
  const amount = `about ${num(size, decimals(size))} ${rateUnit(key)} per decade`;
  const head = `The data points to ${changeWords(key, trend.direction)}${where}, by ${amount} ${over}.`;
  return trend.significant
    ? `${head} A change this steady is unlikely to be chance, so it counts as a trend.`
    : `${head} That is small next to the swings from one year to the next, so it does not count as a trend yet.`;
}
