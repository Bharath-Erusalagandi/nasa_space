import { describe, expect, test } from "vitest";
import { trend } from "./__fixtures__/trends";
import {
  agreement,
  descriptor,
  minusSigns,
  num,
  pValue,
  qValue,
  range,
  rate,
  rateText,
  rateUnit,
  reading,
  recordLimit,
  shortSource,
  significance,
  signed,
} from "./format";
import type { Indicator } from "./types";

describe("numbers", () => {
  test("slopes carry their sign; zero has none", () => {
    expect(signed(0.3573)).toBe("+0.36");
    expect(signed(-1.038)).toBe("\u22121.04");
    expect(signed(38.83)).toBe("+38.8");
    expect(signed(-0.001)).toBe("0.00");
    expect(signed(0)).toBe("0.00");
  });

  test("ranges are plain numbers at one precision", () => {
    expect(range(0.10697, 0.5775)).toBe("(0.11 to 0.58)");
    expect(range(-48.94, 52.01)).toBe("(\u221248.9 to 52.0)");
    expect(range(-0.004, 0.2)).toBe("(0.00 to 0.20)");
    expect(range(-0, 2.08)).toBe("(0.00 to 2.08)");
  });

  test("units show deg C as °C and drop the day of reference from rates", () => {
    expect(rateUnit("deg C")).toBe("°C per decade");
    expect(rateUnit("days after 1 Oct")).toBe("days per decade");
    expect(rateUnit("mm")).toBe("mm per decade");
  });

  test("a rate keeps the figure and its range at one precision", () => {
    const t = { slope_per_decade: 0.3573, ci_low_per_decade: 0.107, ci_high_per_decade: 0.5775 };
    expect(rate(t, "deg C")).toEqual({ figure: "+0.36", unit: "°C per decade", range: "(0.11 to 0.58)" });
    expect(rate({ slope_per_decade: 0.92, ci_low_per_decade: -48.9, ci_high_per_decade: 52 }, "mm").figure).toBe("+0.9");
    expect(rateText(trend(-1.04, 0.47), "deg C")).toBe("\u22121.04 °C per decade (\u22121.24 to \u22120.84)");
  });

  test("readings round by size and show their unit", () => {
    expect(reading(23.4123, "deg C")).toBe("23.4 °C");
    expect(reading(1057.34, "mm")).toBe("1057 mm");
    expect(reading(12, "days")).toBe("12 days");
    expect(reading(-3.25, "deg C")).toBe("\u22123.3 °C");
    expect(reading(-0.04, "deg C")).toBe("0.0 °C");
  });

  test("num writes a real minus sign and never -0", () => {
    expect(num(-1.5, 1)).toBe("\u22121.5");
    expect(num(-0.04, 1)).toBe("0.0");
    expect(num(-0, 0)).toBe("0");
    expect(num(2.345, 2)).toBe("2.35");
    expect(minusSigns("within -3.8 to +5.8 bpm, (-0.2 to 1)")).toBe("within \u22123.8 to +5.8 bpm, (\u22120.2 to 1)");
    expect(minusSigns("1981-82, K-01")).toBe("1981-82, K-01");
  });
});

describe("p-values", () => {
  test("three decimals, and a floor below 0.001", () => {
    expect(pValue(0.006734)).toBe("p = 0.007");
    expect(pValue(0.9922)).toBe("p = 0.992");
    expect(pValue(0.0000782)).toBe("p < 0.001");
    expect(qValue(0.0216)).toBe("q = 0.022");
  });

  test("more decimals when rounding would cross alpha", () => {
    expect(pValue(0.0497)).toBe("p = 0.0497");
    expect(pValue(0.04996)).toBe("p = 0.04996");
    expect(pValue(0.0502)).toBe("p = 0.050");
  });

  test("the verdict wording follows the engine's decision", () => {
    expect(significance(trend(0.36, 0.0067))).toBe("Yes, p = 0.007");
    expect(significance(trend(0.01, 0.992))).toBe("No, not statistically significant, p = 0.992");
  });
});

const indicator = (extra: Partial<Indicator> = {}): Indicator => ({
  label: "October temperature",
  unit: "deg C",
  definition: "Mean air temperature in October.",
  series: [
    { season: 2000, label: "2000/01", value: 1 },
    { season: 2001, label: "2001/02", value: null },
    { season: 2002, label: "2002/03", value: 2 },
  ],
  trend: trend(0.36, 0.007),
  verdict: "",
  windows: { "10": trend(-1.04, 0.47), "20": trend(-0.47, 0.127, { n: 20 }), "30": null },
  ...extra,
});

describe("words from the cell file", () => {
  test("the descriptor names the source, and the seasons with a value", () => {
    const source = "NASA POWER daily point API (MERRA-2 reanalysis): PRECTOTCORR";
    expect(shortSource(source)).toBe("NASA POWER");
    const cell = { source, period: "2000/01 to 2002/03", indicators: { october_temp_c: indicator() } } as never;
    expect(descriptor(cell, "october_temp_c")).toBe("NASA POWER, 2 seasons");
  });

  test("the two sources agree or disagree on direction", () => {
    expect(agreement(trend(0.3, 0.01), trend(0.1, 0.4))).toBe("Both sources agree on direction.");
    expect(agreement(trend(0.3, 0.01), trend(-0.1, 0.4))).toBe("The sources disagree; treat this trend with caution.");
    expect(agreement(trend(0.3, 0.01), null)).toBeNull();
  });

  test("the record limit compares all seasons with the last 20", () => {
    expect(recordLimit(indicator())).toBe(
      "All 45 seasons give +0.36 °C per decade (p = 0.007, significant); the last 20 alone give \u22120.47 (p = 0.127, not statistically significant). " +
        "This record cannot say whether the change continues at the same rate.",
    );
    expect(recordLimit(indicator({ trend: null }))).toBeNull();
    const both = recordLimit(indicator({ windows: { "10": null, "20": trend(0.5, 0.01, { n: 20 }), "30": null } }));
    expect(both).toMatch(/^All 45 seasons/);
    expect(both).not.toMatch(/cannot say/);
  });
});
