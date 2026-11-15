import { rateUnit } from "@/lib/trends/cellLayer";
import { signed } from "@/lib/trends/format";
import type { IndicatorKey, TrendIndex } from "@/lib/trends/types";

// what the map's hover card says about the thing under the pointer; every line comes from the loaded files

export type HoverTarget = { kind: "cell" | "place"; id: string };
export type HoverCard = { title: string; lines: string[] };

type Context = {
  index: TrendIndex;
  key: IndicatorKey;
  label: string;
  heights: Record<string, number> | null;
  // false when the map is not coloured by the climate data, so the card leaves the climate line out
  climate: boolean;
};

const digits = (x: number) => (Math.abs(x) >= 10 ? 1 : 2);
const metres = (m: number) => `${m.toLocaleString("en-GB")} m above sea level`;

function climateLines(cellId: string, { index, key, label }: Context): string[] {
  const unit = rateUnit(key);
  const cell = index.cells.find((c) => c.id === cellId);
  if (cell?.error) return ["No NASA data for this cell"];
  const summary = cell?.indicators?.[key];
  if (!summary || summary.slope_per_decade == null) return [`${label}: no trend`];
  const verdict = summary.significant_fdr ? "Significant after correction" : summary.significant ? "Significant in this cell only" : "Not statistically significant";
  return [`${label}: ${signed(summary.slope_per_decade, digits(summary.slope_per_decade))} ${unit} per decade`, verdict];
}

export function hoverCard(target: HoverTarget, context: Context): HoverCard | null {
  const { index, heights, climate } = context;
  if (target.kind === "cell") {
    const cell = index.cells.find((c) => c.id === target.id);
    if (!cell) return null;
    // named after a town only when that town really is inside the cell
    const town = index.places.find((p) => p.kind === "town" && p.cell === cell.id);
    return { title: town ? `NASA grid cell around ${town.name}` : "NASA grid cell", lines: climateLines(cell.id, context) };
  }
  const place = index.places.find((p) => p.id === target.id);
  if (!place) return null;
  const lines: string[] = [];
  const what = [place.kind === "town" ? "Town" : place.type, place.district ? `${place.district} district` : null].filter(Boolean).join(", ");
  if (what) lines.push(what);
  const height = heights?.[place.id];
  if (height !== undefined) lines.push(metres(height));
  if (climate) lines.push(...climateLines(place.cell, context));
  return { title: place.name, lines };
}
