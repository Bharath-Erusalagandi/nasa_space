import type { SeasonValue, Trend, WindowChoice } from "./types";

export type Point = { season: number; value: number };
export type Span = { first: number; last: number };
export type Scale = ((v: number) => number) & { domain: [number, number]; range: [number, number] };
export type Dot = Point & { label: string; inWindow: boolean };

export function linear(domain: [number, number], range: [number, number]): Scale {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
  return Object.assign((v: number) => r0 + (v - d0) * k, { domain, range });
}

function niceStep(span: number, count: number): number {
  const raw = span / Math.max(1, count);
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * power;
}

const clean = (v: number) => Number(v.toPrecision(12));

// padded out to whole tick steps so the dots never touch the frame and the ends carry labels
export function valueAxis(series: SeasonValue[], count = 4): { domain: [number, number]; ticks: number[] } {
  const values = series.map((s) => s.value).filter((v): v is number => v !== null);
  if (!values.length) return { domain: [0, 1], ticks: [0, 1] };
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) [min, max] = [min - 1, max + 1];
  const step = niceStep(max - min, count);
  const low = Math.floor(min / step);
  const high = Math.ceil(max / step);
  const ticks = Array.from({ length: high - low + 1 }, (_, i) => clean((low + i) * step));
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks };
}

export function seasonLabel(season: number): string {
  return `${season}/${String((season + 1) % 100).padStart(2, "0")}`;
}

export function fullSpan(series: SeasonValue[]): Span | null {
  if (!series.length) return null;
  const seasons = series.map((s) => s.season);
  return { first: Math.min(...seasons), last: Math.max(...seasons) };
}

// a window is the last N seasons of the record, as the engine computes it
export function seasonsUsed(series: SeasonValue[], window: WindowChoice): Span | null {
  const used = window === "all" ? series : series.slice(-Number(window));
  if (window !== "all" && series.length < Number(window)) return null;
  return fullSpan(used);
}

export function seasonStep(widthPx: number, span: Span, minGapPx = 58): number {
  const years = Math.max(1, span.last - span.first);
  return (widthPx / years) * 5 >= minGapPx ? 5 : 10;
}

export function seasonTicks(span: Span, step: number): number[] {
  const ticks: number[] = [];
  for (let s = Math.ceil(span.first / step) * step; s <= span.last; s += step) ticks.push(s);
  return ticks;
}

export function dots(series: SeasonValue[], used: Span | null): Dot[] {
  return series
    .filter((s): s is SeasonValue & { value: number } => s.value !== null)
    .map((s) => ({
      season: s.season,
      value: s.value,
      label: s.label,
      inWindow: !used || (s.season >= used.first && s.season <= used.last),
    }));
}

export function senEnds(trend: Pick<Trend, "intercept" | "slope_per_year">, span: Span): [Point, Point] {
  const at = (season: number) => ({ season, value: trend.intercept + trend.slope_per_year * season });
  return [at(span.first), at(span.last)];
}

const median = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
};

export function pivot(series: SeasonValue[], span: Span): Point | null {
  const inside = series.filter((s) => s.season >= span.first && s.season <= span.last && s.value !== null);
  if (!inside.length) return null;
  return { season: median(inside.map((s) => s.season)), value: median(inside.map((s) => s.value as number)) };
}

// the 95% slope range drawn as two lines through the median season and median value
export function rangeEnds(
  trend: Pick<Trend, "ci_low_per_decade" | "ci_high_per_decade">,
  through: Point,
  span: Span,
): { low: [Point, Point]; high: [Point, Point] } {
  const line = (perDecade: number): [Point, Point] => {
    const at = (season: number) => ({ season, value: through.value + (perDecade / 10) * (season - through.season) });
    return [at(span.first), at(span.last)];
  };
  return { low: line(trend.ci_low_per_decade), high: line(trend.ci_high_per_decade) };
}

export function pathD(points: Point[], x: (season: number) => number, y: (value: number) => number): string {
  return points.map((p, i) => `${i ? "L" : "M"}${x(p.season).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
}
