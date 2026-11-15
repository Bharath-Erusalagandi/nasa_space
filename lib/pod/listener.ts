import { createStore, useStore } from "zustand";
import type { Heard } from "@/lib/mission/chat";
import { loadMosquitoModel, type MosquitoModel } from "./mosquitoModel";
import { GENUS, speciesFor } from "./species";

export type Listening = "off" | "starting" | "on" | "denied" | "unsupported" | "failed";

export type Detection = Heard & { at: string; clip?: string };

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

// A mosquito counts as heard once `need` of the last `of` windows say so; the species is the mean over those
// windows. It is reported again only after `release` quiet windows in a row, or when the species changes.
export function createDecision(classes: string[], { need = 3, of = 4, release = 4, threshold = 0.5 }: DecisionOptions = {}) {
  let recent: Result[] = [];
  let quiet = 0;
  let reported: string | null = null;

  return function next(result: Result): ReturnType<typeof withGenus> | null {
    recent = [...recent, result].slice(-of);
    quiet = result.mosquito >= threshold ? 0 : quiet + 1;
    if (quiet >= release) reported = null;
    const positive = recent.filter((r) => r.mosquito >= threshold);
    if (positive.length < need) return null;
    const mean = classes.map((_, c) => positive.reduce((s, r) => s + r.species[c], 0) / positive.length);
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

type State = { status: Listening; heard: Detection | null; playing: string | null; note: string | null };

export const listenerStore = createStore<State>()(() => ({ status: "off", heard: null, playing: null, note: null }));
const set = (patch: Partial<State>) => listenerStore.setState(patch);

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
    // the browser's voice filters change the sound the model was trained on, so they are off
    stream = await media.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
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
  const onAudio = (chunk: Float32Array) => {
    // a clip playing from this page would reach the microphone too; it is scored from the file instead
    if (listenerStore.getState().playing) return;
    for (const result of push(chunk)) {
      const found = decide(result);
      if (found) report({ ...found, via: "microphone" });
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
    set({ status: "off" });
  };
  set({ status: "on" });
}

export function stopListening(): void {
  if (listenerStore.getState().status === "starting") {
    cancelled = true;
    set({ status: "off" });
  }
  stop?.();
}

// a detection is the browser's own, from whatever microphone it was given, so it is not stored as a pod reading
function report(found: Omit<Detection, "at">) {
  set({ heard: { ...found, at: new Date().toISOString() } });
}

// runs the model over a whole recording: the species is the mean over the windows the detector accepts
export function classifySignal(model: MosquitoModel, signal: Float32Array, need = 3, threshold = 0.5) {
  const results = createScorer(model)(signal);
  const positive = results.filter((r) => r.mosquito >= threshold);
  if (positive.length < Math.min(need, results.length) || positive.length === 0) return null;
  const mean = model.speciesClasses.map((_, c) => positive.reduce((s, r) => s + r.species[c], 0) / positive.length);
  return withGenus(model.speciesClasses, mean);
}

async function decode(url: string, rate: number): Promise<Float32Array> {
  const data = await (await fetch(url)).arrayBuffer();
  const probe = new OfflineAudioContext(1, 1, rate);
  const audio = await probe.decodeAudioData(data);
  const offline = new OfflineAudioContext(1, Math.ceil(audio.duration * rate), rate);
  const source = offline.createBufferSource();
  source.buffer = audio;
  source.connect(offline.destination);
  source.start();
  return (await offline.startRendering()).getChannelData(0);
}

let clip: { url: string; audio: HTMLAudioElement; done: () => void } | null = null;

// stops the clip playing now, if any
export function stopClip(): void {
  if (!clip) return;
  clip.audio.pause();
  clip.done();
  clip = null;
  set({ playing: null });
}

// Plays a recorded clip out loud and scores the file itself; the result is labelled as a recording.
// Tapping the clip again stops it, and tapping another one switches to it.
export async function playClip(url: string): Promise<void> {
  const again = clip?.url === url;
  stopClip();
  if (again) return;
  set({ playing: url, note: null });
  const audio = new Audio(url);
  const ended = new Promise<void>((resolve) => {
    clip = { url, audio, done: resolve };
    audio.onended = () => resolve();
    audio.onerror = () => resolve();
  });
  void audio.play().catch(() => {});
  try {
    const model = await loadMosquitoModel();
    const found = classifySignal(model, await decode(url, model.rate));
    if (clip?.url === url) {
      if (found) report({ ...found, via: "recording", clip: url });
      else set({ note: "No mosquito found in that recording." });
    }
    await ended;
  } catch {
    set({ note: "That recording could not be played." });
  } finally {
    if (clip?.url === url) {
      clip = null;
      set({ playing: null });
    }
  }
}

export const useListener = <T>(select: (state: State) => T) => useStore(listenerStore, select);
