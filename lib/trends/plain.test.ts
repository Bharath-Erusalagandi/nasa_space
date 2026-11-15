import { describe, expect, it } from "vitest";
import { plainVerdict } from "./plain";
import type { Trend } from "./types";

const trend = (over: Partial<Trend>): Trend => ({
  n: 45,
  slope_per_year: 0.036,
  slope_per_decade: 0.36,
  ci_low_per_decade: 0.11,
  ci_high_per_decade: 0.58,
  intercept: 0,
  mk_s: 0,
  mk_z: 0,
  mk_p: 0.007,
  ols_slope_per_decade: 0.33,
  ols_p: 0.003,
  lag1_autocorrelation: null,
  autocorrelation_warning: false,
  direction: "increasing",
  significant: true,
  alpha: 0.05,
  ...over,
});

describe("plain verdict", () => {
  it("names the direction, the rate and the place for a significant trend", () => {
    expect(plainVerdict("october_temp_c", "October temperature", trend({}), "Katete")).toBe(
      "The data points to warmer October around Katete, by about 0.36 °C per decade over 45 seasons. A change this steady is unlikely to be chance, so it counts as a trend.",
    );
  });

  it("does not call a change a trend when the test does not", () => {
    const text = plainVerdict("wet_season_rain_mm", "Wet-season rainfall", trend({ slope_per_decade: -18.98, direction: "decreasing", significant: false }), "Katete");
    expect(text).toContain("less wet-season rain around Katete, by about 19 mm per decade");
    expect(text).toContain("does not count as a trend yet");
  });

  it("uses the indicator's own words when a later start means a rising number", () => {
    expect(plainVerdict("rain_onset_day", "Start of the rains", trend({ slope_per_decade: 2.4 }), "")).toContain("rains start later, by about 2.4 days per decade");
  });

  it("says so when nothing changed, and nothing when there is no trend to describe", () => {
    expect(plainVerdict("wet_days", "Rainy days", trend({ direction: "flat", slope_per_decade: 0 }), "Chipata")).toBe("Rainy days around Chipata shows no change over 45 seasons.");
    expect(plainVerdict("wet_days", "Rainy days", null, "Chipata")).toBeNull();
  });
});
