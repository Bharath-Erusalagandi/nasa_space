"use client";

import { RiMicLine, RiMicOffLine } from "@remixicon/react";
import { useEffect, useState } from "react";
import { Button } from "@/components/base/buttons/button";
import { toast, Toaster } from "@/components/base/toast/toast";
import { usePanelEmphasis } from "@/lib/mission/state";
import { usePodControls } from "@/lib/pod/controls";
import { errorLabel, NOT_TESTED } from "@/lib/pod/errorLabel";
import { startListening, stopListening, useListener } from "@/lib/pod/listener";
import type { PodKind } from "@/lib/pod/parseLine";
import { usePod, type StoredEvent } from "@/lib/pod/store";
import { minusSigns, num } from "@/lib/trends/format";
import { loadPodSite, loadValidation } from "@/lib/trends/load";
import type { PodSite, ValidationResults } from "@/lib/trends/types";
import { Chat } from "./Chat";
import { SpeciesGrid } from "./SpeciesGrid";
import { PodActions, PodStatus, usePodState } from "./PodStatus";
import { FieldLabel, Figure, Note, PanelFrame } from "./primitives";

type Site = PodSite & { place?: string; period?: string; half_window?: number };

const hhmmss = (at: string) => new Date(at).toLocaleTimeString("en-GB");

function useOptional<T>(load: () => Promise<T | undefined>) {
  const [data, setData] = useState<T | undefined>();
  useEffect(() => {
    let live = true;
    void load().then((d) => live && setData(d));
    return () => {
      live = false;
    };
  }, [load]);
  return data;
}

const notify = (message: string) => toast.info(message);

type Shown = { kind: PodKind; label: string; name: string; digits: number; error: (results?: ValidationResults) => string };

// a reading takes a place on screen only once the pod has sent it
const READINGS: Shown[] = [
  { kind: "air_temp_c", label: "Temperature", name: "temperature", digits: 1, error: (r) => errorLabel(r?.air_temp_c, "°C") },
  { kind: "humidity_pct", label: "Humidity", name: "humidity", digits: 0, error: () => errorLabel(undefined, "%") },
  { kind: "heart_rate", label: "Heart rate", name: "heart rate", digits: 0, error: (r) => errorLabel(r?.heart_rate, "bpm") },
  { kind: "spo2", label: "SpO2", name: "SpO2", digits: 0, error: (r) => errorLabel(r?.spo2, "%") },
  { kind: "distance_cm", label: "Distance to surface", name: "distance to surface", digits: 1, error: () => errorLabel(undefined, "cm") },
  { kind: "light_pct", label: "Light on panel", name: "light on panel (uncalibrated)", digits: 0, error: () => errorLabel(undefined, "%") },
];

function Reading({ shown, event, stale }: { shown: Shown; event: StoredEvent; stale: boolean }) {
  return (
    <div role="group" aria-label={shown.label} className="flex min-w-0 flex-col">
      <FieldLabel>{shown.label}</FieldLabel>
      <span className="flex items-baseline gap-2">
        <Figure value={num(event.value ?? 0, shown.digits)} unit={event.unit} muted={stale} />
        {stale ? <Note>at {hhmmss(event.at)}</Note> : null}
      </span>
    </div>
  );
}

function years(period: string | undefined): number | null {
  const found = period?.match(/(\d{4})-(\d{2})-(\d{2}) to (\d{4})-(\d{2})-(\d{2})/);
  if (!found) return null;
  const [, y1, m1, d1, y2, m2, d2] = found.map(Number);
  return Math.floor((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / (365.25 * 86400000));
}

function NasaNormal({ site }: { site: Site }) {
  const today = new Date();
  const key = `${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const normal = site.normals[key];
  if (!normal) return null;
  const span = years(site.period);
  const window = site.half_window === 7 ? "this fortnight" : `${(site.half_window ?? 0) * 2 + 1} days around today`;
  const where = site.place ? ` in ${site.place}` : "";
  return (
    <Note>
      NASA {span ? `${span}-year ` : ""}normal for {window}
      {where}: {num(normal.p10, 1)} to {num(normal.p90, 1)} °C (daily means).
    </Note>
  );
}

function ListenButton() {
  const status = useListener((l) => l.status);
  if (status === "unsupported") return null;
  if (status === "on") {
    return (
      <Button variant="secondary" size="small" leadingIcon={RiMicOffLine} onClick={stopListening}>
        Stop listening
      </Button>
    );
  }
  return (
    <Button variant="secondary" size="small" leadingIcon={RiMicLine} disabled={status === "starting"} onClick={() => void startListening()}>
      {status === "starting" ? "Loading the model" : "Listen for mosquitoes"}
    </Button>
  );
}

// one line under the row says what has been checked against a reference, in place of a note under every number
function Readings({ results, site, stale }: { results?: ValidationResults; site?: Site; stale: boolean }) {
  const latest = usePod((s) => s.latest);
  const shown = READINGS.filter((r) => latest[r.kind]?.value != null);
  if (!shown.length) return null;
  const tested = shown.filter((r) => r.error(results) !== NOT_TESTED);
  const untested = shown.filter((r) => r.error(results) === NOT_TESTED);
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap gap-x-10 gap-y-4">
        {shown.map((r) => (
          <Reading key={r.kind} shown={r} event={latest[r.kind]!} stale={stale} />
        ))}
      </div>
      <div className="flex flex-col gap-1">
        {tested.map((r) => (
          <Note key={r.kind}>
            {r.label} {minusSigns(r.error(results))}.
          </Note>
        ))}
        {untested.length ? <Note>Not yet tested against a reference: {untested.map((r) => r.name).join(", ")}.</Note> : null}
        {site && latest.air_temp_c ? <NasaNormal site={site} /> : null}
      </div>
    </div>
  );
}

function Quiet() {
  const connection = usePod((p) => p.connection);
  const status = useListener((l) => l.status);
  const note = useListener((l) => l.note);
  if (connection === "unsupported") return <Note>This browser cannot read the pod. Open the page in Chrome or Edge.</Note>;
  if (status === "denied") return <Note>The microphone is blocked for this page. Allow it in the browser to listen.</Note>;
  if (status === "failed") return <Note>{note}</Note>;
  if (status === "on") return <Note>Listening through the microphone. A mosquito shows on its card below.</Note>;
  return null;
}

export function GroundPanel() {
  const emphasis = usePanelEmphasis("ground");
  const controls = usePodControls(notify);
  const { state, offline } = usePodState();
  const results = useOptional(loadValidation);
  const site = useOptional(loadPodSite) as Site | undefined;

  return (
    <PanelFrame
      className="min-h-auto"
      title="GROUND"
      label="GROUND"
      emphasis={emphasis}
      descriptor={<PodStatus state={state} />}
      right={
        <>
          <ListenButton />
          <PodActions recording={controls.recording} onConnect={() => void controls.connect()} onDownload={controls.download} />
        </>
      }
    >
      <div className="flex min-w-0 flex-col gap-6 pt-2">
        <Quiet />
        <Readings results={results} site={site} stale={offline} />
        <SpeciesGrid />
        <Chat />
      </div>
      <Toaster />
    </PanelFrame>
  );
}
