import { describe, expect, it } from "vitest";
import type { TrendIndex } from "@/lib/trends/types";
import { hoverCard } from "./hover";

const bounds = { south: -14.25, north: -13.75, west: 31.5625, east: 32.1875 };
const summary = { n: 45, slope_per_decade: 0.36, ci_low_per_decade: 0.11, ci_high_per_decade: 0.58, mk_p: 0.007, q: 0.009, significant: true, significant_fdr: true, direction: "increasing", autocorrelation_warning: false };

const index = {
  generated: "",
  source: null,
  period: null,
  cells: [
    { id: "a", lat: -14, lon: 31.875, bounds, indicators: { october_temp_c: summary, wet_days: { ...summary, slope_per_decade: -1.2, significant: false, significant_fdr: false } } },
    { id: "broken", lat: -12, lon: 33, bounds: { ...bounds, south: -12.25, north: -11.75 }, error: "no data" },
  ],
  places: [
    { id: "katete", name: "Katete", lat: -14.06, lon: 32.04, kind: "town", cell: "a" },
    { id: "clinic", name: "Chimtende Rural Health Centre", lat: -14.1, lon: 32.0, kind: "facility", cell: "a", type: "Rural Health Centre", district: "Katete" },
  ],
} as unknown as TrendIndex;

const base = { index, key: "october_temp_c" as const, label: "October temperature", heights: { katete: 1063 }, climate: true };

describe("hover card", () => {
  it("gives a cell its trend and what the test said", () => {
    expect(hoverCard({ kind: "cell", id: "a" }, base)).toEqual({
      title: "NASA grid cell around Katete",
      lines: ["October temperature: +0.36 °C per decade", "Significant after correction"],
    });
  });

  it("does not call a trend significant when it is not", () => {
    expect(hoverCard({ kind: "cell", id: "a" }, { ...base, key: "wet_days", label: "Rainy days" })?.lines[1]).toBe("Not statistically significant");
  });

  it("says when a cell has no NASA data", () => {
    expect(hoverCard({ kind: "cell", id: "broken" }, base)?.lines).toEqual(["No NASA data for this cell"]);
  });

  it("gives a place its kind, height and its cell's trend", () => {
    expect(hoverCard({ kind: "place", id: "katete" }, base)).toEqual({
      title: "Katete",
      lines: ["Town", "1,063 m above sea level", "October temperature: +0.36 °C per decade", "Significant after correction"],
    });
    expect(hoverCard({ kind: "place", id: "clinic" }, base)?.lines[0]).toBe("Rural Health Centre, Katete district");
  });

  it("leaves the climate line out when the map is not showing climate", () => {
    expect(hoverCard({ kind: "place", id: "katete" }, { ...base, climate: false })?.lines).toEqual(["Town", "1,063 m above sea level"]);
  });

  it("returns nothing for something that is not on the map", () => {
    expect(hoverCard({ kind: "place", id: "nowhere" }, base)).toBeNull();
  });
});
