import type { PodEvent } from "./parseLine";
import type { PodStore } from "./store";

export type RecordedEvent = PodEvent & { t: number };

export function createRecorder(clock: () => number = Date.now) {
  let startedAt: number | null = null;
  let events: RecordedEvent[] = [];

  return {
    start() {
      startedAt = clock();
      events = [];
    },
    stop() {
      startedAt = null;
    },
    isRecording: () => startedAt !== null,
    add({ kind, value, label, unit, quality }: PodEvent) {
      if (startedAt === null) return;
      events.push({ kind, value, label, unit, quality, t: clock() - startedAt });
    },
    toJSON: (): RecordedEvent[] => events.map((event) => ({ ...event })),
  };
}

export type Recorder = ReturnType<typeof createRecorder>;

// live readings only, each one once
export function recordFrom(store: PodStore, recorder: Recorder): () => void {
  const seen = new WeakSet<object>([store.getState().last ?? {}]);
  return store.subscribe(({ last }) => {
    if (!last || last.source !== "live" || seen.has(last)) return;
    seen.add(last);
    recorder.add(last);
  });
}

export const recordingRequested = (search: string) => new URLSearchParams(search).get("record") === "1";

export function downloadJSON(data: unknown, filename = "replay.json") {
  const blob = new Blob([JSON.stringify(data, null, 1)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
