"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { POD_ID } from "@/lib/brand";
import { attribution } from "@/lib/map/attribution";
import { SATELLITE, satelliteUrl } from "@/lib/map/gibs";
import { hoverCard, type HoverTarget } from "@/lib/map/hover";
import { DEFAULT_LAYERS, drawsRelief, riversInBlue, type LayerState } from "@/lib/map/layers";
import { basePaths, provinceFrame } from "@/lib/map/paths";
import { clampView, coordinates, fitProjection, IDENTITY, project, unionFrame, panBy, scaleBar, unproject, zoomAt, type Size, type View } from "@/lib/map/projection";
import { getCellSummary, getPlace, missionStore, useMission, usePanelEmphasis } from "@/lib/mission/state";
import { usePod } from "@/lib/pod/store";
import { cellLayer, layerLegend, rampFor, rateUnit, type LayerCell } from "@/lib/trends/cellLayer";
import { placeForCell } from "@/lib/trends/geo";
import type { IndicatorKey } from "@/lib/trends/types";
import { MapLegend, ScaleBar, type ElevationRamp } from "./MapLegend";
import { Ground, Lines, ProvinceEdge } from "./map/BaseLayers";
import { CellBrackets, CellGround, CellLayer, CellOutlines, HATCH_ID, HatchPattern } from "./map/CellLayer";
import { DeliveryLayer } from "./map/DeliveryLayer";
import { HoverCard } from "./map/HoverCard";
import { MapToolbar } from "./map/MapToolbar";
import { HALO, layoutLabels, PlaceLayer, PodMarker, SelectedPlace, type ContextLabel } from "./map/PlaceLayer";
import { useMapData, type MapData } from "./map/useMapData";
import { useSize } from "./map/useSize";
import { ZoomControls } from "./map/ZoomControls";
import { Note, PanelFrame } from "./primitives";
import { cx } from "@/utils/cx";

const signed = (x: number) => `${x > 0 ? "+" : ""}${Number(x.toFixed(2))}`;

const SIGNIFICANCE = { solid: "significant after correction", dashed: "significant in this cell only", none: "not statistically significant" };

function describeCell(cell: LayerCell, key: IndicatorKey): string {
  if (cell.error) return `Grid cell ${cell.id}: no NASA data`;
  if (cell.slope === null) return `Grid cell ${cell.id}: no trend`;
  return `Grid cell ${cell.id}: ${signed(cell.slope)} ${rateUnit(key)} per decade, ${SIGNIFICANCE[cell.outline]}`;
}

function contextLabels(data: MapData, taken: Set<string>): ContextLabel[] {
  const labels: ContextLabel[] = [];
  for (const f of data.context.features) {
    if (f.properties.kind !== "country" || !f.properties.name || f.geometry.type !== "Point") continue;
    if (f.properties.name === "Zambia") continue;
    const [lon, lat] = f.geometry.coordinates as [number, number];
    labels.push({ name: f.properties.name, lon, lat, kind: "country" });
  }
  for (const f of data.towns.features) {
    if (taken.has(f.properties.name.toLowerCase()) || f.geometry.type !== "Point") continue;
    const [lon, lat] = f.geometry.coordinates as [number, number];
    labels.push({ name: f.properties.name, lon, lat, kind: "town" });
  }
  return labels;
}

type Terrain = { west: number; south: number; east: number; north: number; ramp: ElevationRamp };
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

const metres = (m: number) => `${m.toLocaleString("en-GB")} m`;

function useZoom(size: Size | null) {
  const [view, setView] = useState<View>(IDENTITY);
  const zoom = useCallback(
    (factor: number, at?: [number, number]) => {
      if (!size) return;
      setView((v) => zoomAt(v, factor, at ?? [size.width / 2, size.height / 2], size));
    },
    [size],
  );
  useEffect(() => setView(IDENTITY), [size]);
  return { view, setView, zoom, reset: () => setView(IDENTITY) };
}

function useDragPan(size: Size | null, setView: (fn: (v: View) => View) => void) {
  const start = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const dragged = useRef(false);
  return {
    onPointerDown(e: PointerEvent<SVGSVGElement>) {
      if (e.button !== 0) return;
      start.current = { x: e.clientX, y: e.clientY, moved: false };
      dragged.current = false;
    },
    onPointerMove(e: PointerEvent<SVGSVGElement>) {
      const s = start.current;
      if (!s || !size) return;
      const [dx, dy] = [e.clientX - s.x, e.clientY - s.y];
      if (!s.moved && Math.hypot(dx, dy) < 4) return;
      if (!s.moved) e.currentTarget.setPointerCapture(e.pointerId);
      s.moved = true;
      dragged.current = true;
      start.current = { x: e.clientX, y: e.clientY, moved: true };
      setView((v) => panBy(v, dx, dy, size));
    },
    onPointerUp() {
      start.current = null;
    },
    onClickCapture(e: MouseEvent) {
      if (!dragged.current) return;
      dragged.current = false;
      e.stopPropagation();
    },
  };
}

export function MissionMap() {
  const emphasis = usePanelEmphasis("map");
  const index = useMission((s) => s.index);
  const layer = useMission((s) => s.layer);
  const label = useMission((s) => s.cell?.indicators[s.layer]?.label);
  const place = useMission(getPlace);
  const selectedCell = useMission((s) => getCellSummary(s)?.id ?? null);
  const delivery = useMission((s) => s.delivery);
  const source = usePod((s) => s.source);
  const podId = usePod((s) => s.last?.pod_id ?? POD_ID);
  const { data, error } = useMapData();
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const terrain = useJson<Terrain>("/map/terrain.json");
  const contourLabels = useJson<ContourLabel[]>("/map/contour_labels.json");
  const heights = useJson<Record<string, number>>("/map/elevations.json");
  const trendShown = layers.ground === "trend";
  const elevationShown = layers.ground === "elevation" && terrain !== null;
  const satelliteShown = layers.ground === "satellite";
  const [satelliteFailed, setSatelliteFailed] = useState(false);
  const { ref, size } = useSize();
  const { view, setView, zoom, reset } = useZoom(size);
  const drag = useDragPan(size, setView);
  const svgRef = useRef<SVGSVGElement>(null);

  // fitted to the province and the NASA cells, so the map uses its half of the column
  const frame = useMemo(() => (data && index ? unionFrame(provinceFrame(data.province), index.cells.map((c) => c.bounds)) : null), [data, index]);
  const projection = useMemo(() => (frame && size ? fitProjection(frame, size, 28) : null), [frame, size]);
  const paths = useMemo(() => (data && projection ? basePaths(data, projection) : null), [data, projection]);
  const relief = useMemo(() => {
    if (!data?.relief || !projection) return null;
    const [x0, y0] = projection([data.relief.west, data.relief.north]) ?? [0, 0];
    const [x1, y1] = projection([data.relief.east, data.relief.south]) ?? [0, 0];
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }, [data, projection]);
  const elevation = useMemo(() => {
    if (!elevationShown || !terrain || !projection) return null;
    const [x0, y0] = projection([terrain.west, terrain.north]) ?? [0, 0];
    const [x1, y1] = projection([terrain.east, terrain.south]) ?? [0, 0];
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }, [elevationShown, terrain, projection]);
  const satellite = useMemo(() => {
    if (!satelliteShown || !frame || !projection) return null;
    const [x0, y0] = projection([frame.west, frame.north]) ?? [0, 0];
    const [x1, y1] = projection([frame.east, frame.south]) ?? [0, 0];
    return { href: satelliteUrl(frame), box: { x: x0, y: y0, width: x1 - x0, height: y1 - y0 }, onError: () => setSatelliteFailed(true) };
  }, [satelliteShown, frame, projection]);
  const layerData = useMemo(() => (index ? cellLayer(index, layer) : null), [index, layer]);
  const cells = layerData?.cells ?? [];
  const [hover, setHover] = useState<(HoverTarget & { x: number; y: number }) | null>(null);
  const context = useMemo(
    () => (data && index ? contextLabels(data, new Set(index.places.map((p) => p.name.toLowerCase()))) : []),
    [data, index],
  );

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const box = svg!.getBoundingClientRect();
      zoom(Math.exp(-e.deltaY * 0.002), [e.clientX - box.left, e.clientY - box.top]);
    }
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [zoom, projection]);

  const selectCell = useCallback((id: string) => {
    const s = missionStore.getState();
    const cell = s.index?.cells.find((c) => c.id === id);
    const target = s.index && cell ? placeForCell(s.index, cell) : undefined;
    if (target) s.selectPlace(target.id);
  }, []);
  const selectPlace = useCallback((id: string) => missionStore.getState().selectPlace(id), []);

  // one listener for the whole map: the thing under the pointer is found from its data attribute
  const readout = useRef<HTMLSpanElement>(null);
  const onHover = useCallback((e: PointerEvent<HTMLDivElement>) => {
    const frame = e.currentTarget.getBoundingClientRect();
    // written straight to the element: the pointer moves far more often than the map needs to redraw
    if (readout.current && projection) {
      const at = unproject(projection, view, [e.clientX - frame.left, e.clientY - frame.top]);
      readout.current.textContent = at ? coordinates(at) : "";
    }
    const el = e.target instanceof Element ? e.target.closest<SVGElement>("[data-place], [data-cell]") : null;
    const target: HoverTarget | null = el
      ? el.dataset.place
        ? { kind: "place", id: el.dataset.place }
        : { kind: "cell", id: el.dataset.cell ?? "" }
      : null;
    if (!target || e.buttons !== 0) return setHover(null);
    setHover((h) => (h && h.kind === target.kind && h.id === target.id ? h : { ...target, x: e.clientX - frame.left, y: e.clientY - frame.top }));
  }, [projection, view]);

  // centre the selected place at a zoom where its neighbours separate
  const locate = useCallback(() => {
    if (!place || !projection || !size) return;
    const k = Math.max(view.k, 3);
    const [x, y] = projection([place.lon, place.lat]) ?? [0, 0];
    setView(() => clampView({ k, x: size.width / 2 - x * k, y: size.height / 2 - y * k }, size));
  }, [place, projection, size, view.k, setView]);
  const card = useMemo(
    () =>
      hover && index
        ? hoverCard(hover, {
            index,
            key: layer,
            label: label ?? layer.replace(/_/g, " "),
            heights,
            climate: trendShown,
          })
        : null,
    [hover, index, layer, label, heights, trendShown],
  );

  const podShown = source !== "none";
  // hidden facilities take no room, so the labels do not dodge dots that are not drawn
  const places = useMemo(
    () => (index ? (layers.overlays.facilities ? index.places : index.places.filter((p) => p.kind !== "facility" || p.id === place?.id)) : []),
    [index, layers.overlays.facilities, place],
  );
  const layout = useMemo(
    () => (index && projection && size ? layoutLabels(places, context, place?.id ?? null, podShown ? podId : null, { projection, view, size }) : null),
    [index, places, context, place, podShown, podId, projection, view, size],
  );

  const ramp = rampFor(layer);
  const legend = layerData && trendShown ? layerLegend(layer, layerData.domain) : null;
  const height = place && heights ? heights[place.id] : undefined;
  const title = trendShown
    ? `${label ?? layer.replace(/_/g, " ")}: change per decade${index?.period ? `, ${index.period}` : ""}`
    : elevationShown
      ? "Elevation above sea level"
      : satelliteShown
        ? satelliteFailed
          ? "The NASA satellite picture could not be loaded. It needs an internet connection."
          : `NASA satellite picture: ${SATELLITE.words}, from NASA GIBS`
      : "Eastern Province, Zambia";
  const ready = Boolean(projection && paths && size && layerData && index && layout);
  const centre = data ? { lat: (data.frame.north + data.frame.south) / 2, lon: (data.frame.west + data.frame.east) / 2 } : null;

  const scale = projection && centre ? scaleBar(projection, view, centre.lat, centre.lon) : null;

  return (
    <PanelFrame
      label="Map"
      descriptor="Map of Eastern Province, Zambia"
      right={
        place ? (
          <p className="text-caption-1-medium text-text-secondary tabular-nums" data-map-place>
            {place.name}
            {height !== undefined ? ` · ${metres(height)}` : ""}
          </p>
        ) : null
      }
      emphasis={emphasis}
      className="h-full"
    >
      <div
        ref={ref}
        className="relative min-h-0 flex-1 overflow-hidden rounded-3xl border border-border-button-default bg-background-secondary-default"
        data-map-ready={ready || undefined}
        onPointerMove={onHover}
        onPointerLeave={() => {
          setHover(null);
          if (readout.current) readout.current.textContent = "";
        }}
      >
        {projection && paths && size && layerData && index && layout ? (
          <svg
            ref={svgRef}
            width={size.width}
            height={size.height}
            role="group"
            aria-label="Map of Eastern Province with NASA grid cells, towns and health facilities"
            className={cx("absolute inset-0 touch-none select-none", view.k > 1 && "cursor-grab active:cursor-grabbing")}
            onDoubleClick={(e) => {
              const box = e.currentTarget.getBoundingClientRect();
              zoom(e.shiftKey ? 1 / 1.8 : 1.8, [e.clientX - box.left, e.clientY - box.top]);
            }}
            {...drag}
          >
            <defs>
              <HatchPattern id={HATCH_ID} />
            </defs>
            {trendShown ? <CellGround cells={cells} projection={projection} view={view} /> : null}
            <Ground paths={paths} relief={drawsRelief(layers) ? relief : null} elevation={elevation} satellite={satellite} view={view} />
            {trendShown ? (
              <CellLayer
                cells={cells}
                ramp={ramp.ramp}
                reversed={ramp.reversed}
                projection={projection}
                view={view}
                describe={(cell) => describeCell(cell, layer)}
                onSelect={selectCell}
              />
            ) : null}
            <Lines paths={paths} view={view} show={{ ...layers.overlays, riversBlue: riversInBlue(layers) }} />
            {trendShown ? <CellOutlines cells={cells} projection={projection} view={view} /> : null}
            <ProvinceEdge d={paths.province} view={view} />
            {trendShown ? <CellBrackets cell={cells.find((c) => c.id === selectedCell)} projection={projection} view={view} /> : null}
            {elevationShown && layers.overlays.contours ? (
              <g data-contour-labels aria-hidden className="pointer-events-none">
                {(contourLabels ?? []).map((l) => {
                  const [x, y] = project(projection, view, l.lon, l.lat);
                  return (
                    <text key={`${l.elev}-${l.lon}`} x={x} y={y} textAnchor="middle" dy="0.32em" className={cx("fill-text-secondary text-caption-2-semibold tabular-nums", HALO)}>
                      {l.elev}
                    </text>
                  );
                })}
              </g>
            ) : null}
            <PlaceLayer places={places} context={context} layout={layout} projection={projection} view={view} size={size} showFacilities={layers.overlays.facilities} onSelect={selectPlace} />
            <DeliveryLayer delivery={delivery} projection={projection} view={view} />
            <SelectedPlace selected={layout.selected} />
            <PodMarker pod={layout.pod} podId={podId} place={place} />
          </svg>
        ) : (
          <Note>{error ? `The map files could not be loaded (${error}).` : "Loading the map"}</Note>
        )}
        {ready ? (
          <ZoomControls k={view.k} onZoom={(f) => zoom(f)} onReset={reset} onLocate={place ? locate : undefined} locateLabel={place ? `Zoom to ${place.name}` : undefined} />
        ) : null}
        {ready ? <MapToolbar layers={layers} onChange={setLayers} /> : null}
        {ready && scale ? (
          <div
            className="pointer-events-none absolute start-3 bottom-3 flex items-center gap-3 rounded-lg border border-border-button-default bg-background-primary-default px-2.5 py-1.5 shadow-sm"
            data-map-status
          >
            <ScaleBar {...scale} />
            <span ref={readout} className="min-w-28 text-caption-1-medium text-text-secondary tabular-nums empty:hidden" />
          </div>
        ) : null}
        {ready && card && hover && size ? <HoverCard card={card} at={hover} size={size} /> : null}
      </div>
      {data && (legend || !trendShown) ? (
        <MapLegend
          legend={legend}
          elevation={elevationShown ? terrain?.ramp : null}
          title={title}
          scale={null}
          attribution={attribution(data.sources, index?.source ?? "")}
        />
      ) : null}
    </PanelFrame>
  );
}
