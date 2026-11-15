"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { TooltipTriggerStateContext } from "react-aria-components";
import { Tooltip } from "@/components/base/tooltip/tooltip";
import {
  dots as toDots,
  fullSpan,
  linear,
  pathD,
  pivot,
  rangeEnds,
  seasonLabel,
  seasonStep,
  seasonsUsed,
  seasonTicks,
  senEnds,
  valueAxis,
  type Dot,
} from "@/lib/trends/chart";
import { minusSigns, reading } from "@/lib/trends/format";
import { displayUnit, type Indicator, type Trend, type WindowChoice } from "@/lib/trends/types";
import { cx } from "@/utils/cx";

const MARGIN = { top: 32, right: 28, bottom: 32, left: 48 };
const DOT_R = 4.5;
const FADE_MS = 220;
// one tooltip, held open and anchored to whichever dot is hovered or focused
const OPEN = { isOpen: true, shouldSkipAnimation: false, open() {}, close() {} };

type Size = { width: number; height: number };
type Placed = Dot & { cx: number; cy: number };
type Layer = { key: string; ticks: { v: number; y: number }[]; dots: Placed[]; leaving?: boolean };

function useSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<Size | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setSize({ width: el.clientWidth, height: el.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

// keeps the outgoing layer mounted while it fades, so old and new dots cross-fade
function useCrossFade(layer: Layer | null) {
  const [layers, setLayers] = useState<Layer[]>(layer ? [layer] : []);
  const current = layers.at(-1);
  if (layer && current?.key !== layer.key) {
    setLayers([...layers.filter((l) => l.key !== layer.key).map((l) => ({ ...l, leaving: true })), layer]);
  } else if (layer && current && current !== layer && !current.leaving && current.key === layer.key) {
    setLayers([...layers.slice(0, -1), layer]);
  }
  useEffect(() => {
    if (!layers.some((l) => l.leaving)) return;
    const timer = setTimeout(() => setLayers((ls) => ls.filter((l) => !l.leaving)), FADE_MS);
    return () => clearTimeout(timer);
  }, [layers]);
  return layers;
}

const tickText = (v: number) => minusSigns(String(Number(v.toFixed(2)) || 0));

type Props = {
  layerKey: string;
  indicator: Indicator;
  trend: Trend | null | undefined;
  window: WindowChoice;
};

export function TrendChart({ layerKey, indicator, trend, window }: Props) {
  const [box, size] = useSize();
  const clipId = `plot-${layerKey.replace(/[^\w-]/g, "_")}`;
  const { series, unit } = indicator;
  const span = fullSpan(series);
  const used = seasonsUsed(series, window);

  const geometry = useMemo(() => {
    if (!size || !span || size.width < 120 || size.height < 80) return null;
    const right = size.width - MARGIN.right;
    const bottom = size.height - MARGIN.bottom;
    const x = linear([span.first - 0.5, span.last + 0.5], [MARGIN.left, right]);
    const { domain, ticks } = valueAxis(series);
    const y = linear(domain, [bottom, MARGIN.top]);
    return { x, y, right, bottom, ticks };
  }, [size, span?.first, span?.last, series]); // eslint-disable-line react-hooks/exhaustive-deps

  const layer = useMemo<Layer | null>(() => {
    if (!geometry) return null;
    const { x, y, ticks } = geometry;
    return {
      key: layerKey,
      ticks: ticks.map((v) => ({ v, y: y(v) })),
      dots: toDots(series, window === "all" ? null : used).map((d) => ({ ...d, cx: x(d.season), cy: y(d.value) })),
    };
  }, [geometry, layerKey, series, window, used?.first, used?.last]); // eslint-disable-line react-hooks/exhaustive-deps

  const layers = useCrossFade(layer);

  const lines = useMemo(() => {
    if (!geometry || !trend || !used) return null;
    const through = pivot(series, used);
    const sen = pathD(senEnds(trend, used), geometry.x, geometry.y);
    if (!through) return { sen, low: null, high: null };
    const { low, high } = rangeEnds(trend, through, used);
    return { sen, low: pathD(low, geometry.x, geometry.y), high: pathD(high, geometry.x, geometry.y) };
  }, [geometry, trend, series, used?.first, used?.last]); // eslint-disable-line react-hooks/exhaustive-deps

  // the last drawn line stays in place, hidden, so the next one moves from it
  const lastLines = useRef(lines);
  if (lines) lastLines.current = lines;
  const drawn = lines ?? lastLines.current;

  const [active, setActive] = useState<number | null>(null);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const dotRefs = useRef<(SVGGElement | null)[]>([]);
  const anchor = useRef<Element | null>(null);
  const live = layers.find((l) => !l.leaving);
  const liveDots = live?.dots ?? [];
  const activeDot = active !== null ? liveDots[active] : undefined;
  anchor.current = active !== null ? (dotRefs.current[active] ?? null) : null;

  const tabStop = Math.min(focusIndex ?? liveDots.length - 1, liveDots.length - 1);

  function onKey(event: KeyboardEvent, i: number) {
    const moves: Record<string, number> = { ArrowLeft: i - 1, ArrowRight: i + 1, Home: 0, End: liveDots.length - 1 };
    const target = moves[event.key];
    if (target === undefined) return;
    event.preventDefault();
    event.stopPropagation();
    const next = Math.max(0, Math.min(liveDots.length - 1, target));
    dotRefs.current[next]?.focus();
  }

  const step = geometry && span ? seasonStep(geometry.right - MARGIN.left, span) : 5;
  const hitR = geometry && span ? Math.max(DOT_R + 2, Math.min(10, (geometry.x(span.first + 1) - geometry.x(span.first)) / 2)) : 8;
  const band =
    geometry && used && window !== "all"
      ? { x: geometry.x(used.first - 0.5), width: geometry.x(used.last + 0.5) - geometry.x(used.first - 0.5) }
      : null;
  const lastBand = useRef(band);
  if (band) lastBand.current = band;
  const bandShown = band ?? lastBand.current;

  const moving = "transition-[d,x,width] duration-360 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none";
  const fading = "transition-opacity duration-220 ease-out motion-reduce:transition-none";
  const pathStyle = (d: string | null | undefined): CSSProperties | undefined =>
    d ? ({ d: `path("${d}")` } as CSSProperties) : undefined;

  return (
    <div ref={box} className="relative min-h-0 min-w-0 flex-1">
      {geometry && span ? (
        <svg
          width={size?.width}
          height={size?.height}
          className="absolute inset-0 overflow-visible"
          role="group"
          aria-label={`${indicator.label}, one dot per season from ${seasonLabel(span.first)} to ${seasonLabel(span.last)}`}
        >
          <defs>
            <clipPath id={clipId}>
              <rect x={MARGIN.left} y={MARGIN.top} width={geometry.right - MARGIN.left} height={geometry.bottom - MARGIN.top} />
            </clipPath>
          </defs>

          {bandShown ? (
            <rect
              y={MARGIN.top}
              height={geometry.bottom - MARGIN.top}
              style={{ x: bandShown.x, width: bandShown.width } as CSSProperties}
              x={bandShown.x}
              width={bandShown.width}
              className={cx(
                "fill-background-secondary-default transition-[x,width,opacity] duration-360 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none",
                band ? "opacity-100" : "opacity-0",
              )}
            />
          ) : null}

          <text x={MARGIN.left - 8} y={MARGIN.top - 20} textAnchor="end" className="fill-text-tertiary text-caption-1-medium">
            {displayUnit(unit)}
          </text>

          {seasonTicks(span, step).map((s) => (
            <text
              key={s}
              x={geometry.x(s)}
              y={geometry.bottom + 22}
              textAnchor="middle"
              className="fill-text-secondary text-body-2-regular tabular-nums"
            >
              {seasonLabel(s)}
            </text>
          ))}

          {layers.map((l) => (
            <g
              key={l.key}
              aria-hidden={l.leaving || undefined}
              className={cx(fading, "starting:opacity-0", l.leaving ? "pointer-events-none opacity-0" : "opacity-100")}
            >
              {l.ticks.map((t) => (
                <g key={t.v}>
                  <line x1={MARGIN.left} x2={geometry.right} y1={t.y} y2={t.y} className="stroke-separator-border" strokeWidth={1} />
                  <text x={MARGIN.left - 8} y={t.y} dy="0.32em" textAnchor="end" className="fill-text-secondary text-body-2-regular tabular-nums">
                    {tickText(t.v)}
                  </text>
                </g>
              ))}
            </g>
          ))}

          <g clipPath={`url(#${clipId})`} className={cx(fading, lines ? "opacity-100" : "opacity-0")} aria-hidden>
            {drawn?.low ? <path d={drawn.low} style={pathStyle(drawn.low)} className={cx("fill-none stroke-text-tertiary", moving)} strokeWidth={1} /> : null}
            {drawn?.high ? <path d={drawn.high} style={pathStyle(drawn.high)} className={cx("fill-none stroke-text-tertiary", moving)} strokeWidth={1} /> : null}
            {drawn ? (
              <path
                data-testid="sen-line"
                data-d={lines?.sen ?? ""}
                d={drawn.sen}
                style={pathStyle(drawn.sen)}
                className={cx("fill-none stroke-text-primary", moving)}
                strokeWidth={2.5}
                strokeLinecap="round"
              />
            ) : null}
          </g>

          {layers.map((l) => (
            <g
              key={l.key}
              aria-hidden={l.leaving || undefined}
              className={cx(fading, "starting:opacity-0", l.leaving ? "pointer-events-none opacity-0" : "opacity-100")}
            >
              {l.dots.map((d, i) => {
                const own = !l.leaving;
                const label = `${d.label}: ${reading(d.value, unit)}`;
                return (
                  <g
                    key={d.season}
                    ref={own ? (el) => void (dotRefs.current[i] = el) : undefined}
                    tabIndex={own ? (i === tabStop ? 0 : -1) : undefined}
                    role={own ? "img" : undefined}
                    aria-label={own ? label : undefined}
                    data-season={d.season}
                    data-in-window={d.inWindow}
                    className="cursor-default outline-none"
                    onPointerEnter={own ? () => setActive(i) : undefined}
                    onPointerLeave={own ? () => setActive((a) => (a === i ? null : a)) : undefined}
                    onFocus={own ? () => (setActive(i), setFocusIndex(i)) : undefined}
                    onBlur={own ? () => setActive((a) => (a === i ? null : a)) : undefined}
                    onKeyDown={own ? (e) => onKey(e, i) : undefined}
                  >
                    <circle cx={d.cx} cy={d.cy} r={hitR} className="fill-transparent" />
                    {own && active === i ? (
                      <circle cx={d.cx} cy={d.cy} r={DOT_R + 3.5} className="fill-none stroke-text-primary" strokeWidth={1.5} />
                    ) : null}
                    <circle
                      cx={d.cx}
                      cy={d.cy}
                      r={DOT_R}
                      strokeWidth={1.5}
                      className={cx(
                        "transition-[fill,stroke] duration-220 ease-out motion-reduce:transition-none",
                        d.inWindow ? "fill-text-primary stroke-text-primary" : "fill-background-full stroke-text-tertiary",
                      )}
                    />
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
      ) : null}
      {activeDot ? (
        <TooltipTriggerStateContext.Provider value={OPEN}>
          <Tooltip key={`${live?.key}-${active}`} triggerRef={anchor} isOpen placement="top" offset={8}>
            <span className="tabular-nums">{`${activeDot.label}: ${reading(activeDot.value, unit)}`}</span>
          </Tooltip>
        </TooltipTriggerStateContext.Provider>
      ) : null}
    </div>
  );
}

export function ChartKey({ window, level }: { window: WindowChoice; level: number | null }) {
  const item = "inline-flex items-center gap-2";
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-caption-1-regular text-text-tertiary" aria-hidden>
      {level !== null ? (
        <>
          <span className={item}>
            <svg width="20" height="8" className="overflow-visible">
              <line x1="0" x2="20" y1="4" y2="4" className="stroke-text-primary" strokeWidth={2.5} strokeLinecap="round" />
            </svg>
            Sen&apos;s slope over the seasons used
          </span>
          <span className={item}>
            <svg width="20" height="8" className="overflow-visible">
              <line x1="0" x2="20" y1="7" y2="1" className="stroke-text-tertiary" strokeWidth={1} />
              <line x1="0" x2="20" y1="5" y2="3" className="stroke-text-tertiary" strokeWidth={1} />
            </svg>
            {level}% range of the slope
          </span>
        </>
      ) : null}
      {window !== "all" ? (
        <span className={item}>
          <svg width="10" height="10" className="overflow-visible">
            <circle cx="5" cy="5" r={DOT_R} strokeWidth={1.5} className="fill-background-full stroke-text-tertiary" />
          </svg>
          Season outside the window
        </span>
      ) : null}
    </div>
  );
}
