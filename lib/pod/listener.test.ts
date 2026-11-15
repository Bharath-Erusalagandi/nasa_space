import { describe, expect, it } from "vitest";
import { createDecision, createMeter, createScorer, createTape, withGenus } from "./listener";
import type { MosquitoModel } from "./mosquitoModel";

const CLASSES = ["An. arabiensis", "Ae. aegypti"];

// a stand-in model whose detector reads the loudness of the window and whose species follows its sign
function fakeModel(): MosquitoModel & { calls: number } {
  const model = {
    calls: 0,
    rate: 8000,
    windowSamples: 100,
    speciesClasses: CLASSES,
    features: (signal: Float32Array) => Float32Array.from(signal.slice(0, 100)),
    detector: (x: Float32Array) => {
      model.calls++;
      const loud = x.reduce((s, v) => s + Math.abs(v), 0) / x.length > 0.5 ? 0.9 : 0.1;
      return [1 - loud, loud];
    },
    species: (x: Float32Array) => (x[x.length - 1] > 0 ? [0.8, 0.2] : [0.3, 0.7]),
  };
  return model;
}

const r = (mosquito: number, species = [0.8, 0.2]) => ({ mosquito, species });

describe("createScorer", () => {
  it("scores once per step once a full window is in, however the audio is chunked", () => {
    const a = fakeModel();
    const whole = createScorer(a, 50)(new Float32Array(400).fill(1));
    const b = fakeModel();
    const push = createScorer(b, 50);
    const parts = Array.from({ length: 40 }, () => push(new Float32Array(10).fill(1))).flat();
    expect(whole.length).toBe(7);
    expect(parts.length).toBe(7);
    expect(parts.map((p) => p.mosquito)).toEqual(whole.map((p) => p.mosquito));
  });
});

describe("createDecision", () => {
  it("needs three of four windows, reports once, and again after four quiet windows", () => {
    const next = createDecision(CLASSES);
    expect([r(0.9), r(0.2), r(0.9)].map(next)).toEqual([null, null, null]);
    expect(next(r(0.9))).toMatchObject({ label: "An. arabiensis", confidence: expect.closeTo(0.8, 6), genus: "Anopheles" });
    expect(next(r(0.9))).toBeNull();
    [r(0.1), r(0.1), r(0.1), r(0.1)].forEach(next);
    expect([r(0.9), r(0.9)].map(next)).toEqual([null, null]);
    expect(next(r(0.9))?.label).toBe("An. arabiensis");
  });

  it("reports another species only once it outweighs everything heard so far", () => {
    const next = createDecision(CLASSES);
    [r(0.9), r(0.9), r(0.9)].forEach(next);
    const changed = [r(0.9, [0.1, 0.9]), r(0.9, [0.1, 0.9]), r(0.9, [0.1, 0.9])].map(next).filter(Boolean);
    // after three windows of each the new species leads: (0.2 * 3 + 0.9 * 3) / 6 against (0.8 * 3 + 0.1 * 3) / 6
    expect(changed).toMatchObject([{ label: "Ae. aegypti", confidence: expect.closeTo(0.55, 6), genus: "Aedes", genusConfidence: expect.closeTo(0.55, 6) }]);
  });
});

describe("withGenus", () => {
  it("sums the probability of every species in the winning species' genus", () => {
    const classes = ["An. arabiensis", "An. funestus", "Cx. pipiens complex", "Ae. aegypti"];
    expect(withGenus(classes, [0.5, 0.3, 0.15, 0.05])).toEqual({ label: "An. arabiensis", confidence: 0.5, genus: "Anopheles", genusConfidence: 0.8 });
  });
});

describe("createMeter", () => {
  const feed = (meter: ReturnType<typeof createMeter>, value: number, seconds: number) => {
    let last = null;
    for (let i = 0; i < (8000 * seconds) / 128; i++) last = meter(new Float32Array(128).fill(value)) ?? last;
    return last;
  };

  it("reports a level every quarter second, low for a quiet room and high for a loud sound", () => {
    const meter = createMeter(8000);
    expect(meter(new Float32Array(1999).fill(0.5))).toBeNull();
    expect(meter(new Float32Array(1).fill(0.5))).toMatchObject({ silent: false });
    expect(feed(createMeter(8000), 0.001, 1)!.level).toBeCloseTo(1 / 6, 2);
    expect(feed(createMeter(8000), 0.3, 1)!.level).toBeGreaterThan(0.9);
  });

  it("calls a microphone silent only after two seconds of exact silence, and hears it again at once", () => {
    const meter = createMeter(8000);
    expect(feed(meter, 0, 1.5)).toMatchObject({ level: 0, silent: false });
    expect(feed(meter, 0, 1)).toMatchObject({ silent: true });
    expect(feed(meter, 0.001, 0.3)).toMatchObject({ silent: false });
    expect(feed(createMeter(8000), 0.001, 5)).toMatchObject({ silent: false });
  });
});

describe("createTape", () => {
  it("keeps the newest sound in order and writes it as a 16-bit mono WAV", () => {
    const tape = createTape(4, 2);
    tape.push(Float32Array.from([0.1, 0.2, 0.3]));
    tape.push(Float32Array.from([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, -1, 2]));
    const wav = new DataView(tape.wav());
    expect(String.fromCharCode(...new Uint8Array(wav.buffer, 0, 4))).toBe("RIFF");
    expect([wav.getUint16(22, true), wav.getUint32(24, true), wav.getUint16(34, true), wav.getUint32(40, true)]).toEqual([1, 4, 16, 16]);
    const samples = Array.from({ length: 8 }, (_, i) => wav.getInt16(44 + 2 * i, true) / 32767);
    [0.5, 0.6, 0.7, 0.8, 0.9, 1, -1, 1].forEach((v, i) => expect(samples[i]).toBeCloseTo(v, 3));
  });
});
