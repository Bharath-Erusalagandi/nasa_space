import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { dataColor, NO_DATA, rampColors } from "./colors";

describe("dataColor", () => {
  it("maps a class to its ramp variable", () => {
    expect(dataColor("temperature", 0)).toBe("var(--color-data-temp-0)");
    expect(dataColor("temperature", 6)).toBe("var(--color-data-temp-6)");
    expect(dataColor("rainfall", 3)).toBe("var(--color-data-rain-3)");
  });

  it("flips the ramp when reversed, so an earlier rain onset is wet", () => {
    expect(dataColor("rainfall", 0, true)).toBe("var(--color-data-rain-6)");
    expect(dataColor("rainfall", 6, true)).toBe("var(--color-data-rain-0)");
    expect(dataColor("rainfall", 3, true)).toBe("var(--color-data-rain-3)");
  });

  it("falls back to the no-data colour", () => {
    expect(dataColor("temperature", null)).toBe(NO_DATA);
    expect(dataColor("temperature", 7)).toBe(NO_DATA);
    expect(dataColor("temperature", -1)).toBe(NO_DATA);
    expect(dataColor("temperature", 2.5)).toBe(NO_DATA);
  });

  it("lists seven classes in order", () => {
    expect(rampColors("rainfall")).toHaveLength(7);
    expect(rampColors("rainfall", true)[0]).toBe("var(--color-data-rain-6)");
  });

  it("only names variables the theme defines in light and dark", () => {
    const css = readFileSync(new URL("../../styles/theme.css", import.meta.url), "utf8");
    const names = [...rampColors("temperature"), ...rampColors("rainfall"), NO_DATA].map((v) => v.slice(4, -1));
    for (const name of names) {
      expect(css.match(new RegExp(`${name}:\\s*#[0-9a-f]{6};`, "g"))).toHaveLength(2);
    }
  });
});
