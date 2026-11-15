import { describe, expect, test } from "vitest";
import { createRecorder, recordFrom, recordingRequested } from "./recorder";
import { replay } from "./replay";
import { createPodStore } from "./store";

describe("recorder", () => {
  test("keeps events only while recording, with t since the start", () => {
    let now = 10_000;
    const store = createPodStore(() => now);
    const recorder = createRecorder(() => now);
    recordFrom(store, recorder);

    store.getState().ingestLine('{"k":"hr","v":70,"q":1}', "live");
    recorder.start();
    now += 250;
    store.getState().ingestLine('{"k":"hr","v":71,"q":1}', "live");
    store.getState().ingestLine("garbage", "live");
    now += 1000;
    store.getState().ingestLine('{"k":"mosq","label":"An. funestus","conf":0.7}', "live");
    recorder.stop();
    store.getState().ingestLine('{"k":"hr","v":72,"q":1}', "live");

    expect(recorder.toJSON()).toEqual([
      { kind: "heart_rate", value: 71, label: null, unit: "bpm", quality: 1, t: 250 },
      { kind: "mosquito", value: null, label: "An. funestus", unit: null, quality: 0.7, t: 1250 },
    ]);
    expect(recorder.isRecording()).toBe(false);
  });

  test("a recording replays through the same store", async () => {
    let now = 0;
    const recorder = createRecorder(() => now);
    recorder.start();
    recorder.add({ kind: "spo2", value: 97, label: null, unit: "%", quality: 0.9 });
    now = 1000;
    recorder.add({ kind: "spo2", value: 98, label: null, unit: "%", quality: 0.9 });

    const store = createPodStore(() => now);
    const waits: number[] = [];
    const saved = JSON.parse(JSON.stringify(recorder.toJSON()));
    await replay(saved, (e) => store.getState().ingestEvent(e, "replay"), 2, async (ms) => void waits.push(ms));
    expect(waits).toEqual([500]);
    expect(store.getState().latest.spo2?.value).toBe(98);
    expect(store.getState().source).toBe("replay");
  });

  test("starting again clears the earlier recording", () => {
    const recorder = createRecorder(() => 0);
    recorder.start();
    recorder.add({ kind: "humidity_pct", value: 40, label: null, unit: "%", quality: null });
    recorder.start();
    expect(recorder.toJSON()).toEqual([]);
  });

  test("only ?record=1 asks for recording", () => {
    expect(recordingRequested("?record=1")).toBe(true);
    expect(recordingRequested("?record=true")).toBe(false);
  });

  test("records only live readings, once each, never replayed, simulated or restored ones", () => {
    let now = 0;
    const store = createPodStore(() => now);
    const recorder = createRecorder(() => now);
    recorder.start();
    recordFrom(store, recorder);
    store.getState().ingestLine('{"k":"hr","v":70}', "live");
    const shown = store.getState();
    store.getState().ingestLine('{"k":"hr","v":71}', "simulation");
    store.getState().ingestEvent({ kind: "spo2", value: 97, label: null, unit: "%", quality: null }, "replay");
    store.setState({ latest: shown.latest, last: shown.last, source: shown.source });
    store.getState().setConnection("connected");
    now = 100;
    store.getState().ingestLine('{"k":"hr","v":72}', "live");
    expect(recorder.toJSON().map((e) => e.value)).toEqual([70, 72]);
  });
});

