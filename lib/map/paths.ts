import { geoArea, geoBounds, geoPath, type GeoProjection } from "d3-geo";
import type { Feature, FeatureCollection, Position } from "@/lib/trends/types";

export const ROAD_CLASSES = ["trunk", "primary", "secondary", "tertiary"] as const;
export type RoadClass = (typeof ROAD_CLASSES)[number];

type GeoObject = Parameters<ReturnType<typeof geoPath>>[0];

export type BaseLayers = {
  province: FeatureCollection;
  districts: FeatureCollection;
  rivers: FeatureCollection;
  roads: FeatureCollection<{ class?: string }>;
  context: FeatureCollection<{ kind?: string }>;
  contours?: FeatureCollection<{ major?: boolean }> | null;
};

export type BasePaths = {
  province: string;
  districts: string;
  borders: string;
  rivers: string;
  roads: Record<RoadClass, string>;
  contours: { minor: string; major: string };
};

type Rings = number[][][];

// d3 reads polygons on the sphere and wants clockwise outer rings; GeoJSON files often wind them the other way,
// which d3 then reads as the whole globe minus the shape
export function rewind(feature: Feature): Feature {
  const { type, coordinates } = feature.geometry;
  if (type !== "Polygon" && type !== "MultiPolygon") return feature;
  if (geoArea(feature as unknown as GeoObject) <= 2 * Math.PI) return feature;
  const flip = (rings: Rings) => rings.map((ring) => [...ring].reverse());
  const turned = type === "Polygon" ? flip(coordinates as Rings) : (coordinates as Rings[]).map(flip);
  return { ...feature, geometry: { type, coordinates: turned } };
}

function pathOf(projection: GeoProjection, features: Feature[]): string {
  const path = geoPath(projection).digits(1);
  return features.map((f) => path(rewind(f) as unknown as GeoObject) ?? "").join("");
}

export const roadClass = (value: unknown): RoadClass =>
  ROAD_CLASSES.includes(value as RoadClass) ? (value as RoadClass) : "tertiary";

export function basePaths(layers: BaseLayers, projection: GeoProjection): BasePaths {
  const roads = Object.fromEntries(ROAD_CLASSES.map((c) => [c, [] as Feature[]])) as Record<RoadClass, Feature[]>;
  for (const road of layers.roads.features) roads[roadClass(road.properties?.class)].push(road);
  return {
    province: pathOf(projection, layers.province.features),
    districts: pathOf(projection, layers.districts.features),
    borders: pathOf(projection, layers.context.features.filter((f) => f.properties?.kind === "border")),
    rivers: pathOf(projection, layers.rivers.features),
    roads: Object.fromEntries(ROAD_CLASSES.map((c) => [c, pathOf(projection, roads[c])])) as Record<RoadClass, string>,
    contours: {
      minor: pathOf(projection, (layers.contours?.features ?? []).filter((f) => !f.properties?.major)),
      major: pathOf(projection, (layers.contours?.features ?? []).filter((f) => f.properties?.major)),
    },
  };
}

// the box around the province outline
export function provinceFrame(province: FeatureCollection) {
  const [[west, south], [east, north]] = geoBounds({ type: "FeatureCollection", features: province.features.map(rewind) } as unknown as GeoObject);
  return { west, south, east, north };
}

export function linePath(projection: GeoProjection, line: Position[]): string {
  return pathOf(projection, [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: line } }]);
}
