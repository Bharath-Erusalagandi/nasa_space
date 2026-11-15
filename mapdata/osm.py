import json
import subprocess
from collections import defaultdict

from shapely.geometry import MultiLineString, box, shape
from shapely.ops import linemerge

from common import MAP, RAW, feature, fetch, frame, licence_on_page, record_source, reproject, to_lonlat, to_utm, write_geojson

PBF_URL = "https://download.geofabrik.de/africa/zambia-latest.osm.pbf"
PBF_PAGE = "https://download.geofabrik.de/africa/zambia.html"
ROUTING_PAD = 0.75
ROAD_CLASSES = ["trunk", "primary", "secondary", "tertiary"]
LIMITS = {"roads.json": 500_000, "rivers.json": 150_000}


def osmium(*args):
    subprocess.run(["osmium", *map(str, args), "--overwrite", "--no-progress"], check=True)


def export(src, filters, name, geometry):
    filtered = RAW / f"{name}.osm.pbf"
    seq = RAW / f"{name}.geojsonseq"
    osmium("tags-filter", src, *filters, "-o", filtered)
    osmium("export", filtered, "-f", "geojsonseq", f"--geometry-types={geometry}", "-o", seq)
    for line in seq.read_text().splitlines():
        line = line.strip("\x1e \t")
        if not line:
            continue
        f = json.loads(line)
        yield shape(f["geometry"]), f["properties"]


def extracts():
    pbf = fetch(PBF_URL, RAW / "zambia-latest.osm.pbf")
    record_source("OpenStreetMap Zambia extract (Geofabrik)",
                  licence_on_page(PBF_PAGE, "ODbL 1.0", "Open Database License 1.0 (ODbL), (c) OpenStreetMap contributors"),
                  PBF_URL, "roads, rivers, towns and road routing (OSRM)")
    fr = frame()
    clip = RAW / "frame.osm.pbf"
    osmium("extract", "-b", f"{fr['west']},{fr['south']},{fr['east']},{fr['north']}", pbf, "-o", clip)
    route = RAW / "routing.osm.pbf"
    osmium("extract", "-b", f"{fr['west'] - ROUTING_PAD},{fr['south'] - ROUTING_PAD},"
           f"{fr['east'] + ROUTING_PAD},{fr['north'] + ROUTING_PAD}", pbf, "-o", route)
    return clip


def merged_lines(items, frame_box, key):
    groups = defaultdict(list)
    for geom, props in items:
        part = geom.intersection(frame_box)
        if not part.is_empty:
            groups[key(props)].append(part)
    out = {}
    for k, parts in groups.items():
        lines = []
        for p in parts:
            lines.extend(getattr(p, "geoms", [p]))
        out[k] = linemerge(MultiLineString([l for l in lines if l.geom_type == "LineString"]))
    return out


def write_simplified(name, groups, props_of, start_m):
    fwd, back = to_utm(), to_lonlat()
    metric = {k: reproject(g, fwd) for k, g in groups.items()}
    tol = start_m
    while True:
        feats = [feature(reproject(g.simplify(tol), back), props_of(k)) for k, g in sorted(metric.items(), key=str)]
        path = write_geojson(name, feats)
        if path.stat().st_size <= LIMITS[name]:
            print(f"{name}: {len(feats)} features, tolerance {tol} m, {path.stat().st_size} bytes")
            return
        tol = round(tol * 1.25)


def main():
    clip = extracts()
    fr = frame()
    frame_box = box(fr["west"], fr["south"], fr["east"], fr["north"])

    roads = export(clip, [f"w/highway={','.join(ROAD_CLASSES)}"], "roads", "linestring")
    road_groups = merged_lines(roads, frame_box, lambda p: (p["highway"], p.get("name") or p.get("ref") or ""))
    write_simplified("roads.json", road_groups, lambda k: {"class": k[0], "name": k[1] or None}, 30)

    rivers = [(g, p) for g, p in export(clip, ["w/waterway=river"], "rivers", "linestring") if p.get("name")]
    river_groups = merged_lines(rivers, frame_box, lambda p: p["name"])
    write_simplified("rivers.json", river_groups, lambda k: {"name": k}, 50)

    towns = []
    for geom, p in export(clip, ["n/place=town,city"], "towns", "point"):
        if p.get("name") and frame_box.contains(geom):
            pop = p.get("population", "").replace(",", "")
            towns.append(feature(geom, {"name": p["name"], "place": p["place"],
                                        "population": int(pop) if pop.isdigit() else None}))
    write_geojson("towns.json", sorted(towns, key=lambda f: f["properties"]["name"]))
    print(f"towns.json: {len(towns)} features")


if __name__ == "__main__":
    main()
