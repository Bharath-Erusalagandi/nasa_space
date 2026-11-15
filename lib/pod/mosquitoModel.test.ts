import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { createModel, type ModelFile } from "./mosquitoModel";

// written by models/mosquito/train.py: raw audio from test recordings, with the features and outputs PyTorch gave
type Fixture = { label: string; signal: number[]; features_head: number[]; detector: number[]; species: number[] };

const file = JSON.parse(readFileSync("public/models/mosquito.json", "utf8")) as ModelFile;
const fixtures = JSON.parse(readFileSync("lib/pod/__fixtures__/mosquito.json", "utf8")) as Fixture[];
const model = createModel(file);

describe("mosquito model in the browser matches the Python model", () => {
  it("has the 8 species and a full window of about 2.1 s", () => {
    expect(model.speciesClasses).toHaveLength(8);
    expect(model.windowSamples / model.rate).toBeCloseTo(2.112, 3);
  });

  for (const f of fixtures) {
    it(`features and both outputs agree on a ${f.label} test window`, () => {
      const x = model.features(Float32Array.from(f.signal));
      const head = [0, 1, 2, 3].flatMap((m) => [0, 1, 2, 3].map((t) => x[m * file.frames + t]));
      head.forEach((v, i) => expect(v).toBeCloseTo(f.features_head[i], 3));
      model.detector(x).forEach((p, i) => expect(p).toBeCloseTo(f.detector[i], 3));
      model.species(x).forEach((p, i) => expect(p).toBeCloseTo(f.species[i], 3));
    });
  }
});
