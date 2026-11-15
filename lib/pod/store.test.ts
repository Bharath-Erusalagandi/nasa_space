import { describe, expect, test } from "vitest";
import { createPodStore, OFFLINE_AFTER_MS } from "./store";

function setup(start = Date.UTC(2026, 10, 15, 9, 0, 0)) {
  let now = start;
  const store = createPodStore(() => now);
  return { store, state: () => store.getState(), advance: (ms: number) => (now += ms), now: () => now };
}

describe("pod store", () => {
  test("starts empty and offline", () => {
    const { state } = setup();
    expect(state().source).toBe("none");
    expect(state().latest).toEqual({});
    expect(state().isOffline()).toBe(true);
  });

  test("ingestLine stores the newest event of each kind with pod id and time", () => {
    const { state, advance } = setup();
    state().ingestLine('{"k":"hr","v":72,"q":0.93}', "live");
    advance(400);
    state().ingestLine('{"k":"hr","v":75,"q":0.9}', "live");
    state().ingestLine('{"k":"temp","v":24.1}', "live");
    expect(state().latest.heart_rate).toEqual({
      kind: "heart_rate", value: 75, label: null, unit: "bpm", quality: 0.9, pod_id: "K-01", at: "2026-11-15T09:00:00.400Z", source: "live",
    });
    expect(state().latest.air_temp_c?.value).toBe(24.1);
    expect(state().source).toBe("live");
    expect(state().lastEventAt).toBe(Date.UTC(2026, 10, 15, 9, 0, 0, 400));
  });

  test("bad lines are counted and dropped", () => {
    const { state } = setup();
    expect(state().ingestLine("boot ok", "live")).toBeNull();
    expect(state().ingestLine('{"k":"hr","v":0}', "live")).toBeNull();
    expect(state().dropped).toBe(2);
    expect(state().latest).toEqual({});
    expect(state().lastEventAt).toBeNull();
    expect(state().source).toBe("none");
  });

  test("ingestEvent takes replayed events and marks the source", () => {
    const { state } = setup();
    state().ingestEvent({ kind: "spo2", value: 97, label: null, unit: "%", quality: 1 }, "replay");
    expect(state().source).toBe("replay");
    expect(state().latest.spo2?.pod_id).toBe("K-01");
  });

  test("mosquito events are kept in a session log", () => {
    const { state } = setup();
    state().ingestLine('{"k":"mosq","label":"An. arabiensis","conf":0.84}', "simulation");
    state().ingestLine('{"k":"hr","v":72}', "simulation");
    state().ingestLine('{"k":"mosq","label":"Culex quinquefasciatus","conf":0.6}', "simulation");
    expect(state().mosquitoes.map((e) => e.label)).toEqual(["An. arabiensis", "Culex quinquefasciatus"]);
    expect(state().latest.mosquito?.label).toBe("Culex quinquefasciatus");
  });

  test("goes offline 5000 ms after the last event", () => {
    const { state, advance, now } = setup();
    state().ingestLine('{"k":"hr","v":72}', "live");
    advance(OFFLINE_AFTER_MS - 1);
    expect(state().isOffline()).toBe(false);
    advance(1);
    expect(state().isOffline()).toBe(true);
    expect(state().isOffline(now() - 10)).toBe(false);
  });

  test("tracks the serial connection and resets readings", () => {
    const { state } = setup();
    state().setConnection("connected");
    state().ingestLine('{"k":"rh","v":41}', "live");
    state().reset();
    expect(state().connection).toBe("connected");
    expect(state().latest).toEqual({});
    expect(state().source).toBe("none");
  });

  test("a reading from another source clears what was on screen first", () => {
    const { state } = setup();
    state().ingestLine('{"k":"hr","v":72}', "live");
    state().ingestLine('{"k":"mosq","label":"An. funestus","conf":0.9}', "live");
    state().ingestEvent({ kind: "spo2", value: 95, label: null, unit: "%", quality: 1 }, "replay");
    expect(state().latest.heart_rate).toBeUndefined();
    expect(state().mosquitoes).toEqual([]);
    expect(state().latest.spo2?.source).toBe("replay");
    expect(state().source).toBe("replay");
  });

  test("while a replay or the simulator runs, other lines are counted and not shown", () => {
    const { state } = setup();
    state().ingestLine('{"k":"hr","v":72}', "live");
    state().claim("simulation");
    expect(state().latest).toEqual({});
    expect(state().source).toBe("none");
    state().ingestLine('{"k":"hr","v":80}', "simulation");
    expect(state().ingestLine('{"k":"hr","v":200}', "live")).toBeNull();
    expect(state().held).toBe(1);
    expect(state().latest.heart_rate?.value).toBe(80);
    expect(state().source).toBe("simulation");
  });

  test("release clears the readings of the source that stopped", () => {
    const { state } = setup();
    state().claim("replay");
    state().ingestEvent({ kind: "heart_rate", value: 90, label: null, unit: "bpm", quality: null }, "replay");
    state().release("replay");
    expect(state().running).toBeNull();
    expect(state().latest).toEqual({});
    expect(state().last).toBeNull();
    expect(state().lastEventAt).toBeNull();
    expect(state().source).toBe("none");
    state().ingestLine('{"k":"hr","v":72}', "live");
    expect(state().latest.heart_rate?.source).toBe("live");
  });

  test("releasing a source that is not running changes nothing", () => {
    const { state } = setup();
    state().ingestLine('{"k":"hr","v":72}', "live");
    state().release("replay");
    expect(state().latest.heart_rate?.value).toBe(72);
  });
});


describe("car kit acknowledgements", () => {
  test("a live acknowledgement is kept with its time and is not a dropped line", () => {
    const { state, advance } = setup();
    advance(1500);
    expect(state().ingestLine('{"ack":"dispatch"}', "live")).toBeNull();
    expect(state().ack).toEqual({ command: "dispatch", at: "2026-11-15T09:00:01.500Z" });
    expect(state().dropped).toBe(0);
    expect(state().lastEventAt).toBeNull();
  });

  test("only the connected pod can acknowledge, and reset clears it", () => {
    const { state } = setup();
    state().ingestLine('{"ack":"dispatch"}', "simulation");
    expect(state().ack).toBeNull();
    expect(state().dropped).toBe(1);
    state().ingestLine('{"ack":"dispatch"}', "live");
    state().reset();
    expect(state().ack).toBeNull();
  });

  test("distance and light are stored like any other reading", () => {
    const { state } = setup();
    state().ingestLine('{"k":"dist","v":23.4}', "live");
    state().ingestLine('{"k":"light","v":62}', "live");
    expect(state().latest.distance_cm).toMatchObject({ value: 23.4, unit: "cm", source: "live" });
    expect(state().latest.light_pct).toMatchObject({ value: 62, unit: "%", source: "live" });
  });
});
