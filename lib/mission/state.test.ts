import { describe, expect, it } from "vitest";
import { cellFile, index, indexCell, summary, trend } from "@/lib/trends/fixtures";
import type { CellFile } from "@/lib/trends/types";
import { createMissionStore, defaultPlace, getCellFailed, getCellLoading, getCellSummary, getPlace, getSeries, getTrend } from "./state";
import { STORY } from "./story";

const sample = index([
  indexCell("-14.000_31.875", -14, 31.875, { october_temp_c: summary(0.36, 0.007, 0.01) }),
  indexCell("-13.500_32.500", -13.5, 32.5, { october_temp_c: summary(0.42, 0.0005, 0.004) }),
]);

function withId(file: CellFile, id: string): CellFile {
  return { ...file, cell: { ...file.cell, id } };
}

const katete = cellFile({ october_temp_c: { all: trend(0.36, 0.007), ten: trend(-1.04, 0.47, { n: 10 }) } });
const chipata = withId(cellFile({ october_temp_c: { all: trend(0.42, 0.001) } }), "-13.500_32.500");

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

function setup(search = "", cells: Record<string, () => Promise<CellFile>> = {}) {
  const address = { current: search, writes: [] as string[] };
  let indexLoads = 0;
  const store = createMissionStore({
    loadIndex: async () => {
      indexLoads++;
      return sample;
    },
    loadCell: (id) => (cells[id] ?? (async () => (id === chipata.cell.id ? chipata : katete)))(),
    address: {
      search: () => address.current,
      replace: (s) => {
        address.current = s;
        address.writes.push(s);
      },
    },
  });
  return { store, address, indexLoads: () => indexLoads };
}

const flush = () => new Promise((r) => setTimeout(r, 0));

describe("defaultPlace", () => {
  it("prefers the requested place, then katete, then the first town", () => {
    expect(defaultPlace(sample, "chipata")).toBe("chipata");
    expect(defaultPlace(sample, "nowhere")).toBe("katete");
    expect(defaultPlace(sample, null)).toBe("katete");
    const noKatete = { ...sample, places: sample.places.filter((p) => p.id !== "katete") };
    expect(defaultPlace(noKatete, null)).toBe("chipata");
  });
});

describe("mission store", () => {
  it("loads the index once and selects katete by default", async () => {
    const { store, address, indexLoads } = setup();
    await Promise.all([store.getState().init(), store.getState().init()]);
    await flush();
    const s = store.getState();
    expect(indexLoads()).toBe(1);
    expect(getPlace(s)?.name).toBe("Katete");
    expect(getCellSummary(s)?.id).toBe("-14.000_31.875");
    expect(s.cell?.cell.id).toBe("-14.000_31.875");
    expect(address.current).toBe("?place=katete");
    expect(s.indicator).toBe("october_temp_c");
    expect(s.window).toBe("all");
    expect(s.story).toBe(false);
    expect(s.panel).toBeNull();
  });

  it("takes the place from the address and keeps other parameters", async () => {
    const { store, address } = setup("?story=1&place=chipata");
    await store.getState().init();
    await flush();
    expect(getPlace(store.getState())?.id).toBe("chipata");
    expect(address.writes).toEqual([]);
    store.getState().selectPlace("katete");
    expect(address.current).toBe("?story=1&place=katete");
  });

  it("keeps the previous cell on screen until the next one arrives", async () => {
    const pending = deferred<CellFile>();
    const { store } = setup("", { [chipata.cell.id]: () => pending.promise });
    await store.getState().init();
    await flush();
    store.getState().selectPlace("chipata");
    expect(store.getState().cell?.cell.id).toBe("-14.000_31.875");
    expect(getCellLoading(store.getState())).toBe(true);
    pending.resolve(chipata);
    await flush();
    expect(store.getState().cell?.cell.id).toBe("-13.500_32.500");
    expect(getCellLoading(store.getState())).toBe(false);
  });

  it("ignores a slow cell that was overtaken by a newer selection", async () => {
    const slow = deferred<CellFile>();
    const { store } = setup("", { [chipata.cell.id]: () => slow.promise });
    await store.getState().init();
    await flush();
    store.getState().selectPlace("chipata");
    store.getState().selectPlace("katete");
    await flush();
    slow.resolve(chipata);
    await flush();
    expect(store.getState().cell?.cell.id).toBe("-14.000_31.875");
  });

  it("does not reload when the new place shares the cell", async () => {
    let loads = 0;
    const { store } = setup("", { "-14.000_31.875": async () => (loads++, katete) });
    await store.getState().init();
    await flush();
    store.getState().selectPlace("katete-clinic");
    await flush();
    expect(loads).toBe(1);
  });

  it("reads the active trend and series from the window", async () => {
    const { store } = setup();
    await store.getState().init();
    await flush();
    expect(getTrend(store.getState())?.slope_per_decade).toBe(0.36);
    store.getState().setWindow("10");
    expect(getTrend(store.getState())?.slope_per_decade).toBe(-1.04);
    store.getState().setWindow("20");
    expect(getTrend(store.getState())).toBeNull();
    expect(getSeries(store.getState())).toEqual([]);
    store.getState().setIndicator("wet_days");
    expect(store.getState().layer).toBe("wet_days");
  });

  it("applies story steps and clamps at both ends", async () => {
    const { store } = setup("?story=1");
    await store.getState().init();
    let s = store.getState();
    expect(s.story).toBe(true);
    expect([s.step, s.indicator, s.panel]).toEqual([0, "wet_season_rain_mm", "sky"]);
    s.prevStep();
    expect(store.getState().step).toBe(0);
    store.getState().nextStep();
    store.getState().nextStep();
    s = store.getState();
    expect([s.step, s.indicator, s.window, s.layer, s.panel]).toEqual([2, "october_temp_c", "10", "october_temp_c", "sky"]);
    for (let i = 0; i < 10; i++) store.getState().nextStep();
    s = store.getState();
    expect(s.step).toBe(STORY.length - 1);
    expect(s.panel).toBe("action");
  });

  it("does not step outside story mode", async () => {
    const { store } = setup();
    await store.getState().init();
    store.getState().nextStep();
    expect(store.getState().step).toBe(0);
    expect(store.getState().panel).toBeNull();
  });

  it("reports a missing index instead of throwing", async () => {
    const store = createMissionStore({
      loadIndex: async () => {
        throw new Error("/trends/index.json: HTTP 404");
      },
      address: { search: () => "", replace: () => {} },
    });
    await store.getState().init();
    expect(store.getState().indexError).toContain("404");
    expect(getPlace(store.getState())).toBeUndefined();
  });

  it("a failed cell load is retried when the place is selected again", async () => {
    let attempts = 0;
    const { store } = setup("", {
      "-14.000_31.875": async () => {
        attempts++;
        if (attempts === 1) throw new Error("HTTP 503");
        return katete;
      },
    });
    await store.getState().init();
    await flush();
    expect(store.getState().cellError).toContain("503");
    expect(getCellLoading(store.getState())).toBe(false);
    store.getState().selectPlace("katete");
    await flush();
    expect(attempts).toBe(2);
    expect(store.getState().cellError).toBeNull();
    expect(store.getState().cell?.cell.id).toBe("-14.000_31.875");
    store.getState().selectPlace("katete");
    await flush();
    expect(attempts).toBe(2);
  });

  it("a failed load after another cell does not leave the old cell's file as current", async () => {
    let fail = false;
    const { store } = setup("", {
      "-13.500_32.500": async () => {
        if (fail) throw new Error("HTTP 503");
        return chipata;
      },
    });
    await store.getState().init();
    await flush();
    fail = true;
    store.getState().selectPlace("chipata");
    await flush();
    expect(getCellFailed(store.getState())).toBe(true);
    expect(getCellLoading(store.getState())).toBe(false);
  });
});

