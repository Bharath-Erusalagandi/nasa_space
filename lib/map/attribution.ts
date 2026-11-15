import type { MapSource } from "@/lib/trends/types";

export type Credit = { group: string; text: string };
export type CreditedSource = MapSource & { credit?: Credit };

const ORDER = ["Trends", "Boundaries", "Roads and rivers", "Facilities", "Relief"];

// "NASA POWER daily point API (MERRA-2 reanalysis): ..." -> "NASA POWER (MERRA-2)"
export function climateCredit(source: string): string {
  const m = source.match(/^([A-Z][A-Z0-9]*(?: [A-Z][A-Z0-9]*)*)\b[^(:]*\(([^\s)]+)/);
  return m ? `${m[1]} (${m[2]})` : "NASA POWER";
}

const creditOf = (s: CreditedSource): Credit => s.credit ?? { group: "Sources", text: s.name.replace(/\s*\(.*\)\s*$/, "") };

export function attribution(sources: CreditedSource[], climate: string): string {
  const groups = new Map<string, Set<string>>([["Trends", new Set([climateCredit(climate)])]]);
  for (const { group, text } of sources.map(creditOf)) groups.set(group, (groups.get(group) ?? new Set()).add(text));
  const rank = (g: string) => (ORDER.includes(g) ? ORDER.indexOf(g) : ORDER.length);
  return [...groups]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([group, texts]) => `${group}: ${[...texts].join(", ")}.`)
    .join(" ");
}
