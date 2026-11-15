import type { PodEvent } from "./parseLine";

export async function replay(
  events: (PodEvent & { t: number })[],
  emit: (e: PodEvent) => void,
  speed: number,
  sleep: (ms: number) => Promise<void>,
): Promise<void> {
  let last: number | null = null;
  for (const { t, ...event } of events) {
    if (last !== null) await sleep(Math.max(0, t - last) / speed);
    last = t;
    emit(event);
  }
}
