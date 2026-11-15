import { describe, expect, it } from "vitest";
import { index, indexCell } from "@/lib/trends/__fixtures__/trends";
import type { Routes } from "@/lib/trends/types";
import type { StoredEvent } from "@/lib/pod/store";
import { createSession, oxygenFor, planVisit } from "./session";
import { createMissionStore } from "./state";

const sample = index([indexCell("-14.000_31.875", -14, 31.875, {}), indexCell("-13.500_32.500", -13.5, 32.5, {})]);
const place = (id: string) => sample.places.find((p) => p.id === id)!;

const routes: Routes = {
  hub: { id: "chipata", name: "Chipata", lat: -13.63, lon: 32.65 },
  routes: {
    katete: { km: 87.1, minutes: 66, line: [[32.65, -13.63], [32.3, -13.9], [32.04, -14.06]] },
    chipata: { km: 0, minutes: 0, line: [[32.65, -13.63]] },
  },
};

const now = Date.UTC(2026, 10, 15, 9, 0);

describe("planVisit", () => {
  it("a danger sign gives an urgent referral, an order and a delivery on the place's route", () => {
    const visit = planVisit({ place: place("katete"), answer: { sign: "lethargy" }, spo2: 97, routes, now });
    expect(visit.triage.title).toBe("Urgent referral");
    expect(visit.answer).toBe("very sleepy or hard to wake");
    expect(visit.order?.items.map((i) => i.id)).toEqual(["referral_transport", "malaria_rdt", "artemether_lumefantrine"]);
    expect(visit.order?.createdAt).toBe("2026-11-15T09:00:00.000Z");
    expect(visit.route).toBe("planned");
    expect(visit.delivery?.route.km).toBe(87.1);
    expect(visit.delivery?.hubName).toBe("Chipata");
    expect(visit.delivery?.label(now)).toContain("simulated vehicle");
  });

  it("a typed answer goes through the same keyword check", () => {
    const visit = planVisit({ place: place("katete"), answer: { text: "she has had fits since morning" }, spo2: null, routes, now });
    expect(visit.triage.outcome).toBe("urgent_referral");
    expect(visit.answer).toBe('"she has had fits since morning"');
  });

  it("low SpO2 from the pod refers even when no sign is reported", () => {
    const visit = planVisit({ place: place("katete"), answer: { sign: "none" }, spo2: 86, routes, now });
    expect(visit.triage.outcome).toBe("urgent_referral");
    expect(visit.triage.reason).toContain("SpO2 is 86%");
  });

  it("no danger sign creates no order and nothing to deliver", () => {
    const visit = planVisit({ place: place("katete"), answer: { sign: "none" }, spo2: 98, routes, now });
    expect(visit.triage.outcome).toBe("no_danger_sign");
    expect(visit.order).toBeNull();
    expect(visit.delivery).toBeNull();
    expect(visit.route).toBe("nothing_to_deliver");
  });

  it("a grid cell place has an order but no road route", () => {
    const visit = planVisit({ place: place("cell-14.000_31.875"), answer: { sign: "convulsions" }, spo2: null, routes, now });
    expect(visit.order).not.toBeNull();
    expect(visit.delivery).toBeNull();
    expect(visit.route).toBe("grid_cell");
  });

  it("a place missing from routes.json, or no routes file, gives no delivery", () => {
    expect(planVisit({ place: place("katete-clinic"), answer: { sign: "lethargy" }, spo2: null, routes, now }).route).toBe("no_route");
    expect(planVisit({ place: place("katete"), answer: { sign: "lethargy" }, spo2: null, routes: null, now }).route).toBe("no_routes_file");
  });
});

describe("session", () => {
  async function setup() {
    const mission = createMissionStore({
      loadIndex: async () => sample,
      loadCell: async () => {
        throw new Error("not needed");
      },
      address: { search: () => "?place=katete", replace: () => {} },
    });
    await mission.getState().init();
    const s = createSession({ mission, loadRoutes: async () => routes, clock: () => now });
    return { mission, s };
  }

  it("writes the selected place's delivery to the mission store and follows the place", async () => {
    const { mission, s } = await setup();
    const stop = s.follow();
    const visit = await s.answer({ sign: "lethargy" }, { spo2: 97 });
    expect(mission.getState().delivery).toBe(visit?.delivery);

    mission.getState().selectPlace("chipata");
    expect(mission.getState().delivery).toBeNull();
    mission.getState().selectPlace("katete");
    expect(mission.getState().delivery).toBe(visit?.delivery);
    stop();
  });

  it("keeps one visit per place", async () => {
    const { mission, s } = await setup();
    await s.answer({ sign: "lethargy" }, { spo2: null });
    mission.getState().selectPlace("chipata");
    await s.answer({ sign: "none" }, { spo2: 98 });
    expect(Object.keys(s.store.getState().visits).sort()).toEqual(["chipata", "katete"]);
    expect(s.store.getState().visits.chipata.triage.outcome).toBe("no_danger_sign");
  });

  it("tells the car kit to dispatch only when a delivery is planned", async () => {
    const { mission } = await setup();
    let dispatched = 0;
    const s = createSession({ mission, loadRoutes: async () => routes, clock: () => now, dispatch: () => dispatched++ });
    await s.answer({ sign: "none" }, { spo2: 98 });
    expect(dispatched).toBe(0);
    await s.answer({ sign: "lethargy" }, { spo2: 97 });
    expect(dispatched).toBe(1);
    mission.getState().selectPlace("cell-14.000_31.875");
    const visit = await s.answer({ sign: "convulsions" }, { spo2: null });
    expect(visit?.route).toBe("grid_cell");
    expect(dispatched).toBe(1);
  });

  it("a failed routes load still records the triage and order", async () => {
    const { mission } = await setup();
    const s = createSession({ mission, loadRoutes: () => Promise.reject(new Error("offline")), clock: () => now });
    const visit = await s.answer({ sign: "cannot_drink" }, { spo2: null });
    expect(visit?.order).not.toBeNull();
    expect(visit?.route).toBe("no_routes_file");
  });
});

describe("oxygenFor", () => {
  const at = new Date(now).toISOString();
  const event = (source: StoredEvent["source"], value: number | null = 97): StoredEvent => ({
    kind: "spo2", value, label: null, unit: "%", quality: 0.9, pod_id: "K-01", at, source,
  });

  it("passes a fresh live reading as a measurement", () => {
    expect(oxygenFor(event("live"), now + 1000)).toEqual({ spo2: 97 });
  });

  it("labels replayed and simulated readings", () => {
    expect(oxygenFor(event("replay"), now)).toEqual({ spo2: 97, spo2Source: "replay" });
    expect(oxygenFor(event("simulation"), now)).toEqual({ spo2: 97, spo2Source: "simulation" });
  });

  it("an old or missing reading is not measured", () => {
    expect(oxygenFor(event("live"), now + 5000)).toEqual({ spo2: null });
    expect(oxygenFor(undefined, now)).toEqual({ spo2: null });
  });
});
