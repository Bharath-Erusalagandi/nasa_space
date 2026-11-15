// what the one map can show: one ground colour at a time, and any mix of the overlays above it

export const GROUNDS = [
  { id: "trend", label: "Trend" },
  { id: "elevation", label: "Elevation" },
  { id: "satellite", label: "Satellite" },
  { id: "none", label: "Plain" },
] as const;
export type Ground = (typeof GROUNDS)[number]["id"];

export const OVERLAYS = [
  { id: "relief", label: "Hill shading", source: "Copernicus DEM" },
  { id: "contours", label: "Contours, every 100 m", source: "Copernicus DEM" },
  { id: "rivers", label: "Rivers", source: "OpenStreetMap" },
  { id: "roads", label: "Roads", source: "OpenStreetMap" },
  { id: "districts", label: "District boundaries", source: "geoBoundaries" },
  { id: "facilities", label: "Health facilities", source: "Maina et al. 2019" },
] as const;
export type Overlay = (typeof OVERLAYS)[number]["id"];

export type LayerState = { ground: Ground; overlays: Record<Overlay, boolean> };

export const DEFAULT_LAYERS: LayerState = {
  ground: "trend",
  overlays: { relief: true, contours: true, rivers: true, roads: true, districts: true, facilities: true },
};

export const withGround = (state: LayerState, ground: Ground): LayerState => ({ ...state, ground });

export const withOverlay = (state: LayerState, id: Overlay, on: boolean): LayerState => ({
  ...state,
  overlays: { ...state.overlays, [id]: on },
});

export const shownCount = (state: LayerState) => OVERLAYS.filter((o) => state.overlays[o.id]).length;

// the elevation picture already has the hillshade multiplied in, and the satellite picture shows the real ground,
// so the grey relief is drawn under neither
export const drawsRelief = (state: LayerState) => state.overlays.relief && state.ground !== "elevation" && state.ground !== "satellite";

// why the hill shading switch is locked on a ground that does not use it, or null when it is free
export function reliefLock(ground: Ground): { on: boolean; words: string } | null {
  if (ground === "elevation") return { on: true, words: "Part of the elevation colours" };
  if (ground === "satellite") return { on: false, words: "Not drawn over the satellite picture" };
  return null;
}

// on the trend map blue means "cooler" or "wetter", so rivers stay grey there and turn blue on the other grounds
export const riversInBlue = (state: LayerState) => state.ground !== "trend";
