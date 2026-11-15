import { afterEach, describe, expect, test, vi } from "vitest";
import { parseLine } from "./parseLine";
import { createSimulation, simulationRequested, startSimulator } from "./simulator";
import { createPodStore } from "./store";

const run = (seed: number, seconds: number) => {
  const tick = createSimulation(seed);
  return Array.from({ length: seconds }, (_, i) => tick(i));
};

describe("simulator", () => {
  afterEach(() => void vi.useRealTimers());

  test("the same seed gives the same lines", () => {
    expect(run(7, 30)).toEqual(run(7, 30));
    expect(run(7, 30)).not.toEqual(run(8, 30));
  });

  test("heart rate and SpO2 every second, temperature and humidity every 2 seconds", () => {
    const ticks = run(3, 10).map((lines) => lines.map((l) => parseLine(l)?.kind));
    for (const [i, kinds] of ticks.entries()) {
      expect(kinds.filter((k) => k === "heart_rate").length).toBeGreaterThanOrEqual(1);
      expect(kinds).toContain("spo2");
      expect(kinds.includes("air_temp_c")).toBe(i % 2 === 0);
      expect(kinds.includes("humidity_pct")).toBe(i % 2 === 0);
    }
  });

  test("emits mosquito lines and lines that the parser drops", () => {
    const lines = run(1, 300).flat();
    const parsed = lines.map(parseLine);
    expect(parsed.some((e) => e?.kind === "mosquito")).toBe(true);
    expect(lines.some((l) => l.includes('"spo2","v":104'))).toBe(true);
    expect(parsed.filter((e) => e === null).length).toBeGreaterThan(2);
  });

  test("feeds the store under the simulation source once a second", () => {
    vi.useFakeTimers();
    const store = createPodStore(() => Date.now());
    const stop = startSimulator((line) => store.getState().ingestLine(line, "simulation"), 5);
    expect(store.getState().source).toBe("simulation");
    expect(store.getState().latest.heart_rate).toBeDefined();
    const first = store.getState().latest.heart_rate;
    vi.advanceTimersByTime(1000);
    expect(store.getState().latest.heart_rate).not.toBe(first);
    stop();
    const last = store.getState().latest.heart_rate;
    vi.advanceTimersByTime(5000);
    expect(store.getState().latest.heart_rate).toBe(last);
  });

  test("only ?sim=1 asks for the simulator", () => {
    expect(simulationRequested("?sim=1")).toBe(true);
    expect(simulationRequested("?story=1&sim=1")).toBe(true);
    expect(simulationRequested("?sim=0")).toBe(false);
    expect(simulationRequested("")).toBe(false);
  });
});
