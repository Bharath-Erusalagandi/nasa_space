import json
import math
import subprocess
import urllib.error

from pyproj import Transformer

from common import MAP, RAW, fetch, frame, licence_on_page, record_source

BUCKET = "https://copernicus-dem-90m.s3.amazonaws.com"
README = f"{BUCKET}/readme.html"
LICENCE = ("Copernicus DEM GLO-90, free licence; produced using Copernicus WorldDEM-90 (c) DLR e.V. 2010-2014 "
           "and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; "
           "all rights reserved")
WIDTH = 1400
LIMIT = 450_000


def tile_name(lat, lon):
    ns = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00"
    ew = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00"
    return f"Copernicus_DSM_COG_30_{ns}_{ew}_DEM"


def tiles(fr):
    found = []
    for lat in range(math.floor(fr["south"]) - 1, math.ceil(fr["north"]) + 1):
        for lon in range(math.floor(fr["west"]) - 1, math.ceil(fr["east"]) + 1):
            name = tile_name(lat, lon)
            try:
                found.append(fetch(f"{BUCKET}/{name}/{name}.tif", RAW / "dem" / f"{name}.tif"))
            except urllib.error.HTTPError as e:
                if e.code not in (403, 404):
                    raise
    return found


def gdal(*args):
    subprocess.run([*map(str, args)], check=True, stdout=subprocess.DEVNULL)


def main():
    fr = frame()
    licence = licence_on_page(README, "GLO-90 are available on a free basis for the general public", LICENCE)
    dem = tiles(fr)
    record_source("Copernicus DEM GLO-90 (AWS Open Data, copernicus-dem-90m)", licence, BUCKET,
                  f"hillshade relief ({len(dem)} tiles)")
    work = RAW / "dem"
    vrt, merc, shade = work / "dem.vrt", work / "dem_3857.tif", work / "shade.tif"
    gdal("gdalbuildvrt", "-overwrite", vrt, *dem)
    gdal("gdalwarp", "-overwrite", "-t_srs", "EPSG:3857", "-te_srs", "EPSG:4326",
         "-te", fr["west"], fr["south"], fr["east"], fr["north"], "-ts", WIDTH, 0, "-r", "bilinear", vrt, merc)
    gdal("gdaldem", "hillshade", "-z", "3", "-multidirectional", "-compute_edges", merc, shade)
    out = MAP / "relief.webp"
    quality = 80
    while True:
        gdal("gdal_translate", "-of", "WEBP", "-co", f"QUALITY={quality}", "-b", 1, "-b", 1, "-b", 1,
             "-scale", 0, 255, 70, 235, shade, out)
        if out.stat().st_size <= LIMIT or quality <= 30:
            break
        quality -= 10
    (MAP / "relief.webp.aux.xml").unlink(missing_ok=True)

    info = json.loads(subprocess.run(["gdalinfo", "-json", merc], check=True, capture_output=True).stdout)
    to_ll = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True).transform
    west, north = to_ll(*info["cornerCoordinates"]["upperLeft"])
    east, south = to_ll(*info["cornerCoordinates"]["lowerRight"])
    w, h = info["size"]
    bounds = {"west": round(west, 6), "south": round(south, 6), "east": round(east, 6), "north": round(north, 6),
              "width": w, "height": h, "projection": "EPSG:3857"}
    (MAP / "relief.json").write_text(json.dumps(bounds) + "\n")
    print(f"relief {w}x{h}, {out.stat().st_size} bytes at quality {quality}, {len(dem)} tiles, bounds {bounds}")


if __name__ == "__main__":
    main()
