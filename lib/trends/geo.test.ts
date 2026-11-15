import { describe, expect, test } from "vitest";
import { index, indexCell } from "./__fixtures__/trends";
import { cellSizeKm, cellSizeLabel, distanceKm, nearestPlace, placeForCell } from "./geo";

const katete = { south: -14.25, north: -13.75, west: 31.5625, east: 32.1875 };
const sample = index([indexCell("-14.000_31.875", -14, 31.875, {}), indexCell("-13.500_32.500", -13.5, 32.5, {}), indexCell("-12.000_33.125", -12, 33.125, {})]);

describe("geo", () => {
  test("cell size in km from its bounds", () => {
    const { ns, ew } = cellSizeKm(katete);
    expect(ns).toBeCloseTo(55.6, 1);
    expect(ew).toBeCloseTo(67.4, 1);
    expect(cellSizeLabel(katete)).toBe("about 56 x 67 km");
  });

  test("east-west size shrinks away from the equator", () => {
    const equator = cellSizeKm({ south: -0.25, north: 0.25, west: 0, east: 0.625 });
    expect(equator.ew).toBeGreaterThan(cellSizeKm(katete).ew);
  });

  test("distance between two towns", () => {
    expect(distanceKm({ lat: -14.06, lon: 32.04 }, { lat: -13.63, lon: 32.65 })).toBeCloseTo(81, 0);
  });

  test("nearest place to a point", () => {
    expect(nearestPlace(sample.places, { lat: -13.7, lon: 32.6 })?.id).toBe("chipata");
    expect(nearestPlace([], { lat: 0, lon: 0 })).toBeUndefined();
  });

  test("a cell selects the nearest named place inside it", () => {
    expect(placeForCell(sample, sample.cells[0])?.id).toBe("katete-clinic");
    expect(placeForCell(sample, sample.cells[1])?.id).toBe("chipata");
    expect(placeForCell(sample, sample.cells[2])?.id).toBe("chipata");
  });
});
