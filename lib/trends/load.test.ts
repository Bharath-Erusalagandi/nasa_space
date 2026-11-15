import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { clearCache, isListed, loadCell, loadIndex, loadMap, loadPodSite, loadReplay, loadValidation } from "./load";

const files: Record<string, unknown> = {
  "/trends/index.json": { cells: [], places: [] },
  "/trends/cells/-14.000_31.875.json": { cell: { id: "-14.000_31.875" } },
  "/map/frame.json": { west: 29.7, south: -15.2, east: 33.8, north: -11.3 },
};

let calls: string[] = [];

beforeEach(() => {
  calls = [];
  clearCache();
  vi.stubGlobal("fetch", async (path: string) => {
    calls.push(path);
    if (path === "/pod/replay.json") throw new TypeError("network down");
    const body = files[path];
    return body === undefined
      ? new Response("not found", { status: 404 })
      : new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  });
});

afterEach(() => void vi.unstubAllGlobals());

describe("load", () => {
  test("fetches each file once and caches it", async () => {
    const [a, b] = await Promise.all([loadIndex(), loadIndex()]);
    expect(a).toBe(b);
    await loadIndex();
    expect(calls).toEqual(["/trends/index.json"]);
  });

  test("cells and map files come from their folders", async () => {
    expect((await loadCell("-14.000_31.875")).cell.id).toBe("-14.000_31.875");
    expect((await loadMap("frame")).west).toBe(29.7);
  });

  test("a missing required file throws and is retried next time", async () => {
    await expect(loadCell("nope")).rejects.toThrow("404");
    await expect(loadCell("nope")).rejects.toThrow("404");
    expect(calls.filter((c) => c.includes("nope"))).toHaveLength(2);
  });

  test("missing optional files resolve to undefined", async () => {
    await expect(loadValidation()).resolves.toBeUndefined();
    await expect(loadPodSite()).resolves.toBeUndefined();
    await expect(loadReplay()).resolves.toBeUndefined();
  });

  test("an empty or malformed results file means nothing is tested", async () => {
    files["/validation/results.json"] = {};
    await expect(loadValidation()).resolves.toEqual({});
    clearCache();
    files["/validation/results.json"] = { heart_rate: { n: 0, loa_low: -1, loa_high: 1 }, spo2: "x", mosquito: { n: 3, recall: {} } };
    await expect(loadValidation()).resolves.toEqual({ mosquito: { n: 3, recall: {} } });
    clearCache();
    files["/validation/results.json"] = [1, 2];
    await expect(loadValidation()).resolves.toEqual({});
    delete files["/validation/results.json"];
  });

  test("the build's file list decides which optional files are asked for", () => {
    expect(isListed("/validation/results.json", "trends/pod_site.json")).toBe(false);
    expect(isListed("/trends/pod_site.json", "trends/pod_site.json pod/replay.json")).toBe(true);
    expect(isListed("/pod/replay.json", "")).toBe(false);
    expect(isListed("/pod/replay.json", null)).toBe(true);
  });

  test("evidence keeps only titled results with web links", async () => {
    const { safeItems } = await import("./load");
    expect(
      safeItems([
        { title: "A paper", link: "https://example.org/a", source: "Journal, 2019", year: 2019 },
        { title: "Script", link: "javascript:alert(1)" },
        { title: "", link: "https://example.org/untitled" },
        { link: "https://example.org/no-title" },
        "not an object",
      ]),
    ).toEqual([{ title: "A paper", link: "https://example.org/a", source: "Journal, 2019", year: 2019 }]);
    expect(safeItems(undefined)).toEqual([]);
  });
});
