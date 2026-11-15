"use client";

import { useEffect, useMemo, useState } from "react";
import { basePaths, provinceFrame } from "@/lib/map/paths";
import { fitProjection, IDENTITY, scaleBar } from "@/lib/map/projection";
import { getPlace, useMission } from "@/lib/mission/state";
import { cx } from "@/utils/cx";
import { ScaleBar } from "./MapLegend";
import { useMapData } from "./map/useMapData";
import { useSize } from "./map/useSize";
import { Note, PanelFrame } from "./primitives";

type Terrain = { west: number; south: number; east: number; north: number; ramp: { m: number; colour: string }[] };
type ContourLabel = { elev: number; lon: number; lat: number };

// files written by mapdata/terrain.py; the map draws without them if they are missing
function useJson<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    fetch(path)
      .then((r) => (r.ok ? (r.json() as Promise<T>) : null))
      .then((d) => live && setData(d))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [path]);
  return data;
}

const line = "fill-none [vector-effect:non-scaling-stroke] [stroke-linejoin:round] [stroke-linecap:round]";
const halo = "[paint-order:stroke] stroke-background-primary-default [stroke-width:3px] [stroke-linejoin:round]";
const metres = (m: number) => `${m.toLocaleString("en-GB")} m`;

function Legend({ ramp, scale }: { ramp: Terrain["ramp"]; scale: { km: number; px: number } | null }) {
  const low = ramp[0].m;
  const high = ramp[ramp.length - 1].m;
  const stops = ramp.map((r) => `${r.colour} ${(((r.m - low) / (high - low)) * 100).toFixed(1)}%`).join(", ");
  return (
    <footer className="flex flex-col gap-1" aria-label="Terrain legend">
      <div className="flex items-center gap-3 text-caption-1-medium text-text-secondary tabular-nums">
        <span className="shrink-0">Elevation</span>
        <span className="shrink-0">{metres(low)}</span>
        <span className="h-2 min-w-16 flex-1 rounded-xs" style={{ background: `linear-gradient(to right, ${stops})` }} aria-hidden />
        <span className="shrink-0">{metres(high)}</span>
        {scale ? <ScaleBar {...scale} /> : null}
      </div>
      <Note>Contours every 100 m, labels every 500 m. Copernicus DEM GLO-90.</Note>
    </footer>
  );
}

// the same province, frame and projection as the climate map, coloured by height
export function TerrainMap() {
  const index = useMission((s) => s.index);
  const place = useMission(getPlace);
  const { data } = useMapData();
  const terrain = useJson<Terrain>("/map/terrain.json");
  const labels = useJson<ContourLabel[]>("/map/contour_labels.json");
  const heights = useJson<Record<string, number>>("/map/elevations.json");
  const { ref, size } = useSize();

  // fitted to the province itself, so the terrain fills its half
  const frame = useMemo(() => (data ? provinceFrame(data.province) : null), [data]);
  const projection = useMemo(() => (frame && size ? fitProjection(frame, size) : null), [frame, size]);
  const paths = useMemo(() => (data && projection ? basePaths(data, projection) : null), [data, projection]);
  const image = useMemo(() => {
    if (!terrain || !projection) return null;
    const [x0, y0] = projection([terrain.west, terrain.north]) ?? [0, 0];
    const [x1, y1] = projection([terrain.east, terrain.south]) ?? [0, 0];
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }, [terrain, projection]);

  const at = (lon: number, lat: number) => projection?.([lon, lat]) ?? [0, 0];
  const towns = (index?.places ?? []).filter((t) => t.kind === "town").map((t) => at(t.lon, t.lat));
  const height = place && heights ? heights[place.id] : undefined;
  const centre = data ? { lat: (data.frame.north + data.frame.south) / 2, lon: (data.frame.west + data.frame.east) / 2 } : null;

  return (
    <PanelFrame label="Terrain" className="h-full">
      <div ref={ref} className="relative min-h-0 flex-1" data-terrain-ready={(projection && paths && size) || undefined}>
        {projection && paths && size && data ? (
          <svg width={size.width} height={size.height} role="img" aria-label="Terrain of Eastern Province: elevation, contours, rivers and towns" className="absolute inset-0">
            <defs>
              <clipPath id="terrain-province">
                <path d={paths.province} />
              </clipPath>
            </defs>
            <path d={paths.province} className="fill-background-secondary-default" />
            {image ? <image href="/map/terrain.webp" {...image} preserveAspectRatio="none" /> : null}
            <g clipPath="url(#terrain-province)">
              <path d={paths.contours.minor} className={cx(line, "stroke-text-primary opacity-20 [stroke-width:0.5px]")} />
              <path d={paths.contours.major} className={cx(line, "stroke-text-primary opacity-40 [stroke-width:0.9px]")} />
              <path d={paths.rivers} className={cx(line, "stroke-chart-1 opacity-70 [stroke-width:0.7px]")} />
              <path d={`${paths.roads.primary}${paths.roads.trunk}`} className={cx(line, "stroke-text-primary opacity-50 [stroke-width:1px]")} />
            </g>
            <path d={paths.province} className={cx(line, "stroke-text-secondary [stroke-width:1.5px]")} />
            {(labels ?? []).map((l) => {
              const [x, y] = at(l.lon, l.lat);
              if (towns.some(([tx, ty]) => Math.abs(tx + 20 - x) < 45 && Math.abs(ty - y) < 14)) return null;
              return (
                <text key={`${l.elev}-${l.lon}`} x={x} y={y} textAnchor="middle" dy="0.32em" className={cx("fill-text-secondary text-caption-2-semibold tabular-nums", halo)}>
                  {l.elev}
                </text>
              );
            })}
            {(index?.places ?? [])
              .filter((t) => t.kind === "town" && t.id !== place?.id)
              .map((t) => {
                const [x, y] = at(t.lon, t.lat);
                return (
                  <g key={t.id}>
                    <circle cx={x} cy={y} r={2.5} className="fill-text-primary" />
                    <text x={x + 5} y={y} dy="0.32em" className={cx("fill-text-primary text-caption-1-medium", halo)}>
                      {t.name}
                    </text>
                  </g>
                );
              })}
            {place ? (
              <g data-terrain-place>
                <circle cx={at(place.lon, place.lat)[0]} cy={at(place.lon, place.lat)[1]} r={6} className="fill-none stroke-text-primary [stroke-width:2px]" />
                <text
                  x={at(place.lon, place.lat)[0]}
                  y={at(place.lon, place.lat)[1] - 12}
                  textAnchor="middle"
                  className={cx("fill-text-primary text-caption-1-semibold tabular-nums", halo)}
                >
                  {height !== undefined ? `${place.name}, ${metres(height)}` : place.name}
                </text>
              </g>
            ) : null}
          </svg>
        ) : (
          <Note>Loading the terrain</Note>
        )}
      </div>
      {terrain ? <Legend ramp={terrain.ramp} scale={projection && centre ? scaleBar(projection, IDENTITY, centre.lat, centre.lon, 80) : null} /> : null}
    </PanelFrame>
  );
}
