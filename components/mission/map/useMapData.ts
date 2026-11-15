"use client";

import { useEffect, useState } from "react";
import { loadMap } from "@/lib/trends/load";
import type { FeatureCollection, Frame, MapSource } from "@/lib/trends/types";

export type Relief = Frame & { width: number; height: number };

export type TownProps = { name: string; place?: string };
export type CountryProps = { kind?: string; name?: string };

export type MapData = {
  frame: Frame;
  province: FeatureCollection;
  districts: FeatureCollection;
  rivers: FeatureCollection;
  roads: FeatureCollection<{ class?: string }>;
  context: FeatureCollection<CountryProps>;
  towns: FeatureCollection<TownProps>;
  sources: MapSource[];
  relief: Relief | null;
  contours: FeatureCollection<ContourProps> | null;
};

export type ContourProps = { elev: number; major: boolean };

async function loadRelief(): Promise<Relief | null> {
  try {
    const response = await fetch("/map/relief.json");
    return response.ok ? ((await response.json()) as Relief) : null;
  } catch {
    return null;
  }
}

async function loadContours(): Promise<FeatureCollection<ContourProps> | null> {
  try {
    const response = await fetch("/map/contours.json");
    return response.ok ? ((await response.json()) as FeatureCollection<ContourProps>) : null;
  } catch {
    return null;
  }
}

async function loadAll(): Promise<MapData> {
  const [frame, province, districts, rivers, roads, context, towns, sources, relief, contours] = await Promise.all([
    loadMap("frame"),
    loadMap("province"),
    loadMap("districts"),
    loadMap("rivers"),
    loadMap("roads"),
    loadMap("context"),
    loadMap("towns"),
    loadMap("sources").catch(() => [] as MapSource[]),
    loadRelief(),
    loadContours(),
  ]);
  return {
    frame,
    province,
    districts,
    rivers,
    roads: roads as MapData["roads"],
    context: context as MapData["context"],
    towns: towns as MapData["towns"],
    sources,
    relief,
    contours,
  };
}

// both maps read the same files; they are fetched and parsed once
let shared: Promise<MapData> | null = null;

export function useMapData() {
  const [data, setData] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    shared ??= loadAll().catch((e: unknown) => {
      shared = null;
      throw e;
    });
    shared.then(
      (d) => live && setData(d),
      (e: unknown) => live && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
    };
  }, []);
  return { data, error };
}
