import type { IndexCell, IndicatorKey, TrendIndex, TrendSummary } from "./types";

export const CLASSES = 7;
const MIDDLE = (CLASSES - 1) / 2;

export type Ramp = "temperature" | "rainfall";
export type Outline = "solid" | "dashed" | "none";

type Meta = { ramp: Ramp; reversed: boolean; rateUnit: string; low: string; high: string };

// reversed: class 0 (a falling value) takes the wet end of the rainfall ramp
const META: Record<IndicatorKey, Meta> = {
  wet_season_rain_mm: { ramp: "rainfall", reversed: false, rateUnit: "mm", low: "less wet-season rain", high: "more wet-season rain" },
  wet_days: { ramp: "rainfall", reversed: false, rateUnit: "days", low: "fewer rainy days", high: "more rainy days" },
  heavy_rain_days: { ramp: "rainfall", reversed: false, rateUnit: "days", low: "fewer heavy-rain days", high: "more heavy-rain days" },
  wettest_day_mm: { ramp: "rainfall", reversed: false, rateUnit: "mm", low: "a lighter wettest day", high: "a heavier wettest day" },
  rain_onset_day: { ramp: "rainfall", reversed: true, rateUnit: "days", low: "rains start earlier", high: "rains start later" },
  wet_season_temp_c: { ramp: "temperature", reversed: false, rateUnit: "°C", low: "cooler wet season", high: "warmer wet season" },
  october_temp_c: { ramp: "temperature", reversed: false, rateUnit: "°C", low: "cooler October", high: "warmer October" },
};

export const rampFor = (key: IndicatorKey) => ({ ramp: META[key].ramp, reversed: META[key].reversed });
export const rateUnit = (key: IndicatorKey) => META[key].rateUnit;

export function layerDomain(index: TrendIndex, key: IndicatorKey): number {
  let largest = 0;
  for (const cell of index.cells) {
    const slope = cell.indicators?.[key]?.slope_per_decade;
    if (typeof slope === "number" && Number.isFinite(slope)) largest = Math.max(largest, Math.abs(slope));
  }
  return largest;
}

export function slopeClass(slope: number, domain: number): number {
  if (!(domain > 0)) return MIDDLE;
  const width = (2 * domain) / CLASSES;
  return Math.min(CLASSES - 1, Math.max(0, Math.floor((slope + domain) / width)));
}

export function cellOutline(summary: TrendSummary | undefined): Outline {
  if (summary?.significant_fdr) return "solid";
  if (summary?.significant) return "dashed";
  return "none";
}

export type LayerCell = {
  id: string;
  bounds: IndexCell["bounds"];
  slope: number | null;
  cls: number | null;
  outline: Outline;
  error: boolean;
};

export function cellLayer(index: TrendIndex, key: IndicatorKey): { domain: number; cells: LayerCell[] } {
  const domain = layerDomain(index, key);
  const cells = index.cells.map((cell) => {
    const summary = cell.error ? undefined : cell.indicators?.[key];
    const slope = typeof summary?.slope_per_decade === "number" ? summary.slope_per_decade : null;
    return {
      id: cell.id,
      bounds: cell.bounds,
      slope,
      cls: slope === null ? null : slopeClass(slope, domain),
      outline: cellOutline(summary),
      error: Boolean(cell.error),
    };
  });
  return { domain, cells };
}

const amount = (x: number) => (Number(x.toFixed(2)) || 0).toString();

export type Legend = {
  ramp: Ramp;
  reversed: boolean;
  low: string;
  high: string;
  middle: string;
  outlines: { style: Outline | "error"; words: string }[];
};

export function layerLegend(key: IndicatorKey, domain: number): Legend {
  const meta = META[key];
  const unit = `${meta.rateUnit} per decade`;
  return {
    ramp: meta.ramp,
    reversed: meta.reversed,
    low: `${meta.low}, up to ${amount(domain)} ${unit}`,
    high: `${meta.high}, up to ${amount(domain)} ${unit}`,
    middle: "little or no change",
    outlines: [
      { style: "solid", words: "Solid outline: significant after correcting for testing every cell (q < 0.05)." },
      { style: "dashed", words: "Dashed outline: significant in this cell alone (p < 0.05), not after the correction." },
      { style: "none", words: "No outline: not statistically significant." },
      { style: "error", words: "Grey hatching: NASA data for this cell could not be downloaded." },
    ],
  };
}
