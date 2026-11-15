type Bounds = { west: number; east: number; south: number; north: number };
type Style = "solid" | "dashed";
type OutlinedCell = { id: string; outline: Style | "none"; bounds: Bounds };

export type Segment = [[number, number], [number, number]];

const RANK: Record<Style, number> = { solid: 2, dashed: 1 };

const sides = (b: Bounds): Segment[] => [
  [[b.west, b.north], [b.east, b.north]],
  [[b.east, b.south], [b.east, b.north]],
  [[b.west, b.south], [b.east, b.south]],
  [[b.west, b.south], [b.west, b.north]],
];

const keyOf = ([[x0, y0], [x1, y1]]: Segment) => [x0, y0, x1, y1].map((v) => v.toFixed(5)).join(",");

// each cell edge is drawn by one cell only, the one with the stronger outline, so neighbours never double a line
export function outlineEdges(cells: OutlinedCell[]): Record<string, { style: Style; edges: Segment[] }> {
  const owner = new Map<string, { id: string; style: Style; segment: Segment }>();
  for (const cell of cells) {
    if (cell.outline === "none") continue;
    for (const segment of sides(cell.bounds)) {
      const key = keyOf(segment);
      const held = owner.get(key);
      if (!held || RANK[cell.outline] > RANK[held.style]) owner.set(key, { id: cell.id, style: cell.outline, segment });
    }
  }
  const out: Record<string, { style: Style; edges: Segment[] }> = {};
  for (const cell of cells) if (cell.outline !== "none") out[cell.id] = { style: cell.outline, edges: [] };
  for (const { id, segment } of owner.values()) out[id].edges.push(segment);
  return out;
}
