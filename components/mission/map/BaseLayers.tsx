import { memo } from "react";
import type { BasePaths } from "@/lib/map/paths";
import type { View } from "@/lib/map/projection";
import { cx } from "@/utils/cx";

type Box = { x: number; y: number; width: number; height: number };

const line = "fill-none [vector-effect:non-scaling-stroke] [stroke-linejoin:round] [stroke-linecap:round]";

const zoomed = (view: View) => `translate(${view.x} ${view.y}) scale(${view.k})`;

// the hillshade's flat ground is about 0.73; light mode multiplies it so flat is white,
// dark mode inverts it and screens it so flat is black, both only darken or lighten slopes a little
function ReliefFilter({ id, slope, intercept }: { id: string; slope: number; intercept: number }) {
  return (
    <filter id={id} colorInterpolationFilters="sRGB">
      <feComponentTransfer>
        <feFuncR type="linear" slope={slope} intercept={intercept} />
        <feFuncG type="linear" slope={slope} intercept={intercept} />
        <feFuncB type="linear" slope={slope} intercept={intercept} />
      </feComponentTransfer>
    </filter>
  );
}

// geometry is projected once at zoom 1; the group transform zooms it and strokes keep their width
export const Ground = memo(function Ground({ paths, relief, view }: { paths: BasePaths; relief: Box | null; view: View }) {
  return (
    <g transform={zoomed(view)} aria-hidden className="pointer-events-none">
      <defs>
        <ReliefFilter id="map-relief-light" slope={2} intercept={-0.46} />
        <ReliefFilter id="map-relief-dark" slope={-2} intercept={1.46} />
        <clipPath id="map-province-clip">
          <path d={paths.province} />
        </clipPath>
      </defs>
      <path d={paths.province} className="fill-background-primary-default" />
      {relief ? (
        <g data-relief>
          <image href="/map/relief.webp" {...relief} preserveAspectRatio="none" clipPath="url(#map-province-clip)" filter="url(#map-relief-light)" className="opacity-35 mix-blend-multiply dark:hidden" />
          <image href="/map/relief.webp" {...relief} preserveAspectRatio="none" clipPath="url(#map-province-clip)" filter="url(#map-relief-dark)" className="hidden opacity-25 mix-blend-screen dark:inline" />
        </g>
      ) : null}

    </g>
  );
});

// lines go above the cell fills so roads and rivers read through the colour
export const Lines = memo(function Lines({ paths, view }: { paths: BasePaths; view: View }) {
  return (
    <g transform={zoomed(view)} aria-hidden className="pointer-events-none">
      {/* contours sit above the cell colours so the terrain reads through them */}
      <g data-contours>
        <path d={paths.contours.minor} className={cx(line, "stroke-text-primary opacity-15 [stroke-width:0.5px]")} />
        <path d={paths.contours.major} className={cx(line, "stroke-text-primary opacity-35 [stroke-width:0.9px]")} />
      </g>
      <path d={paths.districts} className={cx(line, "stroke-separator-border [stroke-width:1px]")} />
      <path d={paths.rivers} className={cx(line, "stroke-foreground-icon-quaternary [stroke-width:0.6px]")} />
      <path d={paths.roads.tertiary} className={cx(line, "stroke-foreground-icon-quaternary [stroke-width:0.75px]")} />
      <path d={paths.roads.secondary} className={cx(line, "stroke-foreground-icon-tertiary [stroke-width:0.9px]")} />
      <path d={`${paths.roads.primary}${paths.roads.trunk}`} className={cx(line, "stroke-foreground-icon-secondary [stroke-width:1.25px]")} />
      <path d={paths.borders} className={cx(line, "stroke-text-tertiary [stroke-width:1px]")} />
    </g>
  );
});

// drawn above the cells so the province edge reads through their fill
export function ProvinceEdge({ d, view }: { d: string; view: View }) {
  return (
    <g transform={zoomed(view)} aria-hidden className="pointer-events-none">
      <path d={d} className={cx(line, "stroke-text-secondary [stroke-width:1.5px]")} />
    </g>
  );
}
