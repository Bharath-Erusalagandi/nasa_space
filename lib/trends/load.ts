import type { RecordedEvent } from "@/lib/pod/recorder";
import type { CellFile, Evidence, EvidenceItem, MapFiles, MapName, PodSite, TrendIndex, ValidationResults } from "./types";

const cache = new Map<string, Promise<unknown>>();

async function fetchJSON(path: string): Promise<unknown> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function cached<T>(path: string): Promise<T> {
  let pending = cache.get(path);
  if (!pending) {
    pending = fetchJSON(path);
    cache.set(path, pending);
    pending.catch(() => cache.delete(path));
  }
  return pending as Promise<T>;
}

// files the team adds later; the build lists the ones it found in a meta tag, so the page never asks for a missing one
export const OPTIONAL_FILES = ["trends/pod_site.json", "validation/results.json", "pod/replay.json", "evidence/index.json"] as const;
export const FILES_META = "orbit-files";

export function isListed(path: string, listed: string | null | undefined): boolean {
  if (listed == null) return true;
  return listed.split(" ").includes(path.replace(/^\//, ""));
}

function listedFiles(): string | null {
  if (typeof document === "undefined") return null;
  return document.querySelector<HTMLMetaElement>(`meta[name="${FILES_META}"]`)?.content ?? null;
}

async function optional<T>(path: string): Promise<T | undefined> {
  if (!isListed(path, listedFiles())) return undefined;
  try {
    return await cached<T>(path);
  } catch {
    return undefined;
  }
}

export const loadIndex = () => cached<TrendIndex>("/trends/index.json");
export const loadCell = (id: string) => cached<CellFile>(`/trends/cells/${encodeURIComponent(id)}.json`);
export const loadMap = <N extends MapName>(name: N) => cached<MapFiles[N]>(`/map/${name}.json`);

export const loadPodSite = () => optional<PodSite>("/trends/pod_site.json");
const isObject = (x: unknown): x is Record<string, unknown> => x !== null && typeof x === "object" && !Array.isArray(x);

// an entry counts only when it reports at least one tested pair or clip; anything else is not yet tested
export function testedOnly(data: unknown): ValidationResults {
  if (!isObject(data)) return {};
  const tested = Object.entries(data).filter(([, v]) => isObject(v) && typeof v.n === "number" && v.n > 0);
  return Object.fromEntries(tested) as ValidationResults;
}

export const loadValidation = async () => {
  const data = await optional<unknown>("/validation/results.json");
  return data === undefined ? undefined : testedOnly(data);
};
// only web links are kept, so a result can never carry a script or a local address into the page
export const safeItems = (items: unknown): EvidenceItem[] =>
  Array.isArray(items)
    ? items.filter((i): i is EvidenceItem => isObject(i) && typeof i.title === "string" && i.title !== "" && typeof i.link === "string" && /^https?:\/\//.test(i.link))
    : [];

export const loadEvidence = async (): Promise<Evidence | undefined> => {
  const data = await optional<unknown>("/evidence/index.json");
  if (!isObject(data) || !isObject(data.indicators)) return undefined;
  const indicators = Object.fromEntries(
    Object.entries(data.indicators)
      .filter(([, entry]) => isObject(entry))
      .map(([key, entry]) => {
        const e = entry as Record<string, unknown>;
        return [key, { query: String(e.query ?? ""), google_scholar: safeItems(e.google_scholar), google_news: safeItems(e.google_news) }];
      }),
  );
  return { generated: String(data.generated ?? ""), source: String(data.source ?? ""), region: String(data.region ?? ""), indicators };
};

export const loadReplay = () => optional<RecordedEvent[]>("/pod/replay.json");

export const clearCache = () => cache.clear();
