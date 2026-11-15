import { describe, expect, test } from "vitest";
import { cellFile, index, indexCell, summary, trend } from "@/lib/trends/__fixtures__/trends";
import { formatP, next, prev, STORY, stepLabel } from "./story";

const cell = cellFile({
  wet_season_rain_mm: { all: trend(0.92, 0.992) },
  october_temp_c: { all: trend(0.36, 0.007), ten: trend(-1.04, 0.474, { n: 10 }) },
  rain_onset_day: { all: trend(2.86, 0.232) },
});
const sample = index([
  indexCell("a", -14, 31.875, { october_temp_c: summary(0.36, 0.007, 0.01) }),
  indexCell("b", -13.5, 32.5, { october_temp_c: summary(0.42, 0.0005, 0.004) }),
  indexCell("c", -13, 32.5, { october_temp_c: summary(0.2, 0.04, 0.08) }),
  indexCell("d", -12.5, 33.125, {}, "URLError"),
]);
const data = { placeName: "Katete", cell, index: sample };

describe("story", () => {
  test("six steps with the plan's selections", () => {
    expect(STORY).toHaveLength(6);
    expect(STORY.map((s) => [s.indicator, s.window, s.panel])).toEqual([
      ["wet_season_rain_mm", "all", "sky"],
      ["october_temp_c", "all", "sky"],
      ["october_temp_c", "10", "sky"],
      ["october_temp_c", "all", "map"],
      ["october_temp_c", "all", "ground"],
      ["october_temp_c", "all", "action"],
    ]);
    expect(STORY[3].layer).toBe("october_temp_c");
  });

  test("next and prev stop at the ends", () => {
    expect(prev(0)).toBe(0);
    expect(next(0)).toBe(1);
    expect(next(5)).toBe(5);
    expect(prev(5)).toBe(4);
    expect(stepLabel(1)).toBe("2 / 6");
  });

  test("step 1 says not statistically significant only when it is not significant", () => {
    expect(STORY[0].sentence(data)).toBe("Around Katete, the change in wet-season rainfall over 45 seasons is not statistically significant (p = 0.992).");
    const drier = { ...data, cell: cellFile({ wet_season_rain_mm: { all: trend(-12.5, 0.01) } }) };
    const sentence = STORY[0].sentence(drier);
    expect(sentence).not.toContain("not statistically significant");
    expect(sentence).toBe("Around Katete, wet-season rainfall is falling by 12.50 mm per decade over 45 seasons (p = 0.010), statistically significant.");
  });

  test("step 2 states the October change from data", () => {
    expect(STORY[1].sentence(data)).toBe("Around Katete, October temperature is rising by 0.36 °C per decade over 45 seasons (p = 0.007), statistically significant.");
  });

  test("step 3 compares the 10-season window with the full record", () => {
    expect(STORY[2].sentence(data)).toBe(
      "The last 10 seasons alone point down by 1.04 °C per decade, but that is not statistically significant (p = 0.474). Over 45 seasons the trend is up.",
    );
  });

  test("step 3 says significant when the short window is, and qualifies a weak full record", () => {
    const strong = { ...data, cell: cellFile({ october_temp_c: { all: trend(0.2, 0.3), ten: trend(1.5, 0.01, { n: 10 }) } }) };
    expect(STORY[2].sentence(strong)).toBe(
      "The last 10 seasons alone point up by 1.50 °C per decade, statistically significant (p = 0.010). Over 45 seasons the trend is up, but that is not statistically significant (p = 0.300).",
    );
  });

  test("a p just under 0.05 is never printed as 0.050 beside significant", () => {
    const edge = { ...data, cell: cellFile({ october_temp_c: { all: trend(0.36, 0.0496) } }) };
    expect(STORY[1].sentence(edge)).toContain("(p = 0.0496), statistically significant");
  });

  test("every non-significant branch says not statistically significant", () => {
    const flat = index([indexCell("a", -14, 31.875, { october_temp_c: summary(0.1, 0.3, 0.5) })]);
    expect(STORY[3].sentence({ ...data, index: flat })).toContain("not statistically significant");
  });

  test("step 4 counts cells that survive the correction", () => {
    expect(STORY[3].sentence(data)).toBe("October temperature is rising significantly in 2 of 3 grid cells after correcting for testing every cell (solid outlines).");
  });

  test("step 5 and step 6 name the place", () => {
    expect(STORY[4].sentence(data)).toContain("around Katete");
    expect(STORY[5].sentence(data)).toBe("The danger sign answer sets the triage outcome, the order and the delivery to Katete.");
  });

  test("a missing trend never invents a claim", () => {
    const empty = { placeName: "Lundazi", cell: cellFile({}) };
    expect(STORY[0].sentence(empty)).toContain("not enough seasons to test");
    expect(STORY[2].sentence(empty)).toContain("not enough seasons to test");
    expect(STORY[1].sentence({ placeName: "Lundazi" })).toContain("not loaded");
  });

  test("p-values are written like the trend engine writes them", () => {
    expect(formatP(0.0004)).toBe("p < 0.001");
    expect(formatP(0.007)).toBe("p = 0.007");
  });
});
