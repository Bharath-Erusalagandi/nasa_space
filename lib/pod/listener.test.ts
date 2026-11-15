import { describe, expect, it } from "vitest";
import { classifySignal, createDecision, createScorer, withGenus } from "./listener";
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

  it("reports a change of species straight away", () => {
    const next = createDecision(CLASSES);
    [r(0.9), r(0.9), r(0.9)].forEach(next);
    const changed = [r(0.9, [0.1, 0.9]), r(0.9, [0.1, 0.9]), r(0.9, [0.1, 0.9])].map(next).filter(Boolean);
    // two of the four windows are the new species, which already outweighs the old one: (0.2 + 0.2 + 0.9 + 0.9) / 4
    expect(changed).toMatchObject([{ label: "Ae. aegypti", confidence: expect.closeTo(0.55, 6), genus: "Aedes", genusConfidence: expect.closeTo(0.55, 6) }]);
  });
});

describe("withGenus", () => {
  it("sums the probability of every species in the winning species' genus", () => {
    const classes = ["An. arabiensis", "An. funestus", "Cx. pipiens complex", "Ae. aegypti"];
    expect(withGenus(classes, [0.5, 0.3, 0.15, 0.05])).toEqual({ label: "An. arabiensis", confidence: 0.5, genus: "Anopheles", genusConfidence: 0.8 });
  });
});

describe("classifySignal", () => {
  it("averages the species over the windows the detector accepts", () => {
    const loud = new Float32Array(8000 * 3).fill(1);
    expect(classifySignal(fakeModel(), loud)).toMatchObject({ label: "An. arabiensis", confidence: expect.closeTo(0.8, 6) });
  });

  it("gives nothing for quiet audio", () => {
    expect(classifySignal(fakeModel(), new Float32Array(8000 * 3))).toBeNull();
  });
});
