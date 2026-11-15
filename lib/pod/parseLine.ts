export type PodKind = "heart_rate" | "spo2" | "air_temp_c" | "humidity_pct" | "mosquito" | "distance_cm" | "light_pct";

export type PodEvent = {
  kind: PodKind;
  value: number | null;
  label: string | null;
  unit: string | null;
  quality: number | null;
};

type Reading = { kind: PodKind; unit: string; min: number; max: number };

const READINGS: Record<string, Reading> = {
  hr: { kind: "heart_rate", unit: "bpm", min: 30, max: 220 },
  spo2: { kind: "spo2", unit: "%", min: 70, max: 100 },
  temp: { kind: "air_temp_c", unit: "°C", min: -40, max: 60 },
  rh: { kind: "humidity_pct", unit: "%", min: 0, max: 100 },
  dist: { kind: "distance_cm", unit: "cm", min: 2, max: 400 },
  light: { kind: "light_pct", unit: "%", min: 0, max: 100 },
};

const isNumber = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);
const quality = (x: unknown) => (isNumber(x) && x >= 0 && x <= 1 ? x : null);

function parseObject(line: string): Record<string, unknown> | null {
  try {
    const data: unknown = JSON.parse(line);
    return data !== null && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

export function parseLine(line: string): PodEvent | null {
  const data = parseObject(line.trim());
  if (!data) return null;

  if (data.k === "mosq") {
    if (typeof data.label !== "string" || data.label.trim() === "") return null;
    return { kind: "mosquito", value: null, label: data.label, unit: null, quality: quality(data.conf) };
  }

  const reading = typeof data.k === "string" && Object.hasOwn(READINGS, data.k) ? READINGS[data.k] : undefined;
  if (!reading || !isNumber(data.v) || data.v < reading.min || data.v > reading.max) return null;
  return { kind: reading.kind, value: data.v, label: null, unit: reading.unit, quality: quality(data.q) };
}

// the car kit answers each command it ran with {"ack":"<command>"}
export function parseAck(line: string): string | null {
  const data = parseObject(line.trim());
  return data && typeof data.ack === "string" && data.ack !== "" ? data.ack : null;
}
