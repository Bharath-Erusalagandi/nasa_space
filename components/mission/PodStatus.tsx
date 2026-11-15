"use client";

import { RiBluetoothLine, RiDownloadLine, RiUsbLine } from "@remixicon/react";
import { useEffect, useState } from "react";
import { StatusDot } from "@/components/base/badges/status-dot";
import { Button } from "@/components/base/buttons/button";
import { POD_ID } from "@/lib/brand";
import { useShownStep } from "@/lib/mission/view";
import { OFFLINE_AFTER_MS, usePod, type PodSource } from "@/lib/pod/store";
import { cx } from "@/utils/cx";

export type PodState = "live" | "pod offline" | "replay" | "simulation";

export function useNow(everyMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(id);
  }, [everyMs]);
  return now;
}

const STATE_FOR: Record<PodSource, PodState> = { none: "pod offline", live: "live", replay: "replay", simulation: "simulation" };

// the state names the source of the readings on screen; only live readings go stale
export function usePodState(): { state: PodState; offline: boolean } {
  const now = useNow(500);
  const source = usePod((s) => s.source);
  const lastEventAt = usePod((s) => s.lastEventAt);
  if (source === "replay" || source === "simulation") return { state: STATE_FOR[source], offline: false };
  const offline = lastEventAt === null || now - lastEventAt >= OFFLINE_AFTER_MS;
  return { state: offline ? "pod offline" : "live", offline };
}

const DOT = { live: "green", "pod offline": "neutral", replay: "indigo", simulation: "indigo" } as const;
const LOOK_MS = 1800;
const ANNOUNCE_MS = 4000;

// On opening the page it looks for the pod (a port granted earlier, over USB or Bluetooth) and says so; a connection
// is announced with the way it came in. Nothing claims a connection the browser did not report.
export function PodStatus({ state }: { state: PodState }) {
  const connection = usePod((s) => s.connection);
  const transport = usePod((s) => s.transport);
  const [looking, setLooking] = useState(true);
  const [announce, setAnnounce] = useState(false);

  const shown = useShownStep();

  // the search plays each time GROUND comes on screen
  useEffect(() => {
    if (shown !== "ground") return;
    setLooking(true);
    const id = setTimeout(() => setLooking(false), LOOK_MS);
    return () => clearTimeout(id);
  }, [shown]);

  useEffect(() => {
    if (connection !== "connected") return;
    setAnnounce(true);
    const id = setTimeout(() => setAnnounce(false), ANNOUNCE_MS);
    return () => clearTimeout(id);
  }, [connection]);

  const label = state === "pod offline" ? "not connected" : state;
  const via = transport === "bluetooth" ? "Bluetooth" : transport === "usb" ? "USB" : null;
  const Icon = transport === "usb" ? RiUsbLine : RiBluetoothLine;
  const searching = looking && connection !== "connected" && connection !== "unsupported";

  return (
    <span className="inline-flex items-center gap-2" role="status" aria-label={`pod ${POD_ID}, ${label}`}>
      <span className="text-body-medium text-text-primary">pod {POD_ID}</span>
      {searching ? (
        <span className="inline-flex items-center gap-1.5 text-body-regular text-text-tertiary">
          <Signal Icon={RiBluetoothLine} active />
          Looking for the pod
        </span>
      ) : connection === "connected" && via ? (
        <span className="inline-flex items-center gap-1.5 text-body-regular text-text-secondary">
          <Signal Icon={Icon} active={announce} />
          {announce ? `Connected over ${via}` : via}
        </span>
      ) : null}
      {state !== "pod offline" ? (
        <>
          <StatusDot color={DOT[state]} />
          <span className="text-body-regular text-text-secondary">{state}</span>
        </>
      ) : null}
    </span>
  );
}

// the icon with a ring that spreads out while something is happening
function Signal({ Icon, active }: { Icon: typeof RiBluetoothLine; active: boolean }) {
  return (
    <span className="relative inline-flex size-5 items-center justify-center">
      {active ? <span aria-hidden className="absolute inset-0 rounded-full bg-accent-500/30 motion-safe:animate-ping" /> : null}
      <Icon aria-hidden className={cx("relative size-4", active ? "text-accent-500" : "text-foreground-icon-secondary")} />
    </span>
  );
}

type ActionsProps = { recording: boolean; onConnect: () => void; onDownload: () => void };

export function PodActions({ recording, onConnect, onDownload }: ActionsProps) {
  const connection = usePod((s) => s.connection);
  return (
    <>
      {recording ? (
        <Button variant="ghost" size="small" leadingIcon={RiDownloadLine} onClick={onDownload}>
          Download session
        </Button>
      ) : null}
      {connection !== "connected" && connection !== "unsupported" ? (
        <Button variant="secondary" size="small" leadingIcon={RiUsbLine} disabled={connection === "connecting"} onClick={onConnect}>
          Connect pod
        </Button>
      ) : null}
    </>
  );
}
