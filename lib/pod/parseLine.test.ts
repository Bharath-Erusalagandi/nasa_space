import { describe, expect, test } from "vitest";
import { parseAck, parseLine } from "./parseLine";

describe("car kit lines", () => {
  test("distance and light parse inside their ranges only", () => {
    expect(parseLine('{"k":"dist","v":23.4}')).toEqual({ kind: "distance_cm", value: 23.4, label: null, unit: "cm", quality: null });
    expect(parseLine('{"k":"light","v":62}')).toEqual({ kind: "light_pct", value: 62, label: null, unit: "%", quality: null });
    expect(parseLine('{"k":"dist","v":1.9}')).toBeNull();
    expect(parseLine('{"k":"dist","v":401}')).toBeNull();
    expect(parseLine('{"k":"light","v":101}')).toBeNull();
  });

  test("an acknowledgement is not a reading", () => {
    expect(parseLine('{"ack":"dispatch"}')).toBeNull();
    expect(parseAck('{"ack":"dispatch"}\r')).toBe("dispatch");
    expect(parseAck('{"ack":""}')).toBeNull();
    expect(parseAck('{"ack":7}')).toBeNull();
    expect(parseAck('{"k":"dist","v":23.4}')).toBeNull();
    expect(parseAck("pod K-01 early prototype (Uno car kit) ready")).toBeNull();
  });
});

describe("parseLine quality", () => {
  test("keeps q and conf only when they are numbers from 0 to 1", () => {
    expect(parseLine('{"k":"hr","v":72,"q":0}')?.quality).toBe(0);
    expect(parseLine('{"k":"hr","v":72,"q":1}')?.quality).toBe(1);
    expect(parseLine('{"k":"hr","v":72,"q":1.5}')?.quality).toBeNull();
    expect(parseLine('{"k":"hr","v":72,"q":-0.1}')?.quality).toBeNull();
    expect(parseLine('{"k":"hr","v":72,"q":"0.9"}')?.quality).toBeNull();
    expect(parseLine('{"k":"mosq","label":"An. funestus","conf":84}')?.quality).toBeNull();
    expect(parseLine('{"k":"mosq","label":"An. funestus","conf":0.84}')?.quality).toBe(0.84);
  });

  test("a bad quality never drops the reading", () => {
    expect(parseLine('{"k":"spo2","v":97,"q":7}')).toEqual({ kind: "spo2", value: 97, label: null, unit: "%", quality: null });
  });
});
