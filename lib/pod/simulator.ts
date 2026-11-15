import { podStore } from "./store";

export const TICK_MS = 1000;

const MOSQUITO_LABELS = ["An. arabiensis", "An. funestus", "Culex quinquefasciatus", "Aedes aegypti"];

// mulberry32: small, seeded, the same sequence on every machine
export function seededRandom(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (x: number, digits: number) => Number(x.toFixed(digits));
const clamp = (x: number, low: number, high: number) => Math.min(high, Math.max(low, x));

export function createSimulation(seed = 1) {
  const random = seededRandom(seed);
  const between = (low: number, high: number) => low + (high - low) * random();
  let heart = 78;
  let temp = 24;
  let humidity = 45;

  // lines for second number `tick`, starting at 0
  return function tick(tick: number): string[] {
    heart = clamp(heart + between(-2, 2), 60, 110);
    const lines = [
      JSON.stringify({ k: "hr", v: Math.round(heart), q: round(between(0.8, 0.99), 2) }),
      JSON.stringify({ k: "spo2", v: Math.round(between(95, 99)), q: round(between(0.8, 0.99), 2) }),
    ];
    if (tick % 2 === 0) {
      temp = clamp(temp + between(-0.2, 0.2), 18, 32);
      humidity = clamp(humidity + between(-1, 1), 25, 80);
      lines.push(JSON.stringify({ k: "temp", v: round(temp, 1) }), JSON.stringify({ k: "rh", v: Math.round(humidity) }));
    }
    if (random() < 0.08) {
      const label = MOSQUITO_LABELS[Math.floor(random() * MOSQUITO_LABELS.length)];
      lines.push(JSON.stringify({ k: "mosq", label, conf: round(between(0.4, 0.95), 2) }));
    }
    const fault = random();
    if (fault < 0.04) lines.push('{"k":"hr","v":7');
    else if (fault < 0.08) lines.push(JSON.stringify({ k: "spo2", v: 104 }));
    return lines;
  };
}

export function startSimulator(
  emit: (line: string) => void = (line) => podStore.getState().ingestLine(line, "simulation"),
  seed = 1,
): () => void {
  const tick = createSimulation(seed);
  let n = 0;
  const run = () => tick(n++).forEach(emit);
  run();
  const id = setInterval(run, TICK_MS);
  return () => clearInterval(id);
}

export const simulationRequested = (search: string) => new URLSearchParams(search).get("sim") === "1";
