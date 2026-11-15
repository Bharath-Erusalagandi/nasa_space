import { describe, expect, it } from "vitest";
import type { FeatureCollection } from "@/lib/trends/types";
import { geoArea } from "d3-geo";
import { basePaths, linePath, rewind, roadClass } from "./paths";
import { fitProjection } from "./projection";

const frame = { west: 29.7283, south: -15.2479, east: 33.7996, north: -11.3252 };
const size = { width: 800, height: 700 };

const collection = (features: FeatureCollection["features"]): FeatureCollection => ({ type: "FeatureCollection", features });
const line = (props: Record<string, unknown>, coordinates: number[][]) => ({
  type: "Feature" as const,
  properties: props,
  geometry: { type: "LineString", coordinates },
});

describe("paths", () => {
  const empty = collection([]);
  const layers = {
    province: empty,
    districts: empty,
    rivers: collection([line({ name: "Luangwa" }, [[31, -13], [31.5, -13.5]])]),
    roads: collection([
      line({ class: "trunk" }, [[32, -13], [32.5, -13.5]]),
      line({ class: "tertiary" }, [[30, -14], [30.5, -14.5]]),
      line({ class: "track" }, [[30, -12], [30.5, -12.5]]),
    ]),
    context: collection([line({ kind: "border" }, [[33, -12], [33, -14]]), { type: "Feature", properties: { kind: "country", name: "Malawi" }, geometry: { type: "Point", coordinates: [33.5, -13] } }]),
  };

  it("groups roads by class and sends unknown classes to tertiary", () => {
    const paths = basePaths(layers, fitProjection(frame, size));
    expect(paths.roads.trunk.match(/M/g)).toHaveLength(1);
    expect(paths.roads.primary).toBe("");
    expect(paths.roads.tertiary.match(/M/g)).toHaveLength(2);
    expect(paths.rivers).toMatch(/^M[\d.]+,[\d.]+L/);
    expect(paths.borders.match(/M/g)).toHaveLength(1);
    expect(roadClass(undefined)).toBe("tertiary");
  });

  it("draws a route line through its projected points", () => {
    const p = fitProjection(frame, size);
    const d = linePath(p, [[32.65, -13.63], [32.04, -14.06]]);
    const [x, y] = p([32.65, -13.63])!;
    const [mx, my] = d.slice(1, d.indexOf("L")).split(",").map(Number);
    expect(mx).toBeCloseTo(x, 0);
    expect(my).toBeCloseTo(y, 0);
    expect(d.match(/L/g)).toHaveLength(1);
  });
});

describe("rewind", () => {
  const square = (ring: number[][]) => ({ type: "Feature" as const, properties: {}, geometry: { type: "Polygon", coordinates: [ring] } });
  const ccw = [[32, -14], [33, -14], [33, -13], [32, -13], [32, -14]];

  it("turns a counter-clockwise ring so d3 reads the small shape, not the rest of the globe", () => {
    const area = (f: ReturnType<typeof square>) => geoArea(f as unknown as Parameters<typeof geoArea>[0]);
    expect(area(square(ccw))).toBeGreaterThan(2 * Math.PI);
    expect(area(rewind(square(ccw)) as ReturnType<typeof square>)).toBeLessThan(0.001);
  });

  it("leaves a clockwise ring alone", () => {
    const cw = square([...ccw].reverse());
    expect(rewind(cw)).toBe(cw);
  });
});
