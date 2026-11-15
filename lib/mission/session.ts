import { createStore, useStore } from "zustand";
import { loadMap } from "@/lib/trends/load";
import type { Place, Routes } from "@/lib/trends/types";
import { createDelivery, createOrder, type Delivery, type Order } from "./orders";
import { missionStore, type MissionStore } from "./state";
import { sendToPod } from "@/lib/pod/serial";
import { OFFLINE_AFTER_MS, type StoredEvent } from "@/lib/pod/store";
import { DANGER_SIGNS, triage, type DangerSign, type Spo2Source, type TriageResult } from "./triage";

export type Answer = { sign: DangerSign | "none" } | { text: string };

export type RouteStatus = "planned" | "grid_cell" | "no_route" | "no_routes_file" | "nothing_to_deliver";

export type Visit = {
  placeId: string;
  answer: string;
  triage: TriageResult;
  order: Order | null;
  delivery: Delivery | null;
  route: RouteStatus;
};

export function answerWords(answer: Answer): string {
  if ("text" in answer) return `"${answer.text.trim()}"`;
  if (answer.sign === "none") return "none of these";
  return DANGER_SIGNS.find((s) => s.id === answer.sign)!.words;
}

// what triage may take from the pod: a fresh live reading is a measurement, a replayed or simulated one is labelled
export type Oxygen = { spo2: number | null; spo2Source?: Spo2Source };

export function oxygenFor(event: StoredEvent | undefined, now: number): Oxygen {
  if (!event || event.value === null || now - Date.parse(event.at) >= OFFLINE_AFTER_MS) return { spo2: null };
  return event.source === "live" ? { spo2: event.value } : { spo2: event.value, spo2Source: event.source };
}

// what the chat learned beyond the danger sign answer
export type Findings = { fever?: boolean; warnings?: string[] };

type PlanInput = { place: Place; answer: Answer; routes: Routes | null; now: number; findings?: Findings } & Oxygen;

export function planVisit({ place, answer, spo2, spo2Source, routes, now, findings = {} }: PlanInput): Visit {
  const result = triage({
    signs: "sign" in answer ? [answer.sign] : [],
    answer: "text" in answer ? answer.text : undefined,
    spo2,
    spo2Source,
    warnings: findings.warnings,
    fever: findings.fever,
  });
  const created = createOrder(place.id, result.outcome, now, findings.fever ?? false);
  const order = created.items.length ? created : null;
  const visit = { placeId: place.id, answer: answerWords(answer), triage: result, order };

  if (!order) return { ...visit, delivery: null, route: "nothing_to_deliver" };
  if (place.kind === "cell") return { ...visit, delivery: null, route: "grid_cell" };
  if (!routes) return { ...visit, delivery: null, route: "no_routes_file" };
  const route = routes.routes[place.id];
  if (!route) return { ...visit, delivery: null, route: "no_route" };
  return { ...visit, delivery: createDelivery(route, routes.hub.name, now), route: "planned" };
}

type SessionState = { visits: Record<string, Visit> };

type Deps = {
  mission?: MissionStore;
  loadRoutes?: () => Promise<Routes>;
  clock?: () => number;
  dispatch?: () => unknown;
};

export const DISPATCH = "dispatch";

export function createSession({
  mission = missionStore,
  loadRoutes = () => loadMap("routes"),
  clock = Date.now,
  dispatch = () => sendToPod(DISPATCH),
}: Deps = {}) {
  const store = createStore<SessionState>()(() => ({ visits: {} }));

  const selected = () => mission.getState().placeId;
  const showDelivery = () => {
    const id = selected();
    mission.getState().setDelivery((id && store.getState().visits[id]?.delivery) || null);
  };

  async function answer(input: Answer, oxygen: Oxygen, findings?: Findings): Promise<Visit | null> {
    const { index, placeId } = mission.getState();
    const place = index?.places.find((p) => p.id === placeId);
    if (!place) return null;
    const routes = await loadRoutes().catch(() => null);
    const visit = planVisit({ place, answer: input, ...oxygen, routes, now: clock(), findings });
    store.setState((s) => ({ visits: { ...s.visits, [place.id]: visit } }));
    if (selected() === place.id) showDelivery();
    // a connected car kit drives off when a delivery is planned; with no pod this does nothing
    if (visit.delivery) void dispatch();
    return visit;
  }

  // the map draws the delivery of the place on screen
  const follow = () =>
    mission.subscribe((s, before) => {
      if (s.placeId !== before.placeId) showDelivery();
    });

  return { store, answer, follow };
}

export const session = createSession();

export const useVisit = (placeId: string | null) => useStore(session.store, (s) => (placeId ? s.visits[placeId] : undefined));
