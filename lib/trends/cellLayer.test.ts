import { describe, expect, test } from "vitest";
import { cellLayer, cellOutline, layerDomain, layerLegend, rampFor, slopeClass } from "./cellLayer";
import { index, indexCell, summary } from "./fixtures";

const sample = index([
  indexCell("a", -14, 31.875, { october_temp_c: summary(0.36, 0.007, 0.02), wet_season_rain_mm: summary(0.9, 0.99, 0.99) }),
  indexCell("b", -13.5, 32.5, { october_temp_c: summary(-0.42, 0.04, 0.09), wet_season_rain_mm: summary(-7.8, 0.8, 0.99) }),
  indexCell("c", -13, 32.5, { october_temp_c: summary(0.1, 0.5, 0.6), wet_season_rain_mm: summary(0, 0.9, 0.99) }),
  indexCell("d", -12.5, 33.125, {}, "URLError: timed out"),
]);

describe("cell layer", () => {
  test("the domain is the largest absolute slope for that indicator", () => {
    expect(layerDomain(sample, "october_temp_c")).toBe(0.42);
    expect(layerDomain(sample, "wet_season_rain_mm")).toBe(7.8);
    expect(layerDomain(sample, "wet_days")).toBe(0);
  });

  test("seven classes centred on zero", () => {
    expect(slopeClass(-1, 1)).toBe(0);
    expect(slopeClass(1, 1)).toBe(6);
    expect(slopeClass(0, 1)).toBe(3);
    expect(slopeClass(0.1, 1)).toBe(3);
    expect(slopeClass(-0.1, 1)).toBe(3);
    expect(slopeClass(0.2, 1)).toBe(4);
    expect(slopeClass(-0.5, 1)).toBe(1);
    expect(slopeClass(5, 1)).toBe(6);
    expect(slopeClass(0.3, 0)).toBe(3);
  });

  test("outline: solid after FDR, dashed when only significant, none otherwise", () => {
    expect(cellOutline(summary(0.36, 0.007, 0.02))).toBe("solid");
    expect(cellOutline(summary(0.36, 0.04, 0.09))).toBe("dashed");
    expect(cellOutline(summary(0.36, 0.5, 0.6))).toBe("none");
    expect(cellOutline(undefined)).toBe("none");
  });

  test("each cell gets a class, an outline and an error flag", () => {
    const layer = cellLayer(sample, "october_temp_c");
    expect(layer.domain).toBe(0.42);
    expect(layer.cells.map((c) => [c.id, c.cls, c.outline, c.error])).toEqual([
      ["a", 6, "solid", false],
      ["b", 0, "dashed", false],
      ["c", 4, "none", false],
      ["d", null, "none", true],
    ]);
  });

  test("a cell without that indicator has no class but no error", () => {
    const layer = cellLayer(sample, "wet_days");
    expect(layer.cells[0]).toMatchObject({ cls: null, slope: null, error: false, outline: "none" });
  });

  test("ramps follow the climate report convention", () => {
    expect(rampFor("october_temp_c")).toEqual({ ramp: "temperature", reversed: false });
    expect(rampFor("wet_season_rain_mm")).toEqual({ ramp: "rainfall", reversed: false });
    expect(rampFor("rain_onset_day")).toEqual({ ramp: "rainfall", reversed: true });
  });

  test("the legend explains both ends and every outline in words", () => {
    const legend = layerLegend("october_temp_c", 0.42);
    expect(legend.low).toBe("cooler October, up to 0.42 °C per decade");
    expect(legend.high).toBe("warmer October, up to 0.42 °C per decade");
    expect(legend.outlines.map((o) => o.style)).toEqual(["solid", "dashed", "none", "error"]);
    expect(legend.outlines[2].words).toContain("not statistically significant");
    expect(layerLegend("rain_onset_day", 3).high).toBe("rains start later, up to 3 days per decade");
  });
});
