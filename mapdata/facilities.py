from collections import Counter

import openpyxl
from shapely.geometry import Point

from common import MAP, RAW, feature, fetch, get_json, province, read_geojson, record_source, reproject, to_utm, write_geojson

FIGSHARE = "https://api.figshare.com/v2/articles"
PAPER_DOI = "10.1038/s41597-019-0142-2"
COUNTRY, ADMIN1 = "Zambia", "Eastern"
MAX_OUTSIDE_M = 5000


def download():
    hits = get_json(f"{FIGSHARE}/search", {"resource_doi": PAPER_DOI})
    if len(hits) != 1:
        raise SystemExit(f"expected one figshare article for {PAPER_DOI}, found {len(hits)}")
    meta = get_json(f"{FIGSHARE}/{hits[0]['id']}")
    xlsx = [f for f in meta["files"] if f["name"].endswith(".xlsx")]
    if len(xlsx) != 1:
        raise SystemExit(f"expected one xlsx in figshare article, found {[f['name'] for f in meta['files']]}")
    path = fetch(xlsx[0]["download_url"], RAW / "ssa_mfl.xlsx")
    record_source(f"{meta['title']} (Maina et al. 2019, Scientific Data, doi:{PAPER_DOI})",
                  f"{meta['license']['name']} ({meta['license']['url']})",
                  f"https://doi.org/{meta['doi']}", "health facility names, types and locations")
    return path


def rows(path):
    ws = openpyxl.load_workbook(path, read_only=True)["SSA MFL"]
    it = ws.iter_rows(values_only=True)
    head = next(it)
    for r in it:
        yield dict(zip(head, r))


def main():
    path = download()
    prov = province()
    prov_m = reproject(prov, to_utm())
    districts = [(reproject(g, to_utm()), p["name"]) for g, p in read_geojson(MAP / "districts.json")]
    project = to_utm()

    kept, dropped = [], Counter()
    for r in rows(path):
        if r["Country"] != COUNTRY or (r["Admin1"] or "").strip() != ADMIN1:
            continue
        lat, lon = r["Lat"], r["Long"]
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            dropped["no coordinates"] += 1
            continue
        pt = Point(project(lon, lat))
        if prov_m.distance(pt) > MAX_OUTSIDE_M:
            dropped["more than 5 km outside the province"] += 1
            continue
        district = min(districts, key=lambda d: d[0].distance(pt))[1]
        kept.append(feature(Point(lon, lat), {
            "name": " ".join(str(r["Facility name"]).split()),
            "type": r["Facility type"],
            "district": district,
        }))
    write_geojson("facilities.json", kept)
    print(f"facilities kept {len(kept)}, dropped {dict(dropped)}")
    print(f"types {dict(Counter(f['properties']['type'] for f in kept))}")


if __name__ == "__main__":
    main()
