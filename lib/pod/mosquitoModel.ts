// The two mosquito models from models/mosquito/train.py, run in the browser with no library.
// features() must match models/mosquito/features.py; lib/pod/mosquitoModel.test.ts checks it against Python output.

type Band = { start: number; w: number[] };
type ConvSpec = { type: "conv"; in: number; out: number; w: string; b: string };
type DenseSpec = { type: "dense"; in: number; out: number; w: string; b: string };
type LayerSpec = ConvSpec | DenseSpec | { type: "pool" };
type NetSpec = { classes: string[]; layers: LayerSpec[] };

export type ModelFile = {
  rate: number;
  n_fft: number;
  hop: number;
  n_mels: number;
  frames: number;
  top_db: number;
  mel: Band[];
  detector: NetSpec;
  species: NetSpec;
};

type Conv = { type: "conv"; cin: number; cout: number; w: Float32Array; b: Float32Array };
type Dense = { type: "dense"; cin: number; cout: number; w: Float32Array; b: Float32Array };
type Layer = Conv | Dense | { type: "pool" };
type Net = { classes: string[]; layers: Layer[] };

export type MosquitoModel = {
  rate: number;
  windowSamples: number;
  features: (signal: Float32Array, start?: number) => Float32Array;
  detector: (x: Float32Array) => number[];
  species: (x: Float32Array) => number[];
  speciesClasses: string[];
};

function floats(b64: string): Float32Array {
  const bytes = typeof atob === "function" ? Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)) : new Uint8Array(Buffer.from(b64, "base64"));
  return new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4);
}

function net(spec: NetSpec): Net {
  const layers = spec.layers.map((l): Layer => {
    if (l.type === "pool") return l;
    if (l.type === "conv") return { type: "conv", cin: l.in, cout: l.out, w: floats(l.w), b: floats(l.b) };
    return { type: "dense", cin: l.in, cout: l.out, w: floats(l.w), b: floats(l.b) };
  });
  return { classes: spec.classes, layers };
}

// in-place radix-2 FFT
function fft(re: Float64Array, im: Float64Array) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }
  for (let size = 2; size <= n; size <<= 1) {
    const step = (-2 * Math.PI) / size;
    for (let start = 0; start < n; start += size) {
      for (let k = 0; k < size / 2; k++) {
        const c = Math.cos(step * k);
        const s = Math.sin(step * k);
        const a = start + k;
        const b = a + size / 2;
        const tr = re[b] * c - im[b] * s;
        const ti = re[b] * s + im[b] * c;
        re[b] = re[a] - tr;
        im[b] = im[a] - ti;
        re[a] += tr;
        im[a] += ti;
      }
    }
  }
}

function conv(x: Float32Array, h: number, w: number, l: Conv): Float32Array {
  const out = new Float32Array(l.cout * h * w);
  for (let o = 0; o < l.cout; o++) {
    const bias = l.b[o];
    for (let y = 0; y < h; y++) {
      for (let xx = 0; xx < w; xx++) {
        let sum = bias;
        for (let c = 0; c < l.cin; c++) {
          const wBase = (o * l.cin + c) * 9;
          const xBase = c * h * w;
          for (let ky = 0; ky < 3; ky++) {
            const yy = y + ky - 1;
            if (yy < 0 || yy >= h) continue;
            for (let kx = 0; kx < 3; kx++) {
              const xi = xx + kx - 1;
              if (xi < 0 || xi >= w) continue;
              sum += l.w[wBase + ky * 3 + kx] * x[xBase + yy * w + xi];
            }
          }
        }
        out[(o * h + y) * w + xx] = sum > 0 ? sum : 0;
      }
    }
  }
  return out;
}

function pool(x: Float32Array, c: number, h: number, w: number): [Float32Array, number, number] {
  const ph = Math.floor(h / 2);
  const pw = Math.floor(w / 2);
  const out = new Float32Array(c * ph * pw);
  for (let k = 0; k < c; k++) {
    for (let y = 0; y < ph; y++) {
      for (let xx = 0; xx < pw; xx++) {
        const i = (k * h + 2 * y) * w + 2 * xx;
        out[(k * ph + y) * pw + xx] = Math.max(x[i], x[i + 1], x[i + w], x[i + w + 1]);
      }
    }
  }
  return [out, ph, pw];
}

function softmax(z: number[]): number[] {
  const top = Math.max(...z);
  const e = z.map((v) => Math.exp(v - top));
  const sum = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / sum);
}

function forward(model: Net, input: Float32Array, h: number, w: number): number[] {
  let x = input;
  let channels = 1;
  for (const l of model.layers) {
    if (l.type === "conv") {
      x = conv(x, h, w, l);
      channels = l.cout;
    } else if (l.type === "pool") {
      [x, h, w] = pool(x, channels, h, w);
    } else {
      const mean = new Array<number>(channels).fill(0);
      for (let c = 0; c < channels; c++) {
        for (let i = 0; i < h * w; i++) mean[c] += x[c * h * w + i];
        mean[c] /= h * w;
      }
      const logits = Array.from({ length: l.cout }, (_, o) => l.b[o] + mean.reduce((s, v, c) => s + v * l.w[o * l.cin + c], 0));
      return softmax(logits);
    }
  }
  throw new Error("model has no dense layer");
}

export function createModel(file: ModelFile): MosquitoModel {
  const { n_fft: nFft, hop, n_mels: nMels, frames, top_db: topDb } = file;
  const hann = Float64Array.from({ length: nFft }, (_, i) => 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / nFft));
  const bins = nFft / 2 + 1;
  const detector = net(file.detector);
  const species = net(file.species);

  // (n_mels, frames) row-major, as the models were trained
  function features(signal: Float32Array, start = 0): Float32Array {
    const db = new Float64Array(nMels * frames);
    const re = new Float64Array(nFft);
    const im = new Float64Array(nFft);
    const power = new Float64Array(bins);
    for (let f = 0; f < frames; f++) {
      const offset = start + f * hop;
      for (let i = 0; i < nFft; i++) {
        re[i] = (signal[offset + i] ?? 0) * hann[i];
        im[i] = 0;
      }
      fft(re, im);
      for (let k = 0; k < bins; k++) power[k] = re[k] * re[k] + im[k] * im[k];
      file.mel.forEach((band, m) => {
        let sum = 0;
        for (let j = 0; j < band.w.length; j++) sum += band.w[j] * power[band.start + j];
        db[m * frames + f] = 10 * Math.log10(Math.max(sum, 1e-10));
      });
    }
    let top = -Infinity;
    for (const v of db) top = Math.max(top, v);
    let mean = 0;
    for (let i = 0; i < db.length; i++) {
      db[i] = Math.max(db[i] - top, -topDb);
      mean += db[i];
    }
    mean /= db.length;
    let variance = 0;
    for (const v of db) variance += (v - mean) ** 2;
    const std = Math.sqrt(variance / db.length);
    const scale = std > 1e-6 ? std : 1;
    return Float32Array.from(db, (v) => (v - mean) / scale);
  }

  return {
    rate: file.rate,
    windowSamples: nFft + (frames - 1) * hop,
    features,
    detector: (x) => forward(detector, x, nMels, frames),
    species: (x) => forward(species, x, nMels, frames),
    speciesClasses: species.classes,
  };
}

let loading: Promise<MosquitoModel> | null = null;

export function loadMosquitoModel(): Promise<MosquitoModel> {
  loading ??= fetch("/models/mosquito.json")
    .then((r) => {
      if (!r.ok) throw new Error(`mosquito model: HTTP ${r.status}`);
      return r.json() as Promise<ModelFile>;
    })
    .then(createModel)
    .catch((error) => {
      loading = null;
      throw error;
    });
  return loading;
}
