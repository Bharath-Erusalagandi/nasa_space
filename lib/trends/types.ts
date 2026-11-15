import type { PodKind } from "@/lib/pod/parseLine";

export const INDICATOR_KEYS = [
  "wet_season_rain_mm",
  "wet_days",
  "heavy_rain_days",
  "wettest_day_mm",
  "rain_onset_day",
  "wet_season_temp_c",
  "october_temp_c",
] as const;

export type IndicatorKey = (typeof INDICATOR_KEYS)[number];

export type WindowKey = "10" | "20" | "30";
export type WindowChoice = WindowKey | "all";

export type Bounds = { south: number; north: number; west: number; east: number };

export type Trend = {
  n: number;
  slope_per_year: number;
  slope_per_decade: number;
  ci_low_per_decade: number;
  ci_high_per_decade: number;
  intercept: number;
  mk_s: number;
  mk_z: number;
  mk_p: number;
  ols_slope_per_decade: number;
  ols_p: number;
  lag1_autocorrelation: number | null;
  autocorrelation_warning: boolean;
  direction: "increasing" | "decreasing" | "flat";
  significant: boolean;
  alpha: number;
};

export type TrendSummary = {
  n: number | null;
  slope_per_decade: number | null;
  ci_low_per_decade: number | null;
  ci_high_per_decade: number | null;
  mk_p: number | null;
  q: number | null;
  significant: boolean;
  significant_fdr: boolean;
  direction: Trend["direction"] | null;
  autocorrelation_warning: boolean;
};

export type IndexCell = {
  id: string;
  lat: number;
  lon: number;
  bounds: Bounds;
  error?: string;
  indicators?: Partial<Record<IndicatorKey, TrendSummary>>;
};

export type PlaceKind = "town" | "facility" | "cell";

export type Place = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  kind: PlaceKind;
  cell: string;
  type?: string;
  district?: string;
};

export type TrendIndex = {
  generated: string;
  source: string | null;
  period: string | null;
  cells: IndexCell[];
  places: Place[];
};

export type SeasonValue = { season: number; label: string; value: number | null };

export type Indicator = {
  label: string;
  unit: string;
  definition: string;
  series: SeasonValue[];
  trend: Trend | null;
  verdict: string;
  windows: Record<WindowKey, Trend | null>;
  second_source?: { name: string; trend: Trend | null };
};

export type CellFile = {
  place: string;
  lat: number;
  lon: number;
  source: string;
  period: string;
  indicators: Record<IndicatorKey, Indicator>;
  cell: { id: string; lat: number; lon: number; bounds: Bounds };
};

export type Normal = { mean: number; p10: number; p90: number; n: number };

export type PodSite = {
  cell: string;
  lat: number;
  lon: number;
  source: string;
  normals: Record<string, Normal>;
};

export type Agreement = {
  n: number;
  bias: number;
  sd: number;
  loa_low: number;
  loa_high: number;
  mae: number;
  within_tolerance: number;
  people: number;
};

export type Confusion = {
  labels: string[];
  matrix: number[][];
  recall: Record<string, number>;
  accuracy: number;
  n: number;
};

export type ValidationResults = Partial<Record<Extract<PodKind, "heart_rate" | "spo2" | "air_temp_c">, Agreement>> & {
  mosquito?: Confusion;
};

export type Position = [number, number];

export type Feature<P = Record<string, unknown>> = {
  type: "Feature";
  properties: P;
  geometry: { type: string; coordinates: unknown };
};

export type FeatureCollection<P = Record<string, unknown>> = { type: "FeatureCollection"; features: Feature<P>[] };

export type Route = { km: number; minutes: number; line: Position[] };

export type Routes = {
  hub: { id: string; name: string; lat: number; lon: number };
  routes: Record<string, Route>;
};

export type MapSource = { name: string; licence: string; url: string; fetched: string; used_for: string };

export type Frame = { west: number; south: number; east: number; north: number };

export type MapFiles = {
  province: FeatureCollection;
  districts: FeatureCollection;
  roads: FeatureCollection;
  rivers: FeatureCollection;
  towns: FeatureCollection;
  facilities: FeatureCollection;
  context: FeatureCollection;
  routes: Routes;
  sources: MapSource[];
  frame: Frame;
};

export type MapName = keyof MapFiles;

export const displayUnit = (unit: string) => unit.replace(/deg C/g, "°C");
