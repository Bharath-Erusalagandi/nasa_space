"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { POD_ID } from "@/lib/brand";
import { attribution } from "@/lib/map/attribution";
import { basePaths, provinceFrame } from "@/lib/map/paths";
import { fitProjection, IDENTITY, unionFrame, panBy, scaleBar, zoomAt, type Size, type View } from "@/lib/map/projection";
import { getCellSummary, getPlace, missionStore, useMission, usePanelEmphasis } from "@/lib/mission/state";
import { usePod } from "@/lib/pod/store";
import { cellLayer, layerLegend, rampFor, rateUnit, type LayerCell } from "@/lib/trends/cellLayer";
import { placeForCell } from "@/lib/trends/geo";
import type { IndicatorKey } from "@/lib/trends/types";
import { MapLegend } from "./MapLegend";
import { Ground, Lines, ProvinceEdge } from "./map/BaseLayers";
import { CellBrackets, CellGround, CellLayer, CellOutlines, HATCH_ID, HatchPattern } from "./map/CellLayer";
import { DeliveryLayer } from "./map/DeliveryLayer";
import { layoutLabels, PlaceLayer, PodMarker, SelectedPlace, type ContextLabel } from "./map/PlaceLayer";
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
  const { ref, size } = useSize();
  const { view, setView, zoom, reset } = useZoom(size);
  const drag = useDragPan(size, setView);
  const svgRef = useRef<SVGSVGElement>(null);

  // fitted to the province and the NASA cells, so the map uses its half of the column
  const frame = useMemo(() => (data && index ? unionFrame(provinceFrame(data.province), index.cells.map((c) => c.bounds)) : null), [data, index]);
  const projection = useMemo(() => (frame && size ? fitProjection(frame, size) : null), [frame, size]);
  const paths = useMemo(() => (data && projection ? basePaths(data, projection) : null), [data, projection]);
  const relief = useMemo(() => {
    if (!data?.relief || !projection) return null;
    const [x0, y0] = projection([data.relief.west, data.relief.north]) ?? [0, 0];
    const [x1, y1] = projection([data.relief.east, data.relief.south]) ?? [0, 0];
    return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
  }, [data, projection]);
  const layerData = useMemo(() => (index ? cellLayer(index, layer) : null), [index, layer]);
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

  const podShown = source !== "none";
  const layout = useMemo(
    () => (index && projection && size ? layoutLabels(index.places, context, place?.id ?? null, podShown ? podId : null, { projection, view, size }) : null),
    [index, context, place, podShown, podId, projection, view, size],
  );

  const ramp = rampFor(layer);
  const legend = layerData ? layerLegend(layer, layerData.domain) : null;
  const ready = Boolean(projection && paths && size && layerData && index && layout);
  const centre = data ? { lat: (data.frame.north + data.frame.south) / 2, lon: (data.frame.west + data.frame.east) / 2 } : null;

  return (
    <PanelFrame label="Map" emphasis={emphasis} className="h-full">
      <div ref={ref} className="relative min-h-0 flex-1" data-map-ready={ready || undefined}>
        {projection && paths && size && layerData && index && layout ? (
          <svg
            ref={svgRef}
            width={size.width}
            height={size.height}
            role="group"
            aria-label="Map of Eastern Province with NASA grid cells, towns and health facilities"
            className={cx("absolute inset-0 touch-none select-none", view.k > 1 && "cursor-grab")}
            {...drag}
          >
            <defs>
              <HatchPattern id={HATCH_ID} />
            </defs>
            <CellGround cells={layerData.cells} projection={projection} view={view} />
            <Ground paths={paths} relief={relief} view={view} />
            <CellLayer
              cells={layerData.cells}
              ramp={ramp.ramp}
              reversed={ramp.reversed}
              projection={projection}
              view={view}
              describe={(cell) => describeCell(cell, layer)}
              onSelect={selectCell}
            />
            <Lines paths={paths} view={view} />
            <CellOutlines cells={layerData.cells} projection={projection} view={view} />
            <ProvinceEdge d={paths.province} view={view} />
            <CellBrackets cell={layerData.cells.find((c) => c.id === selectedCell)} projection={projection} view={view} />
            <PlaceLayer places={index.places} context={context} layout={layout} projection={projection} view={view} size={size} onSelect={selectPlace} />
            <DeliveryLayer delivery={delivery} projection={projection} view={view} />
            <SelectedPlace selected={layout.selected} />
            <PodMarker pod={layout.pod} podId={podId} place={place} />
          </svg>
        ) : (
          <Note>{error ? `The map files could not be loaded (${error}).` : "Loading the map"}</Note>
        )}
        {ready ? <ZoomControls k={view.k} onZoom={(f) => zoom(f)} onReset={reset} /> : null}
      </div>
      {legend && data ? (
        <MapLegend
          legend={legend}
          title={`${label ?? layer.replace(/_/g, " ")}: change per decade${index?.period ? `, ${index.period}` : ""}`}
          scale={projection && centre ? scaleBar(projection, view, centre.lat, centre.lon) : null}
          attribution={attribution(data.sources, index?.source ?? "")}
        />
      ) : null}
    </PanelFrame>
  );
}
