import { createStore, useStore } from "zustand";
import { loadCell as fetchCell, loadIndex as fetchIndex } from "@/lib/trends/load";
import type { CellFile, IndexCell, IndicatorKey, Place, Trend, TrendIndex, WindowChoice } from "@/lib/trends/types";
import type { Delivery } from "./orders";
import { next, prev, STORY, type Panel } from "./story";

export const DEFAULT_PLACE = "katete";
export const DEFAULT_INDICATOR: IndicatorKey = "october_temp_c";
export const DEFAULT_WINDOW: WindowChoice = "all";

export type MissionState = {
  index: TrendIndex | null;
  indexError: string | null;
  placeId: string | null;
  cell: CellFile | null;
  cellError: string | null;
  indicator: IndicatorKey;
  window: WindowChoice;
  layer: IndicatorKey;
  story: boolean;
  step: number;
  panel: Panel | null;
  delivery: Delivery | null;
  init: () => Promise<void>;
  selectPlace: (id: string) => void;
  setIndicator: (key: IndicatorKey) => void;
  setWindow: (window: WindowChoice) => void;
  setPanel: (panel: Panel | null) => void;
  setDelivery: (delivery: Delivery | null) => void;
  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
};

export type Address = { search: () => string; replace: (search: string) => void };

type Deps = {
  loadIndex: () => Promise<TrendIndex>;
  loadCell: (id: string) => Promise<CellFile>;
  address: Address;
};

const browserAddress: Address = {
  search: () => (typeof window === "undefined" ? "" : window.location.search),
  replace(search) {
    if (typeof window === "undefined") return;
    const url = `${window.location.pathname}${search}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", url);
  },
};

const message = (error: unknown) => (error instanceof Error ? error.message : String(error));

export function defaultPlace(index: TrendIndex, wanted: string | null): string | null {
  const ids = new Set(index.places.map((p) => p.id));
  if (wanted && ids.has(wanted)) return wanted;
  if (ids.has(DEFAULT_PLACE)) return DEFAULT_PLACE;
  return index.places.find((p) => p.kind === "town")?.id ?? index.places[0]?.id ?? null;
}

export function createMissionStore({ loadIndex = fetchIndex, loadCell = fetchCell, address = browserAddress }: Partial<Deps> = {}) {
  let started: Promise<void> | null = null;
  let cellRequest = 0;
  let pendingCell: string | null = null;

  return createStore<MissionState>()((set, get) => {
    async function showCell(cellId: string) {
      const request = ++cellRequest;
      pendingCell = cellId;
      set({ cellError: null });
      try {
        const cell = await loadCell(cellId);
        if (request === cellRequest) set({ cell, cellError: null });
      } catch (error) {
        if (request === cellRequest) set({ cellError: message(error) });
      } finally {
        if (request === cellRequest) pendingCell = null;
      }
    }

    function writePlace(id: string) {
      const params = new URLSearchParams(address.search());
      if (params.get("place") === id) return;
      params.set("place", id);
      address.replace(`?${params.toString()}`);
    }

    function applyStep(step: number) {
      const s = STORY[step];
      set({ step, indicator: s.indicator, window: s.window, layer: s.layer, panel: s.panel });
    }

    return {
      index: null,
      indexError: null,
      placeId: null,
      cell: null,
      cellError: null,
      indicator: DEFAULT_INDICATOR,
      window: DEFAULT_WINDOW,
      layer: DEFAULT_INDICATOR,
      story: false,
      step: 0,
      panel: null,
      delivery: null,

      init() {
        started ??= (async () => {
          const params = new URLSearchParams(address.search());
          if (params.get("story") === "1") {
            set({ story: true });
            applyStep(0);
          }
          try {
            const index = await loadIndex();
            set({ index, indexError: null });
            const id = defaultPlace(index, params.get("place"));
            if (id) get().selectPlace(id);
          } catch (error) {
            set({ indexError: message(error) });
          }
        })();
        return started;
      },

      selectPlace(id) {
        const place = get().index?.places.find((p) => p.id === id);
        if (!place) return;
        set({ placeId: id });
        writePlace(id);
        if (get().cell?.cell.id === place.cell) {
          // back on the cell on screen: a load still running for another cell must not replace it
          cellRequest++;
          pendingCell = null;
          set({ cellError: null });
        } else if (pendingCell !== place.cell) {
          // also retries a cell that failed to load
          void showCell(place.cell);
        }
      },

      setIndicator: (indicator) => set({ indicator, layer: indicator }),
      setWindow: (window) => set({ window }),
      setPanel: (panel) => set({ panel }),
      setDelivery: (delivery) => set({ delivery }),

      setStep(step) {
        if (!get().story) return;
        applyStep(Math.min(STORY.length - 1, Math.max(0, step)));
      },
      nextStep: () => get().setStep(next(get().step)),
      prevStep: () => get().setStep(prev(get().step)),
    };
  });
}

export type MissionStore = ReturnType<typeof createMissionStore>;

export const missionStore = createMissionStore();

export const useMission = <T>(select: (state: MissionState) => T) => useStore(missionStore, select);

// undefined outside story mode; in story mode the active panel is "active", the rest "quiet"
export const emphasisOf = (s: MissionState, panel: Panel): "active" | "quiet" | undefined =>
  s.story ? (s.panel === panel ? "active" : "quiet") : undefined;

export const usePanelEmphasis = (panel: Panel) => useMission((s) => emphasisOf(s, panel));

export const getPlace = (s: MissionState): Place | undefined => s.index?.places.find((p) => p.id === s.placeId);

export const getCellSummary = (s: MissionState): IndexCell | undefined => {
  const place = getPlace(s);
  return place ? s.index?.cells.find((c) => c.id === place.cell) : undefined;
};

// the file on screen, which may still be the previous cell while the next one loads
export const getCellFile = (s: MissionState): CellFile | null => s.cell;

export const getCellLoading = (s: MissionState): boolean => {
  const place = getPlace(s);
  return Boolean(place) && s.cell?.cell.id !== place?.cell && !s.cellError;
};

// the selected place's cell file failed to load, so nothing on screen belongs to it
export const getCellFailed = (s: MissionState): boolean => {
  const place = getPlace(s);
  return Boolean(place) && s.cell?.cell.id !== place?.cell && Boolean(s.cellError);
};

export const getIndicator = (s: MissionState) => s.cell?.indicators[s.indicator];

export const getTrend = (s: MissionState): Trend | null | undefined => {
  const indicator = getIndicator(s);
  if (!indicator) return undefined;
  return s.window === "all" ? indicator.trend : indicator.windows[s.window];
};
