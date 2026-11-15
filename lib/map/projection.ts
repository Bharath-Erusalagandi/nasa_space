import { geoMercator, type GeoProjection } from "d3-geo";
import { distanceKm } from "@/lib/trends/geo";
import type { Frame } from "@/lib/trends/types";

export type Size = { width: number; height: number };
export type View = { k: number; x: number; y: number };
export type Point = [number, number];

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 8;
export const IDENTITY: View = { k: 1, x: 0, y: 0 };

const corners = (f: Frame) => ({
  type: "MultiPoint" as const,
  coordinates: [
    [f.west, f.north],
    [f.east, f.north],
    [f.east, f.south],
    [f.west, f.south],
  ],
});

type Box = { west: number; south: number; east: number; north: number };

// the frame grown to hold every box, so no grid cell is cut at the map edge
export function unionFrame(frame: Frame, boxes: Box[]): Frame {
  return boxes.reduce<Frame>(
    (f, b) => ({ west: Math.min(f.west, b.west), south: Math.min(f.south, b.south), east: Math.max(f.east, b.east), north: Math.max(f.north, b.north) }),
    { west: frame.west, south: frame.south, east: frame.east, north: frame.north },
  );
}

export function fitProjection(frame: Frame, size: Size, margin = 16): GeoProjection {
  const inner: [[number, number], [number, number]] = [
    [margin, margin],
    [Math.max(margin + 1, size.width - margin), Math.max(margin + 1, size.height - margin)],
  ];
  return geoMercator().fitExtent(inner, corners(frame));
}

// the frame corners in screen pixels at zoom 1, as [x0, y0, x1, y1]
export function frameBox(projection: GeoProjection, frame: Frame): [number, number, number, number] {
  const [x0, y0] = projection([frame.west, frame.north]) ?? [0, 0];
  const [x1, y1] = projection([frame.east, frame.south]) ?? [0, 0];
  return [x0, y0, x1, y1];
}

export const clampZoom = (k: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, k));

// keeps the zoomed map covering the viewport, so it can never be panned away
export function clampView(view: View, size: Size): View {
  const k = clampZoom(view.k);
  const clamp = (v: number, extent: number) => Math.min(0, Math.max(extent - extent * k, v));
  return { k, x: clamp(view.x, size.width), y: clamp(view.y, size.height) };
}

export function zoomAt(view: View, factor: number, [px, py]: Point, size: Size): View {
  const k = clampZoom(view.k * factor);
  const ratio = k / view.k;
  return clampView({ k, x: px - (px - view.x) * ratio, y: py - (py - view.y) * ratio }, size);
}

export const panBy = (view: View, dx: number, dy: number, size: Size): View =>
  clampView({ k: view.k, x: view.x + dx, y: view.y + dy }, size);

export const applyView = (view: View, [x, y]: Point): Point => [view.x + x * view.k, view.y + y * view.k];

export function project(projection: GeoProjection, view: View, lon: number, lat: number): Point {
  return applyView(view, (projection([lon, lat]) ?? [0, 0]) as Point);
}

const NICE_KM = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500];

// the longest round distance that fits in maxPx, measured east-west at the given latitude
export function scaleBar(projection: GeoProjection, view: View, lat: number, lon: number, maxPx = 120) {
  const a = projection([lon, lat]) ?? [0, 0];
  const b = projection([lon + 1, lat]) ?? [0, 0];
  const pxPerKm = (Math.abs(b[0] - a[0]) * view.k) / distanceKm({ lat, lon }, { lat, lon: lon + 1 });
  if (!(pxPerKm > 0)) return null;
  const km = [...NICE_KM].reverse().find((d) => d * pxPerKm <= maxPx) ?? NICE_KM[0];
  return { km, px: km * pxPerKm };
}
