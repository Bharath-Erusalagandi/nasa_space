import type { CellFile, IndexCell, Indicator, IndicatorKey, Trend, TrendIndex, TrendSummary } from "./types";
import { INDICATOR_KEYS } from "./types";

// shapes for tests only; the numbers are made up and never shown
export function trend(slope: number, p: number, extra: Partial<Trend> = {}): Trend {
  return {
    n: 45,
    slope_per_year: slope / 10,
    slope_per_decade: slope,
    ci_low_per_decade: slope - 0.2,
    ci_high_per_decade: slope + 0.2,
    intercept: 0,
    mk_s: 0,
    mk_z: 0,
    mk_p: p,
    ols_slope_per_decade: slope,
    ols_p: p,
    lag1_autocorrelation: 0,
    autocorrelation_warning: false,
    direction: slope > 0 ? "increasing" : slope < 0 ? "decreasing" : "flat",
    significant: p < 0.05,
    alpha: 0.05,
    ...extra,
  };
}

export function summary(slope: number, p: number, q: number | null = null): TrendSummary {
  return {
    n: 45,
    slope_per_decade: slope,
    ci_low_per_decade: slope - 0.2,
    ci_high_per_decade: slope + 0.2,
    mk_p: p,
    q,
    significant: p < 0.05,
    significant_fdr: q !== null && q < 0.05,
    direction: slope > 0 ? "increasing" : slope < 0 ? "decreasing" : "flat",
    autocorrelation_warning: false,
  };
}

export function indexCell(id: string, lat: number, lon: number, indicators: Partial<Record<IndicatorKey, TrendSummary>>, error?: string): IndexCell {
  return {
    id,
    lat,
    lon,
    bounds: { south: lat - 0.25, north: lat + 0.25, west: lon - 0.3125, east: lon + 0.3125 },
    ...(error ? { error } : { indicators }),
  };
}

export function index(cells: IndexCell[]): TrendIndex {
  return {
    generated: "2026-11-14",
    source: "test",
    period: "1981/82 to 2025/26",
    cells,
    places: [
      { id: "katete", name: "Katete", lat: -14.06, lon: 32.04, kind: "town", cell: "-14.000_31.875" },
      { id: "katete-clinic", name: "Katete Clinic", lat: -14.1, lon: 31.9, kind: "facility", cell: "-14.000_31.875" },
      { id: "cell-14.000_31.875", name: "Grid cell", lat: -14, lon: 31.875, kind: "cell", cell: "-14.000_31.875" },
      { id: "chipata", name: "Chipata", lat: -13.63, lon: 32.65, kind: "town", cell: "-13.500_32.500" },
    ],
  };
}

export function cellFile(trends: Partial<Record<IndicatorKey, { all: Trend | null; ten?: Trend | null }>>): CellFile {
  const indicators = {} as Record<IndicatorKey, Indicator>;
  for (const key of INDICATOR_KEYS) {
    const t = trends[key] ?? { all: null };
    indicators[key] = {
      label: key === "wet_season_rain_mm" ? "Wet-season rainfall" : key === "october_temp_c" ? "October temperature" : key,
      unit: key.endsWith("_c") ? "deg C" : "mm",
      definition: "",
      series: [],
      trend: t.all,
      verdict: "",
      windows: { "10": t.ten ?? null, "20": null, "30": null },
    };
  }
  const bounds = { south: -14.25, north: -13.75, west: 31.5625, east: 32.1875 };
  return { place: "-14.000_31.875", lat: -14, lon: 31.875, source: "test", period: "", indicators, cell: { id: "-14.000_31.875", lat: -14, lon: 31.875, bounds } };
}
