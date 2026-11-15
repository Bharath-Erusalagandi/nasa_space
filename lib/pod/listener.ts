import { createStore, useStore } from "zustand";
import type { Heard } from "@/lib/mission/chat";
import { loadMosquitoModel, type MosquitoModel } from "./mosquitoModel";
import { GENUS, speciesFor } from "./species";

export type Listening = "off" | "starting" | "on" | "denied" | "unsupported" | "failed";

export type Detection = Heard & { at: string };

type Result = { mosquito: number; species: number[] };

// scores the newest window of audio every `every` samples
export function createScorer(model: MosquitoModel, every = model.rate / 2) {
  const size = model.windowSamples;
  const buffer = new Float32Array(size);
  let filled = 0;
  let sinceLast = 0;

  function score(): Result {
    const x = model.features(buffer);
    const mosquito = model.detector(x)[1];
    return { mosquito, species: model.species(x) };
  }

  return function push(chunk: Float32Array): Result[] {
    const results: Result[] = [];
    for (let at = 0; at < chunk.length; ) {
      const n = Math.min(chunk.length - at, every - sinceLast);
      if (n >= size) buffer.set(chunk.subarray(at + n - size, at + n));
      else {
        buffer.copyWithin(0, n);
        buffer.set(chunk.subarray(at, at + n), size - n);
      }
      at += n;
      filled = Math.min(size, filled + n);
      sinceLast += n;
      if (sinceLast >= every) {
        sinceLast = 0;
        if (filled === size) results.push(score());
      }
    }
    return results;
  };
}

type DecisionOptions = { need?: number; of?: number; release?: number; threshold?: number };

// A mosquito counts as heard once `need` of the last `of` windows say so. The species is the mean over every
// accepted window since then, so it settles as the mosquito keeps sounding instead of following each window.
// It is reported again only when that mean names another species, or after `release` quiet windows in a row.
export function createDecision(classes: string[], { need = 3, of = 4, release = 4, threshold = 0.5 }: DecisionOptions = {}) {
  let recent: Result[] = [];
  let quiet = 0;
  let reported: string | null = null;
  let accepted: Result[] = [];

  return function next(result: Result): ReturnType<typeof withGenus> | null {
    const positive = result.mosquito >= threshold;
    recent = [...recent, result].slice(-of);
    quiet = positive ? 0 : quiet + 1;
    if (quiet >= release) {
      reported = null;
      accepted = [];
      recent = [];
    }
    if (accepted.length) {
      if (positive) accepted.push(result);
    } else {
      const first = recent.filter((r) => r.mosquito >= threshold);
      if (first.length < need) return null;
      accepted = first;
    }
    const mean = classes.map((_, c) => accepted.reduce((s, r) => s + r.species[c], 0) / accepted.length);
    const best = mean.indexOf(Math.max(...mean));
    if (classes[best] === reported) return null;
    reported = classes[best];
    return withGenus(classes, mean);
  };
}

// the genus is what the advice turns on, and its probability is the sum over its species
export function withGenus(classes: string[], probs: number[]) {
  const best = probs.indexOf(Math.max(...probs));
  const label = classes[best];
  const group = speciesFor(label)?.group;
  const genusConfidence = classes.reduce((sum, c, i) => (speciesFor(c)?.group === group ? sum + probs[i] : sum), 0);
  return { label, confidence: probs[best], genus: group ? GENUS[group] : label, genusConfidence };
}

// The level of the newest quarter second on a 0 to 1 scale (-70 to -10 dB), and whether the microphone
// has sent nothing at all for two seconds: a muted or disconnected one sends exact silence, a quiet room does not.
export function createMeter(rate: number, every = rate / 4, deadAfter = rate * 2) {
  let sum = 0;
  let count = 0;
  let dead = 0;

  return function push(chunk: Float32Array): { level: number; silent: boolean } | null {
    for (let i = 0; i < chunk.length; i++) sum += chunk[i] * chunk[i];
    count += chunk.length;
    if (count < every) return null;
    const rms = Math.sqrt(sum / count);
    dead = rms < 1e-4 ? dead + count : 0;
    sum = 0;
    count = 0;
    const db = 20 * Math.log10(Math.max(rms, 1e-6));
    return { level: Math.min(1, Math.max(0, (db + 70) / 60)), silent: dead >= deadAfter };
  };
}

// The last `seconds` the microphone heard, held in memory only, so a test can be saved and scored again later.
export function createTape(rate: number, seconds = 20) {
  const data = new Float32Array(rate * seconds);
  let at = 0;
  let filled = 0;

  return {
    push(chunk: Float32Array) {
      for (let i = 0; i < chunk.length; i++) {
        data[at] = chunk[i];
        at = (at + 1) % data.length;
      }
      filled = Math.min(data.length, filled + chunk.length);
    },
    // a 16-bit mono WAV file, oldest sample first
    wav(): ArrayBuffer {
      const out = new DataView(new ArrayBuffer(44 + 2 * filled));
      const text = (offset: number, word: string) => [...word].forEach((c, i) => out.setUint8(offset + i, c.charCodeAt(0)));
      text(0, "RIFF");
      out.setUint32(4, 36 + 2 * filled, true);
      text(8, "WAVEfmt ");
      out.setUint32(16, 16, true);
      out.setUint16(20, 1, true);
      out.setUint16(22, 1, true);
      out.setUint32(24, rate, true);
      out.setUint32(28, 2 * rate, true);
      out.setUint16(32, 2, true);
      out.setUint16(34, 16, true);
      text(36, "data");
      out.setUint32(40, 2 * filled, true);
      const start = (at - filled + data.length) % data.length;
      for (let i = 0; i < filled; i++) {
        const sample = Math.max(-1, Math.min(1, data[(start + i) % data.length]));
        out.setInt16(44 + 2 * i, Math.round(sample * 32767), true);
      }
      return out.buffer;
    },
  };
}

let tape: ReturnType<typeof createTape> | null = null;

// downloads what the microphone heard in the last 20 seconds
export function saveHeard(): void {
  if (!tape) return;
  const url = URL.createObjectURL(new Blob([tape.wav()], { type: "audio/wav" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "microphone.wav";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export type Microphone = { id: string; label: string };

type State = {
  status: Listening;
  heard: Detection | null;
  note: string | null;
  // the microphone in use, and the ones the browser offers
  microphone: string | null;
  microphones: Microphone[];
  level: number;
  silent: boolean;
  // how much the newest window sounds like a mosquito, 0 to 1
  score: number | null;
};

const IDLE = { microphone: null, microphones: [], level: 0, silent: false, score: null };

export const listenerStore = createStore<State>()(() => ({ status: "off", heard: null, note: null, ...IDLE }));
const set = (patch: Partial<State>) => listenerStore.setState(patch);

const CHOSEN = "orbit:microphone";

function chosen(): string | null {
  try {
    return localStorage.getItem(CHOSEN);
  } catch {
    return null;
  }
}

function remember(id: string | null) {
  try {
    if (id) localStorage.setItem(CHOSEN, id);
    else localStorage.removeItem(CHOSEN);
  } catch {}
}

// the browser's voice filters change the sound the model was trained on, so they are off
const RAW = { echoCancellation: false, noiseSuppression: false, autoGainControl: false };

// opens the chosen microphone, or the computer's default one when none is chosen or the chosen one is gone
async function open(media: MediaDevices): Promise<MediaStream> {
  const id = chosen();
  if (!id) return media.getUserMedia({ audio: RAW });
  try {
    return await media.getUserMedia({ audio: { ...RAW, deviceId: { exact: id } } });
  } catch (error) {
    if ((error as DOMException).name !== "OverconstrainedError" && (error as DOMException).name !== "NotFoundError") throw error;
    remember(null);
    return media.getUserMedia({ audio: RAW });
  }
}

async function microphones(media: MediaDevices): Promise<Microphone[]> {
  const devices = await media.enumerateDevices().catch(() => []);
  return devices.filter((d) => d.kind === "audioinput" && d.label && d.deviceId !== "communications").map((d) => ({ id: d.deviceId, label: d.label }));
}

let stop: (() => void) | null = null;
let cancelled = false;

const TAP = `class Tap extends AudioWorkletProcessor {
  process(inputs) { const ch = inputs[0] && inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; }
}
registerProcessor("tap", Tap);`;

// the pod's microphone reaches the laptop as an audio input; this listens to the one the browser is given
export async function startListening(): Promise<void> {
  if (stop || listenerStore.getState().status === "starting") return;
  const media = typeof navigator === "undefined" ? undefined : navigator.mediaDevices;
  if (!media?.getUserMedia || typeof AudioContext === "undefined") return set({ status: "unsupported" });

  set({ status: "starting", note: null });
  cancelled = false;
  let model: MosquitoModel;
  try {
    model = await loadMosquitoModel();
  } catch {
    return set({ status: "failed", note: "The mosquito model could not be loaded." });
  }
  let stream: MediaStream;
  try {
    stream = await open(media);
  } catch {
    return set({ status: "denied" });
  }
  if (cancelled) {
    for (const track of stream.getTracks()) track.stop();
    return set({ status: "off" });
  }

  const context = new AudioContext({ sampleRate: model.rate });
  await context.resume().catch(() => {});
  const source = context.createMediaStreamSource(stream);
  const push = createScorer(model);
  const decide = createDecision(model.speciesClasses);
  const meter = createMeter(model.rate);
  tape = createTape(model.rate);
  const onAudio = (chunk: Float32Array) => {
    tape?.push(chunk);
    const measured = meter(chunk);
    if (measured) set(measured);
    for (const result of push(chunk)) {
      set({ score: result.mosquito });
      const found = decide(result);
      if (found) report(found);
    }
  };

  let node: AudioNode;
  try {
    const url = URL.createObjectURL(new Blob([TAP], { type: "text/javascript" }));
    await context.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    const tap = new AudioWorkletNode(context, "tap");
    tap.port.onmessage = (event: MessageEvent<Float32Array>) => onAudio(event.data);
    node = tap;
  } catch {
    const processor = context.createScriptProcessor(1024, 1, 1);
    processor.onaudioprocess = (event) => onAudio(new Float32Array(event.inputBuffer.getChannelData(0)));
    node = processor;
  }
  source.connect(node);
  node.connect(context.destination);

  stop = () => {
    source.disconnect();
    node.disconnect();
    for (const track of stream.getTracks()) track.stop();
    void context.close().catch(() => {});
    stop = null;
    set({ status: "off", ...IDLE });
  };
  const track = stream.getAudioTracks()[0];
  set({ status: "on", microphone: track?.getSettings().deviceId ?? null, microphones: await microphones(media) });
}

// switches to another microphone and keeps the choice for next time
export function chooseMicrophone(id: string): void {
  remember(id);
  if (!stop) return;
  stop();
  void startListening();
}

export function stopListening(): void {
  if (listenerStore.getState().status === "starting") {
    cancelled = true;
    set({ status: "off" });
  }
  stop?.();
}

// a detection is the browser's own, from whatever microphone it was given, so it is not stored as a pod reading
function report(found: Heard) {
  set({ heard: { ...found, at: new Date().toISOString() } });
}

export const useListener = <T>(select: (state: State) => T) => useStore(listenerStore, select);
