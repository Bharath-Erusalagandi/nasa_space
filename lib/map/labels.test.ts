import { describe, expect, it } from "vitest";
import { placeLabel } from "./labels";

const size = { width: 600, height: 400 };
const dot = (x: number, y: number) => ({ x: x - 3, y: y - 3, width: 6, height: 6 });

describe("placeLabel", () => {
  it("puts the label right of the point when that is clear", () => {
    const l = placeLabel([100, 100], { width: 50, height: 14 }, [], size);
    expect(l.anchor).toBe("start");
    expect(l.box.x).toBeGreaterThan(100);
  });

  it("moves the label off a dot that sits where it would go", () => {
    const l = placeLabel([100, 100], { width: 50, height: 14 }, [dot(130, 100)], size);
    expect(l.anchor).toBe("end");
    expect(l.box.x + l.box.width).toBeLessThan(100);
  });

  it("tries above and below when both sides are taken", () => {
    const l = placeLabel([100, 100], { width: 50, height: 14 }, [dot(130, 100), dot(70, 100)], size);
    expect(l.anchor).toBe("middle");
    expect(l.box.y + l.box.height <= 97 || l.box.y >= 103).toBe(true);
  });

  it("stays inside the map", () => {
    const l = placeLabel([590, 100], { width: 50, height: 14 }, [], size);
    expect(l.box.x + l.box.width).toBeLessThanOrEqual(size.width);
  });
});
