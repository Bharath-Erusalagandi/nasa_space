import { describe, expect, it } from "vitest";
import { unionFrame, clampView, fitProjection, frameBox, IDENTITY, MAX_ZOOM, panBy, project, scaleBar, zoomAt } from "./projection";

const frame = { west: 29.7283, south: -15.2479, east: 33.7996, north: -11.3252 };
const size = { width: 800, height: 700 };

describe("fitProjection", () => {
  it("fits the frame inside the margin and touches it on one axis", () => {
    const p = fitProjection(frame, size, 16);
    const [x0, y0, x1, y1] = frameBox(p, frame);
    for (const v of [x0, y0]) expect(v).toBeGreaterThanOrEqual(16 - 1e-6);
    expect(x1).toBeLessThanOrEqual(size.width - 16 + 1e-6);
    expect(y1).toBeLessThanOrEqual(size.height - 16 + 1e-6);
    const touches = Math.abs(x1 - x0 - (size.width - 32)) < 0.01 || Math.abs(y1 - y0 - (size.height - 32)) < 0.01;
    expect(touches).toBe(true);
  });

  it("puts the north edge above the south edge", () => {
    const p = fitProjection(frame, size);
    expect(project(p, IDENTITY, 32, -12)[1]).toBeLessThan(project(p, IDENTITY, 32, -15)[1]);
  });
});

describe("zoom", () => {
  it("keeps the point under the cursor fixed", () => {
    const v = zoomAt(IDENTITY, 2, [200, 300], size);
    expect(v.k).toBe(2);
    expect(v.x + 200 * v.k).toBeCloseTo(200);
    expect(v.y + 300 * v.k).toBeCloseTo(300);
  });

  it("clamps the zoom level", () => {
    expect(zoomAt(IDENTITY, 0.5, [0, 0], size).k).toBe(1);
    expect(zoomAt({ k: 6, x: 0, y: 0 }, 4, [0, 0], size).k).toBe(MAX_ZOOM);
  });

  it("never pans the map out of the viewport", () => {
    expect(panBy(IDENTITY, 50, 50, size)).toEqual({ k: 1, x: 0, y: 0 });
    const v = panBy({ k: 2, x: -100, y: -100 }, -2000, 2000, size);
    expect(v).toEqual({ k: 2, x: -800, y: 0 });
    expect(clampView({ k: 2, x: -900, y: -800 }, size)).toEqual({ k: 2, x: -800, y: -700 });
  });
});

describe("scaleBar", () => {
  it("picks a round distance that fits and doubles in pixels when zoomed in twice", () => {
    const p = fitProjection(frame, size);
    const one = scaleBar(p, IDENTITY, -13.3, 31.8, 120)!;
    expect([1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500]).toContain(one.km);
    expect(one.px).toBeLessThanOrEqual(120);
    const two = scaleBar(p, { k: 2, x: 0, y: 0 }, -13.3, 31.8, 1e6)!;
    const ref = scaleBar(p, IDENTITY, -13.3, 31.8, 1e6)!;
    expect(two.px / two.km).toBeCloseTo((2 * ref.px) / ref.km);
  });
});

describe("unionFrame", () => {
  it("grows the frame to hold every cell and never shrinks it", () => {
    const cells = [
      { west: 33.4375, east: 34.0625, south: -12.75, north: -12.25 },
      { west: 31, east: 31.5, south: -14, north: -13.5 },
    ];
    expect(unionFrame(frame, cells)).toEqual({ ...frame, east: 34.0625 });
  });
});
