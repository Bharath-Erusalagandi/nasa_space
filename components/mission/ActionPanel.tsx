"use client";

import { useEffect } from "react";
import { ProgressBar } from "@/components/base/progress/progress";
import { calendarLine } from "@/lib/mission/calendar";
import { DISPATCH, session, useVisit, type Visit } from "@/lib/mission/session";
import { getCellFailed, getCellLoading, getCellSummary, getPlace, useMission, usePanelEmphasis } from "@/lib/mission/state";
import { usePod } from "@/lib/pod/store";
import { ColumnTitle, Columns, EmptyState, FieldLabel, FieldValue, Note, PanelFrame } from "./primitives";
import { useNow } from "./PodStatus";

const hhmm = (at: string) => new Date(at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

const NO_DELIVERY: Record<Exclude<Visit["route"], "planned">, string> = {
  nothing_to_deliver: "Nothing to deliver.",
  grid_cell: "A grid cell is not a place on the road network, so there is no route to drive. Pick a town or facility.",
  no_route: "No road route to this place was computed.",
  no_routes_file: "The road routes could not be loaded.",
};

function Triage({ visit }: { visit: Visit }) {
  return (
    <div role="group" aria-label="Triage">
      <p className="text-title-1-medium text-text-primary">{visit.triage.title}</p>
      <Note>{visit.triage.reason}</Note>
    </div>
  );
}

function Order({ visit }: { visit: Visit }) {
  const order = visit.order;
  return (
    <div role="group" aria-label="Order">
      <ColumnTitle aside={order ? `created ${hhmm(order.createdAt)}` : undefined}>Order</ColumnTitle>
      {order ? (
        <ul className="flex flex-col">
          {order.items.map((item) => (
            <li key={item.id}>
              <FieldValue>{item.name}</FieldValue>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState>No order: no danger sign found.</EmptyState>
      )}
    </div>
  );
}

function Delivery({ visit }: { visit: Visit }) {
  const now = useNow(1000);
  const delivery = visit.delivery;
  const ack = usePod((s) => s.ack);
  // the car kit's own reply to this order's dispatch, never assumed
  const drove = ack && visit.order && ack.command === DISPATCH && ack.at >= visit.order.createdAt ? ack : null;
  return (
    <div role="group" aria-label="Delivery">
      <ColumnTitle aside={delivery ? `from ${delivery.hubName}` : undefined}>Delivery</ColumnTitle>
      {delivery ? (
        <>
          <FieldValue as="p">
            {delivery.route.km} km by road, {delivery.route.minutes} min
          </FieldValue>
          <ProgressBar aria-label="Delivery progress" value={Math.round(delivery.progress(now) * 100)} size="sm" />
          <Note>{delivery.label(now)}</Note>
          {drove ? <Note>Car kit acknowledged the dispatch command at {new Date(drove.at).toLocaleTimeString("en-GB")}.</Note> : null}
        </>
      ) : (
        <EmptyState>{NO_DELIVERY[visit.route as keyof typeof NO_DELIVERY]}</EmptyState>
      )}
    </div>
  );
}

function Calendar() {
  const summary = useMission(getCellSummary);
  const loading = useMission(getCellLoading);
  const failed = useMission(getCellFailed);
  const trend = useMission((s) => s.cell?.indicators.rain_onset_day?.trend);
  let line: string;
  if (summary?.error) line = "NASA data for this cell could not be downloaded when the trends were built.";
  else if (loading) line = "Loading the start of the rains for this cell.";
  else line = calendarLine(failed ? undefined : trend);
  return (
    <div className="flex min-w-0 flex-col gap-1 border-t border-separator-border pt-4">
      <p className="text-body-medium text-text-primary">{line}</p>
      <FieldLabel>Start of the rains (stand-in for road closure)</FieldLabel>
    </div>
  );
}

export function ActionPanel() {
  const emphasis = usePanelEmphasis("action");
  const place = useMission(getPlace);
  const visit = useVisit(place?.id ?? null);

  useEffect(() => session.follow(), []);

  return (
    <PanelFrame className="min-h-auto" title="ACTION" label="ACTION" emphasis={emphasis} descriptor="Decision support, not a diagnosis.">
      {visit ? (
        <div className="flex min-w-0 flex-col gap-6 pt-2">
          <Triage visit={visit} />
          <Columns className="grid-cols-[minmax(0,6fr)_minmax(0,5fr)]">
            <Order visit={visit} />
            <Delivery visit={visit} />
          </Columns>
        </div>
      ) : (
        <EmptyState>No patient answer yet. Ask the danger sign question under Verify.</EmptyState>
      )}
      <Calendar />
    </PanelFrame>
  );
}
