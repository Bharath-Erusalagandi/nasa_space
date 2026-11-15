import { distanceKm } from "@/lib/trends/geo";
import type { Position, Route } from "@/lib/trends/types";
import { itemsFor, type FormularyItem } from "./formulary";
import type { TriageOutcome } from "./triage";

// one real second moves the simulated vehicle one minute of road time
export const DEMO_SPEEDUP = 60;

export type Order = { id: string; placeId: string; outcome: TriageOutcome; items: FormularyItem[]; createdAt: string };

export function createOrder(placeId: string, outcome: TriageOutcome, now: number, fever = false): Order {
  return { id: `${placeId}-${now}`, placeId, outcome, items: itemsFor(outcome, fever), createdAt: new Date(now).toISOString() };
}

const point = ([lon, lat]: Position) => ({ lat, lon });

export function createDelivery(route: Route, hubName: string, startedAt: number, speedup = DEMO_SPEEDUP) {
  const legs = route.line.slice(1).map((p, i) => distanceKm(point(route.line[i]), point(p)));
  const total = legs.reduce((a, b) => a + b, 0);
  const durationMs = (route.minutes * 60000) / speedup;

  function progress(now: number): number {
    if (durationMs <= 0) return 1;
    return Math.min(1, Math.max(0, (now - startedAt) / durationMs));
  }

  function position(now: number): Position {
    const line = route.line;
    let left = progress(now) * total;
    for (let i = 0; i < legs.length; i++) {
      if (left <= legs[i] && legs[i] > 0) {
        const f = left / legs[i];
        const [a, b] = [line[i], line[i + 1]];
        return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
      }
      left -= legs[i];
    }
    return line[line.length - 1];
  }

  function label(now: number): string {
    const p = progress(now);
    if (p <= 0) return `simulated vehicle waiting at ${hubName}`;
    if (p >= 1) return `simulated vehicle arrived: ${route.km} km by road, ${route.minutes} min of road time`;
    const done = (route.km * p).toFixed(1);
    const left = Math.max(1, Math.round(route.minutes * (1 - p)));
    return `simulated vehicle: ${done} of ${route.km} km, about ${left} min left (demo clock ${speedup}x)`;
  }

  return { route, hubName, startedAt, speedup, progress, position, label };
}

export type Delivery = ReturnType<typeof createDelivery>;
