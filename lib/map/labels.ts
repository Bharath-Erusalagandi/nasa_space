import type { Point, Size } from "./projection";

export type Box = { x: number; y: number; width: number; height: number };
export type Placed = { x: number; y: number; anchor: "start" | "end" | "middle"; box: Box };

const overlap = (a: Box, b: Box) =>
  Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));

const outside = (b: Box, size: Size) => Math.max(0, b.width * b.height - overlap(b, { x: 0, y: 0, ...size }) - 1e-6);

// right, left, above, below, the four diagonals, then further out and higher or lower; y is the text's middle
function candidates([x, y]: Point, { width, height }: { width: number; height: number }, gap: number): Placed[] {
  const half = height / 2;
  return [gap, gap + 6, gap + 12, gap + 20].flatMap((g) => {
    const lift = half + g * 0.6;
    const side = (dy: number): Placed[] => [
      { x: x + g, y: y + dy, anchor: "start", box: { x: x + g, y: y + dy - half, width, height } },
      { x: x - g, y: y + dy, anchor: "end", box: { x: x - g - width, y: y + dy - half, width, height } },
    ];
    return [
      ...side(0),
      { x, y: y - g - half, anchor: "middle", box: { x: x - width / 2, y: y - g - height, width, height } },
      { x, y: y + g + half, anchor: "middle", box: { x: x - width / 2, y: y + g, width, height } },
      ...side(-lift),
      ...side(lift),
      ...side(-2 * lift),
      ...side(2 * lift),
    ];
  });
}

const grow = (b: Box, d: number): Box => ({ x: b.x - d, y: b.y - d, width: b.width + 2 * d, height: b.height + 2 * d });

export function placeLabel(at: Point, text: { width: number; height: number }, obstacles: Box[], size: Size, gap = 8): Placed {
  const score = (p: Placed) => outside(p.box, size) * 4 + obstacles.reduce((sum, o) => sum + overlap(grow(p.box, 1.5), o), 0);
  return candidates(at, text, gap).reduce((best, p) => (score(p) < score(best) ? p : best));
}

export const around = ([x, y]: Point, r: number): Box => ({ x: x - r, y: y - r, width: 2 * r, height: 2 * r });

// rough widths for Inter at the label sizes used on the map
export const textWidth = (text: string, px: number) => Math.ceil(text.length * px * 0.56);
