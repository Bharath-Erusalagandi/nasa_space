import json
import re

from common import MAP, PLACES, nasa_cell, province
from places import province_cells

LIMITS = {
    "province.json": 1_000_000,
    "districts.json": 1_000_000,
    "context.json": 1_000_000,
    "facilities.json": 1_000_000,
    "towns.json": 1_000_000,
    "roads.json": 500_000,
    "rivers.json": 150_000,
    "routes.json": 900_000,
    "relief.webp": 450_000,
    "relief.json": 10_000,
    "contours.json": 900_000,
    "terrain.webp": 450_000,
    "terrain.json": 10_000,
    "contour_labels.json": 20_000,
    "elevations.json": 50_000,
    "frame.json": 10_000,
    "sources.json": 100_000,
}
DATASETS = ["geoBoundaries Zambia ADM1", "geoBoundaries Zambia ADM2", "Natural Earth 1:10m admin 0 boundary lines",
            "Natural Earth 1:10m admin 0 countries", "Public health facilities in sub Saharan Africa",
            "OpenStreetMap Zambia extract", "Copernicus DEM GLO-90"]
failures = []


def check(ok, message):
    print(("ok   " if ok else "FAIL ") + message)
    if not ok:
        failures.append(message)


def coords(c):
    if isinstance(c, (int, float)):
        yield c
    else:
        for x in c:
            yield from coords(x)


def main():
    for name, limit in LIMITS.items():
        path = MAP / name
        size = path.stat().st_size if path.exists() else None
        check(size is not None and size <= limit, f"{name} exists, {size} bytes <= {limit}")
    check(PLACES.exists() and PLACES.stat().st_size <= 1_000_000, "trend/places.json exists, under 1 MB")

    for name in LIMITS:
        if name.endswith(".json") and name not in ("relief.json", "frame.json", "sources.json", "routes.json", "terrain.json", "contour_labels.json", "elevations.json"):
            data = json.loads((MAP / name).read_text())
            bad = [v for f in data["features"] for v in coords(f["geometry"]["coordinates"]) if round(v, 4) != v]
            check(not bad, f"{name} coordinates rounded to 4 decimals")

    places = json.loads(PLACES.read_text())
    ids = [p["id"] for p in places]
    check(len(ids) == len(set(ids)), f"{len(ids)} place ids are unique")
    check(all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids), "place ids are lowercase slugs")
    check(all(p["kind"] in ("town", "facility", "cell") for p in places), "place kinds are town, facility or cell")

    fr = json.loads((MAP / "frame.json").read_text())
    outside = [p["id"] for p in places
               if not (fr["west"] <= p["lon"] <= fr["east"] and fr["south"] <= p["lat"] <= fr["north"])]
    check(not outside, f"every place lies inside the frame {outside[:5]}")

    routes = json.loads((MAP / "routes.json").read_text())
    need = [p["id"] for p in places if p["kind"] in ("town", "facility")]
    missing = [i for i in need if i not in routes["routes"]]
    check(not missing, f"{len(need)} towns and facilities each have a route {missing[:5]}")
    shaped = all({"km", "minutes", "line"} <= set(r) and r["line"] for r in routes["routes"].values())
    check(shaped and {"id", "name", "lat", "lon"} <= set(routes["hub"]), "routes.json has the contract shape")

    cells = province_cells(province())
    held = {nasa_cell(p["lat"], p["lon"]) for p in places}
    empty = [c for c in cells if c not in held]
    check(not empty, f"{len(cells)} NASA cells intersecting the province each hold a place {empty[:5]}")

    sources = json.loads((MAP / "sources.json").read_text())
    complete = all(all(s.get(k) for k in ("name", "licence", "url", "fetched", "used_for")) for s in sources)
    check(complete, f"{len(sources)} sources.json entries have name, licence, url, fetched, used_for")
    credited = all(set(s.get("credit") or {}) == {"group", "text"} for s in sources)
    check(credited, "sources.json entries each have a short credit")
    for d in DATASETS:
        check(any(s["name"].startswith(d) for s in sources), f"sources.json lists {d}")

    print(f"{len(failures)} failures")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
