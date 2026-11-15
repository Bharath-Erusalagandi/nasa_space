import type { KeyboardEvent } from "react";
import type { GeoProjection } from "d3-geo";
import { around, placeLabel, textWidth, type Box, type Placed } from "@/lib/map/labels";
import { project, type Point, type Size, type View } from "@/lib/map/projection";
import type { Place } from "@/lib/trends/types";
import { cx } from "@/utils/cx";

// a surface-coloured halo so labels stay legible over cells and roads
export const HALO = "[paint-order:stroke] stroke-background-primary-default [stroke-width:3px] [stroke-linejoin:round]";

// other towns from OpenStreetMap appear once the map is zoomed in, so the five reference towns stay clear
export const MINOR_TOWNS_FROM = 2;

export type ContextLabel = { name: string; lon: number; lat: number; kind: "town" | "country" };

type Geo = { projection: GeoProjection; view: View; size: Size };

export type Layout = {
  towns: Map<string, Placed>;
  minor: { label: ContextLabel; at: Point; text: Placed }[];
  selected: { place: Place; at: Point; text: Placed } | null;
  pod: { at: Point; text: Placed } | null;
};

const activate = (fn: () => void) => (event: KeyboardEvent) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  fn();
};

const inside = ([x, y]: Point, size: Size, pad = 0) => x >= -pad && y >= -pad && x <= size.width + pad && y <= size.height + pad;

const POD_RISE = 24;
const podSquare = ([x, y]: Point): Box => ({ x: x - 4, y: y - POD_RISE - 4, width: 8, height: 8 });

// the selected name goes first, then the pod id, then towns in order, each one kept off every dot and every label before it
export function layoutLabels(places: Place[], context: ContextLabel[], selectedId: string | null, podId: string | null, { projection, view, size }: Geo): Layout {
  const at = (p: { lon: number; lat: number }) => project(projection, view, p.lon, p.lat);
  const visible = places.filter((p) => p.kind !== "cell" && inside(at(p), size, 8));
  const obstacles: Box[] = visible.map((p) => around(at(p), p.kind === "town" ? 5 : 3.5));
  const place = (point: Point, text: string, px: number, gap: number) => {
    const placed = placeLabel(point, { width: textWidth(text, px), height: Math.round(px * 1.25) }, obstacles, size, gap);
    obstacles.push(placed.box);
    return placed;
  };

  const chosen = places.find((p) => p.id === selectedId);
  let selected: Layout["selected"] = null;
  let pod: Layout["pod"] = null;
  if (chosen) {
    const point = at(chosen);
    obstacles.push(around(point, 11));
    if (podId) obstacles.push(podSquare(point));
    selected = { place: chosen, at: point, text: place(point, chosen.name, 15, 14) };
    if (podId) pod = { at: point, text: place([point[0], point[1] - POD_RISE], podId, 12, 9) };
  }

  const towns = new Map<string, Placed>();
  for (const p of visible) if (p.kind === "town" && p.id !== selectedId) towns.set(p.id, place(at(p), p.name, 12.5, 8));

  const minor: Layout["minor"] = [];
  if (view.k >= MINOR_TOWNS_FROM) {
    for (const label of context) {
      if (label.kind !== "town") continue;
      const point = at(label);
      if (!inside(point, size, -24)) continue;
      obstacles.push(around(point, 2.5));
      minor.push({ label, at: point, text: place(point, label.name, 11, 6) });
    }
  }
  return { towns, minor, selected, pod };
}

function Countries({ labels, projection, view, size }: { labels: ContextLabel[] } & Geo) {
  return (
    <g aria-hidden className="pointer-events-none">
      {labels.map((l) => {
        if (l.kind !== "country") return null;
        const p = project(projection, view, l.lon, l.lat);
        const half = l.name.length * 3.5;
        if (!inside(p, size, -24) || p[0] - half < 4 || p[0] + half > size.width - 4) return null;
        return (
          <text key={l.name} x={p[0]} y={p[1]} textAnchor="middle" className={cx("fill-text-tertiary text-caption-1-regular", HALO)}>
            {l.name}
          </text>
        );
      })}
    </g>
  );
}

function MinorTowns({ minor }: { minor: Layout["minor"] }) {
  return (
    <g aria-hidden className="pointer-events-none">
      {minor.map(({ label, at, text }) => (
        <g key={label.name}>
          <circle cx={at[0]} cy={at[1]} r={1.75} className="fill-text-tertiary" />
          <text x={text.x} y={text.y} dy="0.35em" textAnchor={text.anchor} className={cx("fill-text-tertiary text-caption-2-regular", HALO)}>
            {label.name}
          </text>
        </g>
      ))}
    </g>
  );
}

type Props = Geo & {
  places: Place[];
  context: ContextLabel[];
  layout: Layout;
  showFacilities?: boolean;
  onSelect: (id: string) => void;
};

export function PlaceLayer({ places, context, layout, projection, view, size, showFacilities = true, onSelect }: Props) {
  const facilities = showFacilities ? places.filter((p) => p.kind === "facility") : [];
  const towns = places.filter((p) => p.kind === "town");
  const at = (p: Place) => project(projection, view, p.lon, p.lat);

  return (
    <g>
      <Countries labels={context} projection={projection} view={view} size={size} />
      <MinorTowns minor={layout.minor} />
      <g data-layer="facilities">
        {facilities.map((place) => {
          const [x, y] = at(place);
          if (!inside([x, y], size, 8)) return null;
          return (
            <g
              key={place.id}
              role="button"
              tabIndex={0}
              aria-label={`${place.name}${place.type ? `, ${place.type}` : ""}`}
              data-place={place.id}
              className="group cursor-pointer outline-none"
              onClick={() => onSelect(place.id)}
              onKeyDown={activate(() => onSelect(place.id))}
            >
              <circle cx={x} cy={y} r={7} className="fill-transparent" />
              <circle cx={x} cy={y} r={6} className="fill-background-primary-default stroke-text-primary opacity-0 [stroke-width:1.5px] group-hover:opacity-100" />
              <circle cx={x} cy={y} r={2.5} className="fill-text-secondary stroke-background-primary-default [stroke-width:1px] group-hover:fill-text-primary" />
              <circle cx={x} cy={y} r={6} className="fill-none stroke-border-focus-ring opacity-0 [stroke-width:2px] group-focus-visible:opacity-100" />
            </g>
          );
        })}
      </g>
      <g data-layer="towns">
        {towns.map((place) => {
          const [x, y] = at(place);
          if (!inside([x, y], size, 8)) return null;
          const label = layout.towns.get(place.id);
          return (
            <g
              key={place.id}
              role="button"
              tabIndex={0}
              aria-label={place.name}
              data-place={place.id}
              className="group cursor-pointer outline-none"
              onClick={() => onSelect(place.id)}
              onKeyDown={activate(() => onSelect(place.id))}
            >
              <circle cx={x} cy={y} r={9} className="fill-transparent" />
              <circle cx={x} cy={y} r={8} className="fill-background-primary-default stroke-text-primary opacity-0 [stroke-width:1.5px] group-hover:opacity-100" />
              <circle cx={x} cy={y} r={3.5} className="fill-text-primary stroke-background-primary-default [stroke-width:1.5px]" />
              {label ? (
                <text x={label.x} y={label.y} dy="0.35em" textAnchor={label.anchor} data-town-label={place.id} className={cx("fill-text-primary text-caption-1-medium", HALO)}>
                  {place.name}
                </text>
              ) : null}
              <circle cx={x} cy={y} r={7} className="fill-none stroke-border-focus-ring opacity-0 [stroke-width:2px] group-focus-visible:opacity-100" />
            </g>
          );
        })}
      </g>
    </g>
  );
}

export function SelectedPlace({ selected }: { selected: Layout["selected"] }) {
  if (!selected) return null;
  const { place, at, text } = selected;
  const [x, y] = at;
  return (
    <g data-selected-place={place.id} aria-hidden className="pointer-events-none">
      {/* a slow ring that spreads from the selected place, so the eye finds it on a busy map */}
      <circle cx={x} cy={y} r={8} data-pulse className="origin-center fill-none stroke-text-primary opacity-60 [stroke-width:1.5px] [transform-box:fill-box] motion-safe:animate-ping motion-reduce:hidden" />
      <circle cx={x} cy={y} r={8} className="fill-none stroke-background-primary-default [stroke-width:4px]" />
      <circle cx={x} cy={y} r={8} className="fill-none stroke-text-primary [stroke-width:2px]" />
      <circle cx={x} cy={y} r={2.5} className="fill-text-primary" />
      <text x={text.x} y={text.y} dy="0.35em" textAnchor={text.anchor} data-selected-label className={cx("fill-text-primary text-body-semibold", HALO)}>
        {place.name}
      </text>
    </g>
  );
}

export function PodMarker({ pod, podId, place }: { pod: Layout["pod"]; podId: string; place: Place | undefined }) {
  if (!pod || !place) return null;
  const square = podSquare(pod.at);
  return (
    <g data-pod-marker aria-label={`Pod ${podId} at ${place.name}`} role="img" className="pointer-events-none">
      <line x1={pod.at[0]} y1={pod.at[1] - 11} x2={pod.at[0]} y2={square.y + square.height} className="stroke-text-primary [stroke-width:1px]" />
      <rect {...square} className="fill-text-primary stroke-background-primary-default [stroke-width:1.5px]" />
      <text x={pod.text.x} y={pod.text.y} dy="0.35em" textAnchor={pod.text.anchor} className={cx("fill-text-primary text-caption-1-semibold", HALO)}>
        {podId}
      </text>
    </g>
  );
}
