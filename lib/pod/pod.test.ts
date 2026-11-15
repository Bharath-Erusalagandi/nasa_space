import { describe, expect, test } from "vitest";
import { parseLine } from "./parseLine";
import { replay } from "./replay";
import { errorLabel } from "./errorLabel";

describe("parseLine", () => {
  test("turns each line format into a pod event", () => {
    expect(parseLine('{"k":"hr","v":72,"q":0.93}')).toEqual({ kind: "heart_rate", value: 72, label: null, unit: "bpm", quality: 0.93 });
    expect(parseLine('{"k":"spo2","v":98,"q":0.9}')).toEqual({ kind: "spo2", value: 98, label: null, unit: "%", quality: 0.9 });
    expect(parseLine('{"k":"temp","v":24.1}')).toEqual({ kind: "air_temp_c", value: 24.1, label: null, unit: "°C", quality: null });
    expect(parseLine('{"k":"rh","v":41}')).toEqual({ kind: "humidity_pct", value: 41, label: null, unit: "%", quality: null });
    expect(parseLine('{"k":"mosq","label":"An. arabiensis","conf":0.84}')).toEqual({ kind: "mosquito", value: null, label: "An. arabiensis", unit: null, quality: 0.84 });
  });

  test("drops lines that are not JSON, unknown, or cannot be real", () => {
    // dropped: not JSON, unknown key, or a value that cannot be real
    expect(parseLine("boot ok")).toBeNull();
    expect(parseLine('{"k":"volts","v":3.3}')).toBeNull();
    expect(parseLine('{"k":"hr","v":0}')).toBeNull();        // finger off the sensor
    expect(parseLine('{"k":"hr","v":221}')).toBeNull();
    expect(parseLine('{"k":"spo2","v":101}')).toBeNull();
    expect(parseLine('{"k":"temp","v":61}')).toBeNull();
    expect(parseLine('{"k":"rh","v":-3}')).toBeNull();
  });

  test("drops an empty line", () => {
    expect(parseLine("")).toBeNull();
    expect(parseLine("   \r")).toBeNull();
  });

  test("drops JSON that is not an object", () => {
    expect(parseLine("42")).toBeNull();
    expect(parseLine("null")).toBeNull();
    expect(parseLine('"hr"')).toBeNull();
    expect(parseLine('[{"k":"hr","v":72}]')).toBeNull();
  });

  test("drops a value given as a numeric string", () => {
    expect(parseLine('{"k":"hr","v":"72"}')).toBeNull();
  });

  test("drops a mosquito line without a label", () => {
    expect(parseLine('{"k":"mosq","conf":0.84}')).toBeNull();
    expect(parseLine('{"k":"mosq","label":"","conf":0.84}')).toBeNull();
  });

  test("keeps readings on the inclusive limits", () => {
    expect(parseLine('{"k":"spo2","v":70}')?.value).toBe(70);
    expect(parseLine('{"k":"spo2","v":100}')?.value).toBe(100);
    expect(parseLine('{"k":"hr","v":30}')?.value).toBe(30);
    expect(parseLine('{"k":"hr","v":220}')?.value).toBe(220);
    expect(parseLine('{"k":"temp","v":-40}')?.value).toBe(-40);
    expect(parseLine('{"k":"temp","v":60}')?.value).toBe(60);
    expect(parseLine('{"k":"rh","v":0}')?.value).toBe(0);
    expect(parseLine('{"k":"rh","v":100}')?.value).toBe(100);
  });

  test("drops readings just past the limits", () => {
    expect(parseLine('{"k":"spo2","v":69.9}')).toBeNull();
    expect(parseLine('{"k":"hr","v":29.9}')).toBeNull();
    expect(parseLine('{"k":"temp","v":-40.1}')).toBeNull();
    expect(parseLine('{"k":"rh","v":100.1}')).toBeNull();
  });
});

describe("replay", () => {
  test("keeps order and scales the gaps", async () => {
    // replay keeps order and scales the gaps: 1000 ms and 1500 ms at speed 10 -> 100 ms and 150 ms
    const emitted: string[] = []; const waits: number[] = [];
    const hr = { kind: "heart_rate", value: 70, label: null, unit: "bpm", quality: 1 } as const;
    await replay([{ ...hr, t: 0 }, { ...hr, value: 71, t: 1000 }, { ...hr, value: 72, t: 2500 }],
      (e) => emitted.push(String(e.value)), 10, async (ms) => { waits.push(ms); });
    expect(emitted).toEqual(["70", "71", "72"]);
    expect(waits).toEqual([100, 150]);
  });

  test("waits the recorded gaps at speed 1", async () => {
    const waits: number[] = [];
    const hr = { kind: "heart_rate", value: 70, label: null, unit: "bpm", quality: 1 } as const;
    await replay([{ ...hr, t: 0 }, { ...hr, t: 1000 }, { ...hr, t: 2500 }], () => {}, 1, async (ms) => { waits.push(ms); });
    expect(waits).toEqual([1000, 1500]);
  });

  test("emits a single event without waiting", async () => {
    const emitted: unknown[] = []; const waits: number[] = [];
    const rh = { kind: "humidity_pct", value: 41, label: null, unit: "%", quality: null } as const;
    await replay([{ ...rh, t: 500 }], (e) => emitted.push(e), 1, async (ms) => { waits.push(ms); });
    expect(emitted).toEqual([rh]);
    expect(waits).toEqual([]);
  });
});

describe("errorLabel", () => {
  test("plan cases", () => {
    expect(errorLabel({ n: 48, loa_low: -3.8, loa_high: 5.8 }, "bpm")).toBe("tested on 48 pairs: 95% of readings within -3.8 to +5.8 bpm of the reference");
    expect(errorLabel(undefined, "bpm")).toBe("not yet tested");
  });

  test("errorLabel with a negative upper limit", () => {
    expect(errorLabel({ n: 10, loa_low: -5.2, loa_high: -1.4 }, "°C")).toBe("tested on 10 pairs: 95% of readings within -5.2 to -1.4 °C of the reference");
  });

  test("errorLabel with a zero limit", () => {
    expect(errorLabel({ n: 12, loa_low: 0, loa_high: 2 }, "%")).toBe("tested on 12 pairs: 95% of readings within 0 to +2 % of the reference");
    expect(errorLabel({ n: 12, loa_low: -2, loa_high: -0 }, "%")).toBe("tested on 12 pairs: 95% of readings within -2 to 0 % of the reference");
  });

  test("errorLabel with zero pairs is not yet tested", () => {
    expect(errorLabel({ n: 0, loa_low: -1, loa_high: 1 }, "bpm")).toBe("not yet tested");
  });
});
