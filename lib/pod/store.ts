import { createStore, useStore } from "zustand";
import { POD_ID } from "@/lib/brand";
import { parseAck, parseLine, type PodEvent, type PodKind } from "./parseLine";

export const OFFLINE_AFTER_MS = 5000;

export type PodSource = "none" | "live" | "replay" | "simulation";
export type ReadingSource = Exclude<PodSource, "none">;
export type Connection = "unsupported" | "idle" | "connecting" | "connected" | "disconnected";
export type StoredEvent = PodEvent & { pod_id: string; at: string; source: ReadingSource };

export type PodState = {
  latest: Partial<Record<PodKind, StoredEvent>>;
  last: StoredEvent | null;
  lastEventAt: number | null;
  // the source of the readings on screen; they never mix
  source: PodSource;
  // a replay or the simulator owns the screen while it runs
  running: Exclude<ReadingSource, "live"> | null;
  held: number;
  connection: Connection;
  transport: "bluetooth" | "usb" | null;
  mosquitoes: StoredEvent[];
  // the last command the connected pod said it ran
  ack: { command: string; at: string } | null;
  dropped: number;
  ingestLine: (line: string, source: ReadingSource) => StoredEvent | null;
  ingestEvent: (event: PodEvent, source: ReadingSource) => StoredEvent | null;
  claim: (source: Exclude<ReadingSource, "live">) => void;
  release: (source: Exclude<ReadingSource, "live">) => void;
  countDropped: () => void;
  isOffline: (now?: number) => boolean;
  setConnection: (connection: Connection) => void;
  setTransport: (transport: "bluetooth" | "usb") => void;
  reset: () => void;
};

const noReadings = {
  latest: {},
  last: null,
  lastEventAt: null,
  source: "none" as PodSource,
  mosquitoes: [],
};

export function createPodStore(clock: () => number = Date.now) {
  return createStore<PodState>()((set, get) => ({
    ...noReadings,
    running: null,
    held: 0,
    dropped: 0,
    ack: null,
    connection: "idle",
    transport: null,

    ingestEvent(event, source) {
      const { running } = get();
      if (running && source !== running) {
        set((state) => ({ held: state.held + 1 }));
        return null;
      }
      const now = clock();
      const stored: StoredEvent = { ...event, pod_id: POD_ID, at: new Date(now).toISOString(), source };
      set((state) => {
        const base = state.source === source ? state : noReadings;
        return {
          latest: { ...base.latest, [stored.kind]: stored },
          last: stored,
          lastEventAt: now,
          source,
          mosquitoes: stored.kind === "mosquito" ? [...base.mosquitoes, stored] : base.mosquitoes,
        };
      });
      return stored;
    },

    ingestLine(line, source) {
      const event = parseLine(line);
      if (event) return get().ingestEvent(event, source);
      const command = source === "live" ? parseAck(line) : null;
      if (command) set({ ack: { command, at: new Date(clock()).toISOString() } });
      else get().countDropped();
      return null;
    },

    claim(source) {
      set((state) => ({ running: source, ...(state.source === source ? {} : noReadings) }));
    },

    release(source) {
      if (get().running !== source) return;
      set((state) => ({ running: null, ...(state.source === source ? noReadings : {}) }));
    },

    countDropped: () => set((state) => ({ dropped: state.dropped + 1 })),

    isOffline(now = clock()) {
      const at = get().lastEventAt;
      return at === null || now - at >= OFFLINE_AFTER_MS;
    },

    setConnection: (connection) => set(connection === "connected" ? { connection } : { connection, transport: null }),
    setTransport: (transport) => set({ transport }),
    reset: () => set({ ...noReadings, dropped: 0, held: 0, ack: null }),
  }));
}

export type PodStore = ReturnType<typeof createPodStore>;

export const podStore = createPodStore();

export const usePod = <T>(select: (state: PodState) => T) => useStore(podStore, select);
