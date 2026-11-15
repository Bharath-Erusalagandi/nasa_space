export const NOT_TESTED = "not yet tested";

function signed(x: number): string {
  const v = Number(x.toFixed(1)) || 0;
  return v > 0 ? `+${v}` : String(v);
}

export function errorLabel(result: { n: number; loa_low: number; loa_high: number } | undefined, unit: string): string {
  if (!result || result.n <= 0) return NOT_TESTED;
  const pairs = result.n === 1 ? "pair" : "pairs";
  return `tested on ${result.n} ${pairs}: 95% of readings within ${signed(result.loa_low)} to ${signed(result.loa_high)} ${unit} of the reference`;
}

export function recallLabel(result: { recall: Record<string, number>; n: number } | undefined, label: string): string {
  const recall = result && Object.hasOwn(result.recall, label) ? result.recall[label] : undefined;
  if (!result || result.n <= 0 || recall === undefined) return NOT_TESTED;
  return `recognised ${Math.round(recall * 100)}% of recorded ${label} clips (${result.n} clips tested)`;
}
