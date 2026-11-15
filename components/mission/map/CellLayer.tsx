import type { KeyboardEvent } from "react";
import type { GeoProjection } from "d3-geo";
import { outlineEdges } from "@/lib/map/outlines";
import { project, type View } from "@/lib/map/projection";
import type { LayerCell, Outline, Ramp } from "@/lib/trends/cellLayer";
import { dataColor } from "@/lib/trends/colors";

export const HATCH_ID = "map-hatch";

export function HatchPattern({ id }: { id: string }) {
  return (
    <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" className="fill-data-none" />
      <line x1="0" y1="0" x2="0" y2="6" className="stroke-text-tertiary [stroke-width:1.5px]" />
    </pattern>
  );
}

export const OUTLINE_DASH: Record<Outline, string | undefined> = { solid: undefined, dashed: "3 2.5", none: undefined };

// opaque enough that the relief under a cell barely shifts its colour, so one class reads as one colour
export const FILL_OPACITY = 0.86;

export const OUTLINE_CLASS = "fill-none stroke-text-primary opacity-55 [stroke-width:1.25px] [stroke-linecap:butt]";

type Rect = { x: number; y: number; width: number; height: number };

export function rectOf(cell: LayerCell, projection: GeoProjection, view: View): Rect {
  const [x0, y0] = project(projection, view, cell.bounds.west, cell.bounds.north);
  const [x1, y1] = project(projection, view, cell.bounds.east, cell.bounds.south);
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

const inset = (r: Rect, d: number): Rect => ({ x: r.x + d, y: r.y + d, width: r.width - 2 * d, height: r.height - 2 * d });

function brackets(r: Rect): string {
  const o = inset(r, -4);
  const arm = Math.min(14, o.width / 3, o.height / 3);
  const [l, t, rt, b] = [o.x, o.y, o.x + o.width, o.y + o.height];
  return [
    `M${l},${t + arm}V${t}H${l + arm}`,
    `M${rt - arm},${t}H${rt}V${t + arm}`,
    `M${rt},${b - arm}V${b}H${rt - arm}`,
    `M${l + arm},${b}H${l}V${b - arm}`,
  ].join("");
}

type Props = {
  cells: LayerCell[];
  ramp: Ramp;
  reversed: boolean;
  projection: GeoProjection;
  view: View;
  describe: (cell: LayerCell) => string;
  onSelect: (id: string) => void;
};

const activate = (fn: () => void) => (event: KeyboardEvent) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  event.preventDefault();
  fn();
};

export function CellLayer({ cells, ramp, reversed, projection, view, describe, onSelect }: Props) {
  const drawn = cells.map((cell) => ({ cell, rect: rectOf(cell, projection, view) }));

  return (
    <g data-layer="cells">
      {drawn.map(({ cell, rect }) => (
        <g
          key={cell.id}
          role="button"
          tabIndex={0}
          aria-label={describe(cell)}
          data-cell={cell.id}
          data-outline={cell.outline}
          data-error={cell.error || undefined}
          data-class={cell.cls ?? undefined}
          className="group cursor-pointer outline-none"
          onClick={() => onSelect(cell.id)}
          onKeyDown={activate(() => onSelect(cell.id))}
        >
          <rect
            {...rect}
            data-fill
            fill={cell.error ? `url(#${HATCH_ID})` : dataColor(ramp, cell.cls, reversed)}
            fillOpacity={cell.error ? 1 : FILL_OPACITY}
            className="transition-[fill] duration-200 ease-out motion-reduce:transition-none"
          />
          {/* the cell under the pointer */}
          <rect {...inset(rect, 1)} data-hover className="pointer-events-none fill-none stroke-text-primary opacity-0 [stroke-width:2px] group-hover:opacity-70" />
          <rect
            {...inset(rect, 2)}
            className="pointer-events-none fill-none stroke-border-focus-ring opacity-0 [stroke-width:2px] group-focus-visible:opacity-100"
          />
        </g>
      ))}
    </g>
  );
}

// drawn above roads and rivers; each shared edge once
export function CellOutlines({ cells, projection, view }: { cells: LayerCell[]; projection: GeoProjection; view: View }) {
  const edges = outlineEdges(cells.filter((c) => !c.error));
  return (
    <g data-layer="outlines" className="pointer-events-none" aria-hidden>
      {Object.entries(edges).map(([id, { style, edges: segments }]) => (
        <path
          key={id}
          d={segments.map(([a, b]) => `M${project(projection, view, ...a).join(",")}L${project(projection, view, ...b).join(",")}`).join("")}
          data-outline-for={id}
          data-style={style}
          strokeDasharray={OUTLINE_DASH[style]}
          className={OUTLINE_CLASS}
        />
      ))}
    </g>
  );
}

// one surface under every cell, so a cell outside the province sits on the same ground as one inside it
export function CellGround({ cells, projection, view }: { cells: LayerCell[]; projection: GeoProjection; view: View }) {
  return (
    <g aria-hidden className="pointer-events-none">
      {cells.map((cell) => (
        <rect key={cell.id} {...inset(rectOf(cell, projection, view), -0.5)} className="fill-background-primary-default" />
      ))}
    </g>
  );
}

export function CellBrackets({ cell, projection, view }: { cell: LayerCell | undefined; projection: GeoProjection; view: View }) {
  if (!cell) return null;
  return (
    <path
      d={brackets(rectOf(cell, projection, view))}
      data-selected-cell={cell.id}
      aria-hidden
      className="pointer-events-none fill-none stroke-text-primary [stroke-width:2.5px] [stroke-linecap:square]"
    />
  );
}
