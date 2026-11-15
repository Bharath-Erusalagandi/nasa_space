import { describe, expect, it } from "vitest";
import { DEFAULT_LAYERS, drawsRelief, OVERLAYS, reliefLock, riversInBlue, shownCount, withGround, withOverlay } from "./layers";

describe("map layers", () => {
  it("starts on the climate trend with every overlay on", () => {
    expect(DEFAULT_LAYERS.ground).toBe("trend");
    expect(shownCount(DEFAULT_LAYERS)).toBe(OVERLAYS.length);
  });

  it("switches one overlay and leaves the rest", () => {
    const next = withOverlay(DEFAULT_LAYERS, "roads", false);
    expect(next.overlays.roads).toBe(false);
    expect(shownCount(next)).toBe(OVERLAYS.length - 1);
    expect(DEFAULT_LAYERS.overlays.roads).toBe(true);
  });

  it("does not draw the grey relief under the elevation colours, which already hold it", () => {
    expect(drawsRelief(DEFAULT_LAYERS)).toBe(true);
    expect(drawsRelief(withGround(DEFAULT_LAYERS, "elevation"))).toBe(false);
    expect(drawsRelief(withOverlay(DEFAULT_LAYERS, "relief", false))).toBe(false);
  });

  it("keeps rivers grey on the trend map, where blue is a data colour", () => {
    expect(riversInBlue(DEFAULT_LAYERS)).toBe(false);
    expect(riversInBlue(withGround(DEFAULT_LAYERS, "elevation"))).toBe(true);
    expect(riversInBlue(withGround(DEFAULT_LAYERS, "none"))).toBe(true);
  });

  it("locks the hill shading on the grounds that carry their own relief", () => {
    expect(reliefLock("trend")).toBeNull();
    expect(reliefLock("none")).toBeNull();
    expect(reliefLock("elevation")?.on).toBe(true);
    expect(reliefLock("satellite")?.on).toBe(false);
    expect(drawsRelief(withGround(DEFAULT_LAYERS, "satellite"))).toBe(false);
  });
});
