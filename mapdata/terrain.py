"""The terrain map: elevation tint under the hillshade, contour labels, and the elevation of every place.

Reads the Copernicus DEM GLO-90 work files that relief.py leaves in mapdata/raw/dem, and writes
  public/map/terrain.webp          elevation colours times hillshade, transparent outside the province
  public/map/terrain.json          its bounds (as relief.json) and the colour table, which the legend draws
  public/map/contour_labels.json   one label per long 500 m contour
  public/map/elevations.json       metres above sea level at each place in trend/places.json
"""

import json
import math
import subprocess

import numpy as np
from PIL import Image

from common import MAP, RAW, ROOT

# metres, colour: low valley green to highland brown, the usual order of a hypsometric tint
RAMP = [(300, "#3f7a52"), (600, "#7fa06a"), (900, "#c2bf86"), (1100, "#d8c391"), (1300, "#bf956b"), (1500, "#99705a"), (1800, "#7a6157")]
LABEL_GAP_DEG = 0.45


def run(*args, capture=False):
    result = subprocess.run([*map(str, args)], check=True, capture_output=True, text=True)
    return result.stdout if capture else None


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def tint():
    work = RAW / "dem"
    merc, shade = work / "dem_3857.tif", work / "shade.tif"
    table = work / "ramp.txt"
    table.write_text("nv 0 0 0 0\n" + "".join(f"{e} {' '.join(map(str, hex_rgb(c)))} 255\n" for e, c in RAMP))
    colour, cut = work / "tint.tif", work / "tint_cut.tif"
    run("gdaldem", "color-relief", "-alpha", merc, table, colour)
    run("gdalwarp", "-overwrite", "-cutline", MAP / "province.json", "-dstalpha", colour, cut)
    png_tint, png_shade = work / "tint.png", work / "shade.png"
    run("gdal_translate", "-of", "PNG", "-b", 1, "-b", 2, "-b", 3, "-b", 4, cut, png_tint)
    run("gdal_translate", "-of", "PNG", "-ot", "Byte", "-b", 1, shade, png_shade)
    rgba = np.array(Image.open(png_tint).convert("RGBA"), dtype=np.float32)
    light = np.array(Image.open(png_shade).convert("L"), dtype=np.float32) / 255.0
    # the hillshade's flat ground is about 0.73; scale so flat keeps its colour and slopes darken or lighten
    factor = np.clip(light / 0.73, 0.55, 1.25)[..., None]
    rgba[..., :3] = np.clip(rgba[..., :3] * factor, 0, 255)
    out = MAP / "terrain.webp"
    Image.fromarray(rgba.astype(np.uint8), "RGBA").save(out, "WEBP", quality=78, method=6)
    bounds = json.loads((MAP / "relief.json").read_text())
    (MAP / "terrain.json").write_text(json.dumps({**bounds, "ramp": [{"m": e, "colour": c} for e, c in RAMP]}) + "\n")
    print(f"terrain {rgba.shape[1]}x{rgba.shape[0]}, {out.stat().st_size} bytes")


def line_length(coords):
    return sum(math.dist(a, b) for a, b in zip(coords, coords[1:]))


def contour_labels():
    data = json.loads((MAP / "contours.json").read_text())
    candidates = []
    for f in data["features"]:
        if not f["properties"]["major"]:
            continue
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for part in parts:
            if len(part) > 4:
                candidates.append((line_length(part), f["properties"]["elev"], part[len(part) // 2]))
    candidates.sort(reverse=True)
    chosen = []
    for length, elev, (lon, lat) in candidates:
        if length < 0.3:
            break
        if all(math.dist((lon, lat), (c["lon"], c["lat"])) > LABEL_GAP_DEG for c in chosen):
            chosen.append({"elev": elev, "lon": lon, "lat": lat})
    (MAP / "contour_labels.json").write_text(json.dumps(chosen, separators=(",", ":")) + "\n")
    print(f"contour labels: {len(chosen)}")


def elevations():
    places = json.loads((ROOT / "trend" / "places.json").read_text())
    vrt = RAW / "dem" / "dem.vrt"
    points = "".join(f"{p['lon']} {p['lat']}\n" for p in places)
    out = subprocess.run(["gdallocationinfo", "-valonly", "-wgs84", str(vrt)], input=points, check=True, capture_output=True, text=True).stdout
    values = out.split()
    result = {p["id"]: round(float(v)) for p, v in zip(places, values) if v and float(v) > 0}
    (MAP / "elevations.json").write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(f"elevations for {len(result)} of {len(places)} places, {min(result.values())} to {max(result.values())} m")


if __name__ == "__main__":
    tint()
    contour_labels()
    elevations()
