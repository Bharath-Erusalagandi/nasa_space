import json
import subprocess

from shapely.geometry import box, shape
from shapely.ops import unary_union

from common import MAP, RAW, feature, fetch, get_json, licence_on_page, record_source, write_geojson

API = "https://www.geoboundaries.org/api/current/gbOpen/ZMB/{}/"
NE = "https://naciscdn.org/naturalearth/10m/cultural/{}.zip"
NE_TERMS = "https://www.naturalearthdata.com/about/terms-of-use/"
PROVINCE = "Eastern"
PAD = 0.25
TOL = 0.001


def geoboundaries(level, used_for):
    meta = get_json(API.format(level))
    path = fetch(meta["gjDownloadURL"], RAW / f"geoBoundaries-ZMB-{level}.geojson")
    record_source(f"geoBoundaries Zambia {level} ({meta['boundarySource']})",
                  meta["boundaryLicense"], meta["gjDownloadURL"], used_for)
    return [(shape(f["geometry"]), f["properties"]) for f in json.loads(path.read_text())["features"]]


def natural_earth(layer, bbox):
    zipped = fetch(NE.format(layer), RAW / f"{layer}.zip")
    out = RAW / f"{layer}_frame.geojson"
    out.unlink(missing_ok=True)
    subprocess.run(["ogr2ogr", "-f", "GeoJSON", str(out), f"/vsizip/{zipped}",
                    "-clipsrc", *map(str, bbox)], check=True)
    return [(shape(f["geometry"]), f["properties"]) for f in json.loads(out.read_text())["features"]
            if f["geometry"]]


def main():
    adm1 = geoboundaries("ADM1", "province outline")
    prov = unary_union([g for g, p in adm1 if p["shapeName"] == PROVINCE])
    write_geojson("province.json", [feature(prov.simplify(TOL), {"name": f"{PROVINCE} Province"})])

    adm2 = geoboundaries("ADM2", "district outlines and facility districts")
    districts = [feature(g.simplify(TOL), {"name": p["shapeName"]}) for g, p in adm2
                 if prov.contains(g.representative_point())]
    write_geojson("districts.json", sorted(districts, key=lambda f: f["properties"]["name"]))

    w, s, e, n = prov.bounds
    fr = {"west": round(w - PAD, 4), "south": round(s - PAD, 4),
          "east": round(e + PAD, 4), "north": round(n + PAD, 4)}
    (MAP / "frame.json").write_text(json.dumps(fr) + "\n")
    bbox = (fr["west"], fr["south"], fr["east"], fr["north"])

    licence = licence_on_page(NE_TERMS, "are in the public domain", "Public domain (Natural Earth terms of use)")
    borders = natural_earth("ne_10m_admin_0_boundary_lines_land", bbox)
    record_source("Natural Earth 1:10m admin 0 boundary lines", licence,
                  NE.format("ne_10m_admin_0_boundary_lines_land"), "international borders")
    countries = natural_earth("ne_10m_admin_0_countries", bbox)
    record_source("Natural Earth 1:10m admin 0 countries", licence,
                  NE.format("ne_10m_admin_0_countries"), "country names and label points")

    frame_box = box(*bbox)
    feats = [feature(g, {"kind": "border"}) for g, _ in borders if not g.is_empty]
    for g, p in countries:
        part = g.intersection(frame_box)
        if part.is_empty:
            continue
        feats.append(feature(part.representative_point(),
                             {"kind": "country", "name": p["NAME"], "area_share": round(part.area / frame_box.area, 3)}))
    write_geojson("context.json", feats)
    print(f"province bounds {prov.bounds}, districts {len(districts)}, frame {fr}")
    print(f"borders {sum(f['properties']['kind'] == 'border' for f in feats)}, countries "
          f"{[f['properties']['name'] for f in feats if f['properties']['kind'] == 'country']}")


if __name__ == "__main__":
    main()
