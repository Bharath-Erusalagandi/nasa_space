"""Elevation contours for the topographic map, from the same Copernicus DEM GLO-90 tiles as relief.py.

Lines every 100 m (every 500 m marked as major), simplified and clipped to the province, written to
public/map/contours.json as GeoJSON with an `elev` property in metres. Run relief.py first; it downloads the tiles.
"""

import json
import subprocess

from common import MAP, RAW

INTERVAL = 100
MAJOR = 500
SIMPLIFY = 0.003
LIMIT = 900_000


def run(*args):
    subprocess.run([*map(str, args)], check=True, stdout=subprocess.DEVNULL)


def main():
    work = RAW / "dem"
    vrt, low, raw, clipped = work / "dem.vrt", work / "dem_low.tif", work / "contours_raw.geojson", work / "contours.geojson"
    province = MAP / "province.json"
    # about 450 m cells: enough for 100 m contours at province scale, and it smooths out speckle
    run("gdalwarp", "-overwrite", "-tr", "0.004", "0.004", "-r", "average", "-dstnodata", "-9999",
        "-cutline", province, "-crop_to_cutline", vrt, low)
    for path in (raw, clipped):
        path.unlink(missing_ok=True)
    run("gdal_contour", "-a", "elev", "-i", INTERVAL, "-snodata", "-9999", "-f", "GeoJSON", low, raw)
    run("ogr2ogr", "-f", "GeoJSON", "-simplify", SIMPLIFY, "-clipsrc", province, "-lco", "COORDINATE_PRECISION=4", clipped, raw)

    data = json.loads(clipped.read_text())
    features = []
    for f in data["features"]:
        geometry = f.get("geometry")
        if not geometry or geometry["type"] not in ("LineString", "MultiLineString"):
            continue
        elev = int(round(f["properties"]["elev"]))
        features.append({"type": "Feature", "properties": {"elev": elev, "major": elev % MAJOR == 0}, "geometry": geometry})
    out = MAP / "contours.json"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    size = out.stat().st_size
    elevs = sorted({f["properties"]["elev"] for f in features})
    print(f"contours: {len(features)} lines, {elevs[0]} to {elevs[-1]} m, {size} bytes")
    if size > LIMIT:
        raise SystemExit(f"contours.json is {size} bytes, over {LIMIT}; raise SIMPLIFY or INTERVAL")


if __name__ == "__main__":
    main()
