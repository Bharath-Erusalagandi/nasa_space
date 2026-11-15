import datetime
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "mapdata" / "raw"
MAP = ROOT / "public" / "map"
SOURCES = MAP / "sources.json"
PLACES = ROOT / "trend" / "places.json"
UTM = "EPSG:32736"


def fetch(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "mapdata-build"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    return dest


def get_json(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "mapdata-build",
                                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def page_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "mapdata-build"})
    with urllib.request.urlopen(req, timeout=120) as r:
        html = r.read().decode("utf-8", "replace")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def licence_on_page(url, phrase, licence):
    if phrase.lower() not in page_text(url).lower():
        raise SystemExit(f"licence phrase {phrase!r} not found at {url}")
    return licence


# short credits for the map's one-line attribution, by dataset name prefix
CREDITS = {
    "geoBoundaries": ("Boundaries", "geoBoundaries"),
    "Natural Earth": ("Boundaries", "Natural Earth"),
    "OpenStreetMap": ("Roads and rivers", "\u00a9 OpenStreetMap contributors"),
    "Copernicus DEM": ("Relief", "Copernicus DEM"),
}


def credit_for(name):
    if "Maina et al. 2019" in name:
        return {"group": "Facilities", "text": "Maina et al. 2019"}
    for prefix, (group, text) in CREDITS.items():
        if name.startswith(prefix):
            return {"group": group, "text": text}
    raise SystemExit(f"no short credit for source {name!r}")


def record_source(name, licence, url, used_for):
    MAP.mkdir(parents=True, exist_ok=True)
    rows = json.loads(SOURCES.read_text()) if SOURCES.exists() else []
    rows = [r for r in rows if r["name"] != name]
    rows.append({
        "name": name,
        "licence": licence,
        "url": url,
        "fetched": datetime.date.today().isoformat(),
        "used_for": used_for,
        "credit": credit_for(name),
    })
    write_sources(rows)


def write_sources(rows):
    SOURCES.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


# python common.py adds the credits to an existing sources.json without fetching anything
def add_credits():
    write_sources([{**r, "credit": credit_for(r["name"])} for r in json.loads(SOURCES.read_text())])


def r4(coords):
    if isinstance(coords, (int, float)):
        return round(coords, 4)
    return [r4(c) for c in coords]


def feature(geom, props):
    from shapely.geometry import mapping
    g = mapping(geom)
    return {"type": "Feature", "properties": props,
            "geometry": {"type": g["type"], "coordinates": r4(g["coordinates"])}}


def write_geojson(name, features):
    path = MAP / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features},
                               separators=(",", ":"), ensure_ascii=False))
    return path


def read_geojson(path):
    from shapely.geometry import shape
    data = json.loads(Path(path).read_text())
    return [(shape(f["geometry"]), f["properties"]) for f in data["features"]]


def frame():
    return json.loads((MAP / "frame.json").read_text())


def province():
    return read_geojson(MAP / "province.json")[0][0]


def to_utm():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform


def to_lonlat():
    from pyproj import Transformer
    return Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform


def reproject(geom, fn):
    import numpy as np
    import shapely
    return shapely.transform(geom, lambda xy: np.column_stack(fn(xy[:, 0], xy[:, 1])))


def nasa_cell(lat, lon):
    return round(lat / 0.5) * 0.5, round((lon + 180) / 0.625) * 0.625 - 180


def cell_id(cell):
    return f"{cell[0]:.3f}_{cell[1]:.3f}"


if __name__ == "__main__":
    add_credits()
