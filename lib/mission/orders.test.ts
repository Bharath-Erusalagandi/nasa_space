import { describe, expect, test } from "vitest";
import { itemsFor } from "./formulary";
import { createDelivery, createOrder, DEMO_SPEEDUP } from "./orders";

describe("formulary", () => {
  test("an urgent referral orders transport and malaria test-and-treat supplies", () => {
    expect(itemsFor("urgent_referral").map((i) => i.id)).toEqual(["referral_transport", "malaria_rdt", "artemether_lumefantrine"]);
  });

  test("no danger sign orders tests only when there is fever", () => {
    expect(itemsFor("no_danger_sign", true).map((i) => i.id)).toEqual(["malaria_rdt"]);
    expect(itemsFor("no_danger_sign")).toEqual([]);
  });

  test("every item cites a source and says whether it was checked", () => {
    for (const item of itemsFor("urgent_referral")) {
      expect(item.source).toMatch(/^https:\/\//);
      expect(typeof item.needsCheck).toBe("boolean");
    }
  });
});

describe("orders", () => {
  test("createOrder stamps the place, outcome, items and time", () => {
    const now = Date.UTC(2026, 10, 15, 10, 30);
    const order = createOrder("katete", "urgent_referral", now);
    expect(order).toMatchObject({ placeId: "katete", outcome: "urgent_referral", createdAt: "2026-11-15T10:30:00.000Z" });
    expect(order.items).toHaveLength(3);
  });
});

describe("delivery", () => {
  // two legs of equal length along the equator
  const route = { km: 20, minutes: 30, line: [[0, 0], [0.1, 0], [0.2, 0]] as [number, number][] };
  const start = 1_000_000;
  const delivery = createDelivery(route, "Chipata", start);
  const realMs = (route.minutes * 60000) / DEMO_SPEEDUP;

  test("progress runs from 0 to 1 on the demo clock", () => {
    expect(DEMO_SPEEDUP).toBeGreaterThan(1);
    expect(delivery.progress(start - 5000)).toBe(0);
    expect(delivery.progress(start + realMs / 2)).toBeCloseTo(0.5);
    expect(delivery.progress(start + realMs * 3)).toBe(1);
  });

  test("the position moves along the line", () => {
    expect(delivery.position(start)).toEqual([0, 0]);
    const quarter = delivery.position(start + realMs / 4);
    expect(quarter[0]).toBeCloseTo(0.05, 4);
    expect(quarter[1]).toBeCloseTo(0, 6);
    expect(delivery.position(start + (realMs * 3) / 4)[0]).toBeCloseTo(0.15, 4);
    expect(delivery.position(start + realMs)).toEqual([0.2, 0]);
  });

  test("every label says simulated vehicle", () => {
    const labels = [start - 1, start + realMs / 3, start + realMs + 1].map(delivery.label);
    for (const label of labels) expect(label).toContain("simulated vehicle");
    expect(labels[0]).toBe("simulated vehicle waiting at Chipata");
    expect(labels[1]).toBe(`simulated vehicle: 6.7 of 20 km, about 20 min left (demo clock ${DEMO_SPEEDUP}x)`);
    expect(labels[2]).toBe("simulated vehicle arrived: 20 km by road, 30 min of road time");
  });
});
