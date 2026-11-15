import type { CellFile, Indicator, IndicatorKey, Trend, WindowKey } from "./types";
import { displayUnit } from "./types";

const decimalsFor = (...values: number[]) => (Math.max(...values.map(Math.abs)) >= 10 ? 1 : 2);

const MINUS = "\u2212";

// a real minus sign, and no sign on a value that rounds to zero
export function num(x: number, digits: number): string {
  const text = Math.abs(x).toFixed(digits);
  return x < 0 && Number(text) !== 0 ? `${MINUS}${text}` : text;
}

// hyphens that are minus signs in text built elsewhere
export const minusSigns = (text: string) => text.replace(/(^|[\s(])-(?=\d)/g, `$1${MINUS}`);

export function signed(x: number, digits = decimalsFor(x)): string {
  const text = num(x, digits);
  return x > 0 && Number(text) !== 0 ? `+${text}` : text;
}

export function range(low: number, high: number, digits = decimalsFor(low, high)): string {
  return `(${num(low, digits)} to ${num(high, digits)})`;
}

// "days after 1 Oct" per decade reads as days per decade
export const rateUnit = (unit: string) => `${displayUnit(unit).replace(/ after .*$/, "")} per decade`;

export function rate(trend: Pick<Trend, "slope_per_decade" | "ci_low_per_decade" | "ci_high_per_decade">, unit: string) {
  const digits = decimalsFor(trend.slope_per_decade, trend.ci_low_per_decade, trend.ci_high_per_decade);
  return {
    figure: signed(trend.slope_per_decade, digits),
    unit: rateUnit(unit),
    range: range(trend.ci_low_per_decade, trend.ci_high_per_decade, digits),
  };
}

export const rateText = (trend: Trend, unit: string) => {
  const r = rate(trend, unit);
  return `${r.figure} ${r.unit} ${r.range}`;
};

// three decimals, more when rounding would put the value on the other side of alpha
function probability(name: string, p: number, alpha: number): string {
  if (p < 0.001) return `${name} < 0.001`;
  let digits = 3;
  while (digits < 6 && Number(p.toFixed(digits)) < alpha !== p < alpha) digits++;
  return `${name} = ${p.toFixed(digits)}`;
}

export const pValue = (p: number, alpha = 0.05) => probability("p", p, alpha);
export const qValue = (q: number, alpha = 0.05) => probability("q", q, alpha);

export function significance(trend: Pick<Trend, "mk_p" | "significant" | "alpha">): string {
  const p = pValue(trend.mk_p, trend.alpha);
  return trend.significant ? `Yes, ${p}` : `No, not statistically significant, ${p}`;
}

export const AUTOCORRELATION_NOTE = "This series is autocorrelated, so the p-value may be too small.";
export const NOT_ENOUGH_SEASONS = "Not enough seasons to test (need at least 10)";

export function reading(value: number, unit: string): string {
  const digits = Number.isInteger(value) || Math.abs(value) >= 100 ? 0 : 1;
  return `${num(value, digits)} ${displayUnit(unit)}`;
}

export const shortSource = (source: string) => source.split(/ daily| \(|:/)[0].trim();

export function seasonCount(indicator: Indicator): number {
  return indicator.series.filter((s) => s.value !== null).length;
}

export function descriptor(cell: Pick<CellFile, "source" | "indicators">, key: IndicatorKey): string {
  const n = seasonCount(cell.indicators[key]);
  return `${shortSource(cell.source)}, ${n} ${n === 1 ? "season" : "seasons"}`;
}

export function agreement(trend: Trend | null, second: Trend | null): string | null {
  if (!trend || !second) return null;
  return trend.direction === second.direction
    ? "Both sources agree on direction."
    : "The sources disagree; treat this trend with caution.";
}

const significantWord = (t: Trend) => (t.significant ? "significant" : "not statistically significant");

// what the full record and a recent window each say, from the cell file
export function recordLimit(indicator: Indicator, windowKey: WindowKey = "20"): string | null {
  const all = indicator.trend;
  const recent = indicator.windows[windowKey];
  if (!all || !recent) return null;
  const unit = rateUnit(indicator.unit);
  const head =
    `All ${all.n} seasons give ${signed(all.slope_per_decade)} ${unit} (${pValue(all.mk_p, all.alpha)}, ${significantWord(all)}); ` +
    `the last ${recent.n} alone give ${signed(recent.slope_per_decade)} (${pValue(recent.mk_p, recent.alpha)}, ${significantWord(recent)}).`;
  if (all.significant && !recent.significant)
    return `${head} This record cannot say whether the change continues at the same rate.`;
  if (!all.significant && recent.significant)
    return `${head} A recent change may be starting, but the full record does not confirm it.`;
  return head;
}
