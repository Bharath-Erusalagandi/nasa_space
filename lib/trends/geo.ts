import { geoDistance } from "d3-geo";
import { cellId, powerCell } from "./powerCell";
import type { Bounds, IndexCell, Place, TrendIndex } from "./types";

export const EARTH_RADIUS_KM = 6371.0088;
const RAD = Math.PI / 180;

export function cellSizeKm(bounds: Bounds): { ns: number; ew: number } {
  const lat = (bounds.north + bounds.south) / 2;
  return {
    ns: EARTH_RADIUS_KM * (bounds.north - bounds.south) * RAD,
    ew: EARTH_RADIUS_KM * Math.cos(lat * RAD) * (bounds.east - bounds.west) * RAD,
  };
}

export function cellSizeLabel(bounds: Bounds): string {
  const { ns, ew } = cellSizeKm(bounds);
  return `about ${Math.round(ns)} x ${Math.round(ew)} km`;
}

export const distanceKm = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) =>
  geoDistance([a.lon, a.lat], [b.lon, b.lat]) * EARTH_RADIUS_KM;

export function nearestPlace<P extends Pick<Place, "lat" | "lon">>(
  places: P[],
  point: { lat: number; lon: number },
): P | undefined {
  let best: P | undefined;
  let bestKm = Infinity;
  for (const place of places) {
    const km = distanceKm(place, point);
    if (km < bestKm) [best, bestKm] = [place, km];
  }
  return best;
}

export function cellOfPlace(index: TrendIndex, place: Pick<Place, "lat" | "lon"> & { cell?: string }): IndexCell | undefined {
  const id = place.cell ?? cellId(powerCell(place.lat, place.lon));
  return index.cells.find((cell) => cell.id === id);
}

// prefers named places over the per-cell entries when one lies in the cell
export function placeForCell(index: TrendIndex, cell: IndexCell): Place | undefined {
  const centre = { lat: cell.lat, lon: cell.lon };
  const inside = index.places.filter((place) => place.cell === cell.id);
  const named = inside.filter((place) => place.kind !== "cell");
  return nearestPlace(named.length ? named : inside.length ? inside : index.places, centre);
}
