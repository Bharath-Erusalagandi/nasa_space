import { describe, expect, test } from "vitest";
import {
  dots,
  linear,
  pathD,
  pivot,
  rangeEnds,
  seasonLabel,
  seasonStep,
  seasonsUsed,
  seasonTicks,
  senEnds,
  valueAxis,
} from "./chart";
import type { SeasonValue } from "./types";

const series = (first: number, values: (number | null)[]): SeasonValue[] =>
  values.map((value, i) => ({ season: first + i, label: seasonLabel(first + i), value }));

const record = series(1981, Array.from({ length: 45 }, (_, i) => 20 + i * 0.1));

describe("scales and ticks", () => {
  test("linear maps the domain onto the range, both ways round", () => {
    const y = linear([10, 20], [200, 0]);
    expect(y(10)).toBe(200);
    expect(y(15)).toBe(100);
    expect(y(20)).toBe(0);
  });

  test("ticks land on 1, 2, 2.5 or 5 times a power of ten", () => {
    expect(valueAxis(series(1981, [0, 10]), 5).ticks).toEqual([0, 2, 4, 6, 8, 10]);
    expect(valueAxis(series(1981, [0, 10])).ticks).toEqual([0, 2.5, 5, 7.5, 10]);
    expect(valueAxis(series(1981, [610, 1390])).ticks).toEqual([600, 800, 1000, 1200, 1400]);
  });

  test("the value domain is padded out to whole steps and ignores gaps", () => {
    expect(valueAxis(series(1981, [23.2, null, 27.9]))).toEqual({ domain: [22, 28], ticks: [22, 24, 26, 28] });
    expect(valueAxis(series(1981, [24.8, 28.5]))).toEqual({ domain: [24, 29], ticks: [24, 25, 26, 27, 28, 29] });
    expect(valueAxis(series(1981, [5, 5])).domain).toEqual([4, 6]);
    expect(valueAxis([]).domain).toEqual([0, 1]);
  });

  test("seasons are labelled by the years they span", () => {
    expect(seasonLabel(1985)).toBe("1985/86");
    expect(seasonLabel(1999)).toBe("1999/00");
  });

  test("season ticks fall on multiples of the step, wider when the chart is narrow", () => {
    expect(seasonTicks({ first: 1981, last: 2025 }, 5)).toEqual([1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]);
    expect(seasonStep(640, { first: 1981, last: 2025 })).toBe(5);
    expect(seasonStep(450, { first: 1981, last: 2025 })).toBe(10);
  });
});

describe("seasons used", () => {
  test("a window is the last N seasons; all is the whole record", () => {
    expect(seasonsUsed(record, "10")).toEqual({ first: 2016, last: 2025 });
    expect(seasonsUsed(record, "30")).toEqual({ first: 1996, last: 2025 });
    expect(seasonsUsed(record, "all")).toEqual({ first: 1981, last: 2025 });
  });

  test("a window longer than the record has no seasons", () => {
    expect(seasonsUsed(series(2017, Array(9).fill(1)), "10")).toBeNull();
  });

  test("dots outside the window are marked, missing seasons leave a gap", () => {
    const s = series(2000, [1, null, 3, 4]);
    const d = dots(s, { first: 2002, last: 2003 });
    expect(d.map((p) => p.season)).toEqual([2000, 2002, 2003]);
    expect(d.map((p) => p.inWindow)).toEqual([false, true, true]);
    expect(dots(s, null).every((p) => p.inWindow)).toBe(true);
  });
});

describe("lines", () => {
  test("the Sen line runs from the first to the last season used", () => {
    const [a, b] = senEnds({ intercept: -44.77, slope_per_year: 0.0357 }, { first: 1981, last: 2025 });
    expect(a.season).toBe(1981);
    expect(a.value).toBeCloseTo(-44.77 + 0.0357 * 1981, 9);
    expect(b.season).toBe(2025);
    expect(b.value).toBeCloseTo(-44.77 + 0.0357 * 2025, 9);
  });

  test("the pivot is the median season and the median value of the seasons used", () => {
    expect(pivot(series(2000, [5, 1, 9, 3, 7]), { first: 2000, last: 2004 })).toEqual({ season: 2002, value: 5 });
    expect(pivot(series(2000, [5, 1, 9, 3]), { first: 2001, last: 2003 })).toEqual({ season: 2002, value: 3 });
    expect(pivot(series(2000, [null]), { first: 2000, last: 2000 })).toBeNull();
  });

  test("the range lines pass through the pivot with the low and high slopes", () => {
    const through = { season: 2003, value: 25 };
    const { low, high } = rangeEnds({ ci_low_per_decade: 0.1, ci_high_per_decade: 0.6 }, through, { first: 1981, last: 2025 });
    expect(low[0].value).toBeCloseTo(25 - 0.01 * 22, 9);
    expect(low[1].value).toBeCloseTo(25 + 0.01 * 22, 9);
    expect(high[0].value).toBeCloseTo(25 - 0.06 * 22, 9);
    expect(high[1].value).toBeCloseTo(25 + 0.06 * 22, 9);
  });

  test("a path visits each point in pixels", () => {
    const x = linear([2000, 2010], [0, 100]);
    const y = linear([0, 10], [100, 0]);
    expect(pathD([{ season: 2000, value: 0 }, { season: 2010, value: 10 }], x, y)).toBe("M0.0 100.0 L100.0 0.0");
  });
});
