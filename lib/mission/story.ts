import { POD_ID } from "@/lib/brand";
import { rateUnit } from "@/lib/trends/cellLayer";
import { pValue } from "@/lib/trends/format";
import type { CellFile, IndicatorKey, Trend, TrendIndex, WindowChoice } from "@/lib/trends/types";

export type Panel = "sky" | "map" | "ground" | "action";

export type StoryData = { placeName: string; cell?: CellFile; index?: TrendIndex };

export type StoryStep = {
  question: string;
  indicator: IndicatorKey;
  window: WindowChoice;
  layer: IndicatorKey;
  panel: Panel;
  sentence: (data: StoryData) => string;
};

export const formatP = (p: number, alpha = 0.05) => pValue(p, alpha);
const pOf = (t: Trend) => formatP(t.mk_p, t.alpha);
const NOT_SIGNIFICANT = "not statistically significant";

function change(key: IndicatorKey, t: Trend): string {
  if (t.direction === "flat") return "shows no change";
  const verb = t.direction === "increasing" ? "is rising" : "is falling";
  return `${verb} by ${Math.abs(t.slope_per_decade).toFixed(2)} ${rateUnit(key)} per decade`;
}

const MONTH = /^(January|February|March|April|May|June|July|August|September|October|November|December)\b/;

function indicatorName(data: StoryData, key: IndicatorKey): string {
  const label = data.cell?.indicators[key]?.label ?? key.replace(/_/g, " ");
  return MONTH.test(label) ? label : label[0].toLowerCase() + label.slice(1);
}

const capital = (text: string) => text[0].toUpperCase() + text.slice(1);

function trendOf(data: StoryData, key: IndicatorKey, window: WindowChoice = "all"): Trend | null | undefined {
  const indicator = data.cell?.indicators[key];
  if (!indicator) return undefined;
  return window === "all" ? indicator.trend : indicator.windows[window];
}

function trendSentence(data: StoryData, key: IndicatorKey): string {
  const name = indicatorName(data, key);
  const t = trendOf(data, key);
  if (t === undefined) return `${capital(name)} around ${data.placeName}: the trend file for this cell is not loaded.`;
  if (t === null) return `${capital(name)} around ${data.placeName}: not enough seasons to test (need at least 10).`;
  if (!t.significant) {
    return `Around ${data.placeName}, the change in ${name} over ${t.n} seasons is ${NOT_SIGNIFICANT} (${pOf(t)}).`;
  }
  return `Around ${data.placeName}, ${name} ${change(key, t)} over ${t.n} seasons (${pOf(t)}), statistically significant.`;
}

function pointing(key: IndicatorKey, t: Trend): string {
  if (t.direction === "flat") return "show no change";
  return `point ${t.direction === "increasing" ? "up" : "down"} by ${Math.abs(t.slope_per_decade).toFixed(2)} ${rateUnit(key)} per decade`;
}

const verdict = (t: Trend) => (t.significant ? `, statistically significant (${pOf(t)})` : `, but that is ${NOT_SIGNIFICANT} (${pOf(t)})`);

function recordSentence(all: Trend): string {
  const way = all.direction === "flat" ? "flat" : all.direction === "increasing" ? "up" : "down";
  return `Over ${all.n} seasons the trend is ${way}${all.significant ? "" : `, but that is ${NOT_SIGNIFICANT} (${pOf(all)})`}.`;
}

function windowSentence(data: StoryData, key: IndicatorKey, window: "10" | "20" | "30"): string {
  const short = trendOf(data, key, window);
  const all = trendOf(data, key);
  if (short === undefined) return `The ${window}-season trend for ${data.placeName} is not loaded.`;
  if (short === null) return `The last ${window} seasons alone are not enough seasons to test (need at least 10).`;
  const head = `The last ${window} seasons alone ${pointing(key, short)}${verdict(short)}.`;
  return all ? `${head} ${recordSentence(all)}` : head;
}

function whereSentence(data: StoryData, key: IndicatorKey): string {
  const name = indicatorName(data, key);
  const tested = (data.index?.cells ?? []).filter((c) => !c.error && c.indicators?.[key]?.mk_p != null);
  if (!tested.length) return `Solid outlines on the map mark cells where ${name} changed significantly after correcting for testing every cell.`;
  const Name = capital(name);
  const strong = tested.filter((c) => c.indicators?.[key]?.significant_fdr);
  const correction = "after correcting for testing every cell";
  if (!strong.length) return `The change in ${name} is ${NOT_SIGNIFICANT} in any of the ${tested.length} grid cells ${correction}.`;
  const rising = strong.filter((c) => c.indicators?.[key]?.direction === "increasing").length;
  const way = rising === strong.length ? "rising" : rising === 0 ? "falling" : "changing";
  return `${Name} is ${way} significantly in ${strong.length} of ${tested.length} grid cells ${correction} (solid outlines).`;
}

export const STORY: StoryStep[] = [
  {
    question: "Is the rain disappearing?",
    indicator: "wet_season_rain_mm",
    window: "all",
    layer: "wet_season_rain_mm",
    panel: "sky",
    sentence: (data) => trendSentence(data, "wet_season_rain_mm"),
  },
  {
    question: "Then what is changing?",
    indicator: "october_temp_c",
    window: "all",
    layer: "october_temp_c",
    panel: "sky",
    sentence: (data) => trendSentence(data, "october_temp_c"),
  },
  {
    question: "Why ten years is not enough.",
    indicator: "october_temp_c",
    window: "10",
    layer: "october_temp_c",
    panel: "sky",
    sentence: (data) => windowSentence(data, "october_temp_c", "10"),
  },
  {
    question: "Where?",
    indicator: "october_temp_c",
    window: "all",
    layer: "october_temp_c",
    panel: "map",
    sentence: (data) => whereSentence(data, "october_temp_c"),
  },
  {
    question: "Check the ground.",
    indicator: "october_temp_c",
    window: "all",
    layer: "october_temp_c",
    panel: "ground",
    sentence: (data) => `Pod ${POD_ID} checks the NASA cell around ${data.placeName} on the ground: the air, the mosquitoes and the patient.`,
  },
  {
    question: "Act.",
    indicator: "october_temp_c",
    window: "all",
    layer: "october_temp_c",
    panel: "action",
    sentence: (data) => `The danger sign answer sets the triage outcome, the order and the delivery to ${data.placeName}.`,
  },
];

export const next = (step: number) => Math.min(STORY.length - 1, step + 1);
export const prev = (step: number) => Math.max(0, step - 1);
export const stepLabel = (step: number) => `${step + 1} / ${STORY.length}`;
