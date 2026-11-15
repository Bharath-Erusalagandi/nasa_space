import json
import math
import re

from shapely.geometry import box

from common import MAP, PLACES, cell_id, frame, nasa_cell, province, read_geojson

TOWNS = [
    ("katete", "Katete", -14.06, 32.04),
    ("chipata", "Chipata", -13.63, 32.65),
    ("mfuwe", "Mfuwe", -13.26, 31.93),
    ("lundazi", "Lundazi", -12.29, 33.18),
    ("petauke", "Petauke", -14.24, 31.33),
]
LAT_STEP, LON_STEP = 0.5, 0.625


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def unique(base, taken):
    sid, n = base, 2
    while sid in taken:
        sid, n = f"{base}-{n}", n + 1
    taken.add(sid)
    return sid


def cell_box(lat, lon):
    return box(lon - LON_STEP / 2, lat - LAT_STEP / 2, lon + LON_STEP / 2, lat + LAT_STEP / 2)


def province_cells(prov):
    w, s, e, n = prov.bounds
    cells = []
    for i in range(math.floor(s / LAT_STEP), math.ceil(n / LAT_STEP) + 1):
        for j in range(math.floor((w + 180) / LON_STEP), math.ceil((e + 180) / LON_STEP) + 1):
            lat, lon = i * LAT_STEP, j * LON_STEP - 180
            if cell_box(lat, lon).intersection(prov).area > 0:
                cells.append(nasa_cell(lat, lon))
    return cells


def main():
    prov = province()
    taken = set()
    places = [{"id": unique(i, taken), "name": n, "lat": lat, "lon": lon, "kind": "town"}
              for i, n, lat, lon in TOWNS]
    for geom, p in read_geojson(MAP / "facilities.json"):
        places.append({"id": unique(slug(p["name"]), taken), "name": p["name"],
                       "lat": round(geom.y, 4), "lon": round(geom.x, 4), "kind": "facility",
                       "type": p["type"], "district": p["district"]})

    occupied = {nasa_cell(p["lat"], p["lon"]) for p in places}
    fr = frame()
    cells = province_cells(prov)
    for lat, lon in cells:
        if (lat, lon) in occupied:
            continue
        cid = cell_id((lat, lon))
        if not (fr["west"] <= lon <= fr["east"] and fr["south"] <= lat <= fr["north"]):
            raise SystemExit(f"cell centre {cid} falls outside the map frame")
        places.append({"id": unique("cell-" + slug(cid.replace("-", "s")), taken),
                       "name": f"Grid cell {cid}", "lat": lat, "lon": lon, "kind": "cell"})

    PLACES.parent.mkdir(parents=True, exist_ok=True)
    PLACES.write_text(json.dumps(places, indent=1, ensure_ascii=False) + "\n")
    kinds = {k: sum(p["kind"] == k for p in places) for k in ("town", "facility", "cell")}
    print(f"places {len(places)} {kinds}, province cells {len(cells)}, "
          f"distinct cells over all places {len({nasa_cell(p['lat'], p['lon']) for p in places})}")


if __name__ == "__main__":
    main()
