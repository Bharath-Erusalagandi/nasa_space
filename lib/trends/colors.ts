import { CLASSES, type Ramp } from "./cellLayer";

const PREFIX: Record<Ramp, string> = { temperature: "temp", rainfall: "rain" };

export const NO_DATA = "var(--color-data-none)";

// class 0 is the low end of the slope; reversed flips which pole it takes
export function dataColor(ramp: Ramp, cls: number | null, reversed = false): string {
  if (cls === null || !Number.isInteger(cls) || cls < 0 || cls >= CLASSES) return NO_DATA;
  const step = reversed ? CLASSES - 1 - cls : cls;
  return `var(--color-data-${PREFIX[ramp]}-${step})`;
}

export const rampColors = (ramp: Ramp, reversed = false) =>
  Array.from({ length: CLASSES }, (_, cls) => dataColor(ramp, cls, reversed));
