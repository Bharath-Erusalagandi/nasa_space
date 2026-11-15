import { describe, expect, it } from "vitest";
import { outlineEdges } from "./outlines";

const cell = (id: string, west: number, outline: "solid" | "dashed" | "none") => ({ id, outline, bounds: { west, east: west + 1, south: 0, north: 1 } });

describe("outlineEdges", () => {
  const cells = [cell("a", 0, "solid"), cell("b", 1, "solid"), cell("c", 2, "dashed"), cell("d", 3, "none")];
  const edges = outlineEdges(cells);

  it("draws a shared edge once, with the stronger style", () => {
    expect(edges.a.edges).toHaveLength(4);
    expect(edges.b.edges).toHaveLength(3);
    expect(edges.c.edges).toHaveLength(3);
    expect(edges.b.edges).toContainEqual([[2, 0], [2, 1]]);
    expect(edges.c.edges).not.toContainEqual([[2, 0], [2, 1]]);
  });

  it("keeps the edge next to an unoutlined cell and skips unoutlined cells", () => {
    expect(edges.c.edges).toContainEqual([[3, 0], [3, 1]]);
    expect(edges.d).toBeUndefined();
    expect(edges.c.style).toBe("dashed");
  });

  it("never draws the same segment twice", () => {
    const keys = Object.values(edges).flatMap((e) => e.edges.map((s) => JSON.stringify(s)));
    expect(new Set(keys).size).toBe(keys.length);
  });
});
