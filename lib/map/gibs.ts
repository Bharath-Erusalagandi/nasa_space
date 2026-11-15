import type { Frame } from "@/lib/trends/types";

// A real NASA satellite picture of the province, from NASA's Global Imagery Browse Services (GIBS).
// This is the one thing the map asks the internet for, and only when the Satellite ground is chosen.

export const GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi";

// MODIS on the Terra satellite, true colour. 20 August 2025 is a dry-season day with almost no cloud over the province.
export const SATELLITE = {
  layer: "MODIS_Terra_CorrectedReflectance_TrueColor",
  date: "2025-08-20",
  words: "MODIS Terra true colour, 20 August 2025",
} as const;

const R = 6378137;

// Web Mercator metres, the projection GIBS serves and the map draws in
export function mercator(lon: number, lat: number): [number, number] {
  return [R * ((lon * Math.PI) / 180), R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];
}

export function satelliteUrl(frame: Frame, width = 1400): string {
  const [west, south] = mercator(frame.west, frame.south);
  const [east, north] = mercator(frame.east, frame.north);
  const height = Math.max(1, Math.round((width * (north - south)) / (east - west)));
  const query = new URLSearchParams({
    SERVICE: "WMS",
    REQUEST: "GetMap",
    VERSION: "1.3.0",
    LAYERS: SATELLITE.layer,
    STYLES: "",
    CRS: "EPSG:3857",
    BBOX: [west, south, east, north].map((v) => v.toFixed(1)).join(","),
    WIDTH: String(width),
    HEIGHT: String(height),
    FORMAT: "image/jpeg",
    TIME: SATELLITE.date,
  });
  return `${GIBS_WMS}?${query}`;
}
