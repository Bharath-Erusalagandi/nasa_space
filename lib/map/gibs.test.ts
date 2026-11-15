import { describe, expect, it } from "vitest";
import { GIBS_WMS, mercator, SATELLITE, satelliteUrl } from "./gibs";

const frame = { west: 29.5, south: -15.5, east: 34, north: -10.8 };

describe("NASA GIBS satellite picture", () => {
  it("puts the equator and the prime meridian at zero and south below it", () => {
    expect(mercator(0, 0)[0]).toBeCloseTo(0, 6);
    expect(mercator(0, 0)[1]).toBeCloseTo(0, 6);
    expect(mercator(180, 0)[0]).toBeCloseTo(20037508.34, 1);
    expect(mercator(32, -14)[1]).toBeLessThan(0);
  });

  it("asks NASA for the dated MODIS layer over exactly the map's frame", () => {
    const url = new URL(satelliteUrl(frame, 700));
    expect(`${url.origin}${url.pathname}`).toBe(GIBS_WMS);
    expect(url.searchParams.get("LAYERS")).toBe(SATELLITE.layer);
    expect(url.searchParams.get("TIME")).toBe("2025-08-20");
    expect(url.searchParams.get("CRS")).toBe("EPSG:3857");
    const [west, south, east, north] = url.searchParams.get("BBOX")!.split(",").map(Number);
    expect(west).toBeCloseTo(mercator(29.5, 0)[0], 0);
    expect(east).toBeCloseTo(mercator(34, 0)[0], 0);
    expect(south).toBeLessThan(north);
  });

  it("keeps the picture's shape the same as the frame's, so it is not stretched", () => {
    const url = new URL(satelliteUrl(frame, 700));
    const [west, south, east, north] = url.searchParams.get("BBOX")!.split(",").map(Number);
    const ratio = Number(url.searchParams.get("HEIGHT")) / Number(url.searchParams.get("WIDTH"));
    expect(ratio).toBeCloseTo((north - south) / (east - west), 2);
  });
});
