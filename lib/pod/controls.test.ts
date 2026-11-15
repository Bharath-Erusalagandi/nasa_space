import { describe, expect, test } from "vitest";
import { createPodControls } from "./controls";
import type { RecordedEvent } from "./recorder";
import { createPodStore } from "./store";

const hr = (value: number, t: number): RecordedEvent => ({ kind: "heart_rate", value, label: null, unit: "bpm", quality: 0.9, t });

function setup(events: RecordedEvent[] = [hr(91, 0), hr(92, 10)]) {
  const pod = createPodStore();
  const notes: string[] = [];
  let simulating = 0;
  const controls = createPodControls({
    pod,
    load: async () => events,
    simulate: () => {
      simulating++;
      return () => void simulating--;
    },
    notify: (message) => void notes.push(message),
  });
  const live = (v: number) => pod.getState().ingestLine(`{"k":"hr","v":${v}}`, "live");
  const shown = () => pod.getState().latest.heart_rate;
  return { pod, controls, notes, live, shown, simulating: () => simulating };
}

describe("pod controls", () => {
  test("a replay that runs to its end clears its readings", async () => {
    const { pod, controls, live, shown } = setup();
    live(72);
    await controls.startReplay();
    expect(controls.state.getState().replaying).toBe(false);
    expect(shown()).toBeUndefined();
    expect(pod.getState().source).toBe("none");
    expect(pod.getState().running).toBeNull();
    live(73);
    expect(shown()?.source).toBe("live");
  });

  test("live, then replay, then live: live lines are held while the replay runs and nothing stale comes back", async () => {
    const { pod, controls, live, shown } = setup([hr(91, 0), hr(92, 60_000)]);
    live(72);
    const running = controls.startReplay();
    await new Promise((r) => setTimeout(r, 20));
    expect(shown()).toMatchObject({ value: 91, source: "replay" });
    expect(live(75)).toBeNull();
    expect(shown()?.value).toBe(91);
    expect(pod.getState().held).toBe(1);
    controls.stopReplay();
    await running;
    expect(shown()).toBeUndefined();
    expect(pod.getState().source).toBe("none");
    live(76);
    expect(shown()).toMatchObject({ value: 76, source: "live" });
  });

  test("the simulator holds live lines and clears its readings when it stops", () => {
    const { pod, controls, live, shown, simulating } = setup();
    live(72);
    controls.startSimulation();
    expect(simulating()).toBe(1);
    expect(shown()).toBeUndefined();
    pod.getState().ingestLine('{"k":"hr","v":80}', "simulation");
    expect(live(200)).toBeNull();
    expect(shown()).toMatchObject({ value: 80, source: "simulation" });
    controls.stopSimulation();
    expect(simulating()).toBe(0);
    expect(shown()).toBeUndefined();
    expect(pod.getState().source).toBe("none");
  });

  test("a replay pauses the simulator and hands back to it when it ends", async () => {
    const { pod, controls, simulating } = setup();
    controls.startSimulation();
    await controls.startReplay();
    expect(simulating()).toBe(1);
    expect(pod.getState().running).toBe("simulation");
  });

  test("no replay file shows a note and leaves the screen alone", async () => {
    const { controls, notes, live, shown } = setup([]);
    live(72);
    await controls.startReplay();
    expect(notes).toEqual(["No replay recorded yet"]);
    expect(shown()?.value).toBe(72);
  });
});
