import { describe, expect, test } from "vitest";
import { cellId, powerCell } from "./powerCell";
import { senLine } from "./senLine";

describe("powerCell and cellId", () => {
  test("plan cases", () => {
    expect(powerCell(-14.06, 32.04)).toEqual([-14.0, 31.875]);
    expect(powerCell(-13.80, 32.25)).toEqual([-14.0, 32.5]);
    expect(powerCell(-14.30, 32.04)).toEqual([-14.5, 31.875]);
    expect(cellId([-14.0, 31.875])).toBe("-14.000_31.875");
  });

  test("a latitude tie rounds half to even like the python twin", () => {
    expect(powerCell(-13.75, 32.0)).toEqual([-14, 31.875]);
    expect(powerCell(-13.25, 32.0)).toEqual([-13, 31.875]);
  });

  test("a longitude tie rounds half to even", () => {
    expect(powerCell(-14, 31.5625)).toEqual([-14, 31.25]);
    expect(powerCell(-14, 32.1875)).toEqual([-14, 32.5]);
  });

  test("a cell at zero has no negative zero", () => {
    expect(cellId(powerCell(-0.1, -0.1))).toBe("0.000_0.000");
  });
});

describe("senLine", () => {
  test("plan case", () => {
    // line value = intercept + slope_per_year * season
    expect(senLine({ intercept: 100, slope_per_year: 2 }, [2000, 2001])).toEqual([4100, 4102]);
  });

  test("empty seasons give an empty line", () => {
    expect(senLine({ intercept: 1, slope_per_year: 1 }, [])).toEqual([]);
  });
});
