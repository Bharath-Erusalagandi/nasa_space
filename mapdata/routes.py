import json
import shutil
import subprocess
import time
import urllib.request

from shapely.geometry import LineString

from common import MAP, PLACES, RAW, r4, reproject, to_lonlat, to_utm

IMAGE = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
CONTAINER = "mapdata-osrm"
PORT = 5055
HUB = "chipata"
TOLERANCE_M = 100
LIMIT = 900_000


def docker(*args, **kw):
    return subprocess.run(["sudo", "docker", *args], check=True, **kw)


def prepare(work):
    work.mkdir(exist_ok=True)
    pbf = work / "routing.osm.pbf"
    shutil.copy(RAW / "routing.osm.pbf", pbf)
    vol = ["-v", f"{work}:/data", IMAGE]
    docker("run", "--rm", "-t", *vol, "osrm-extract", "-p", "/opt/car.lua", "/data/routing.osm.pbf",
           stdout=subprocess.DEVNULL)
    docker("run", "--rm", "-t", *vol, "osrm-partition", "/data/routing.osrm", stdout=subprocess.DEVNULL)
    docker("run", "--rm", "-t", *vol, "osrm-customize", "/data/routing.osrm", stdout=subprocess.DEVNULL)


def serve(work):
    subprocess.run(["sudo", "docker", "rm", "-f", CONTAINER], capture_output=True)
    docker("run", "-d", "--name", CONTAINER, "-p", f"127.0.0.1:{PORT}:5000", "-v", f"{work}:/data", IMAGE,
           "osrm-routed", "--algorithm", "mld", "/data/routing.osrm", stdout=subprocess.DEVNULL)
    for _ in range(60):
        try:
            route((32.65, -13.63), (32.65, -13.63))
            return
        except OSError:
            time.sleep(1)
    raise SystemExit("osrm did not start")


def route(a, b):
    url = (f"http://127.0.0.1:{PORT}/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}"
           "?overview=full&geometries=geojson")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    if data["code"] != "Ok":
        raise SystemExit(f"osrm {data['code']} for {a} -> {b}")
    return data["routes"][0], data["waypoints"][1]["distance"]


def simplify(coords, fwd, back):
    if len(coords) < 2:
        return r4(coords)
    line = reproject(LineString(coords), fwd).simplify(TOLERANCE_M)
    return r4([list(c) for c in reproject(line, back).coords])


def main():
    places = json.loads(PLACES.read_text())
    hub = next(p for p in places if p["id"] == HUB)
    work = RAW / "osrm"
    prepare(work)
    fwd, back = to_utm(), to_lonlat()
    routes = {}
    try:
        serve(work)
        for p in places:
            if p["kind"] not in ("town", "facility"):
                continue
            r, snap = route((hub["lon"], hub["lat"]), (p["lon"], p["lat"]))
            routes[p["id"]] = {"km": round(r["distance"] / 1000, 1), "minutes": round(r["duration"] / 60),
                               "snap_km": round(snap / 1000, 1),
                               "line": simplify(r["geometry"]["coordinates"], fwd, back)}
    finally:
        subprocess.run(["sudo", "docker", "rm", "-f", CONTAINER], capture_output=True)
    out = {"hub": {k: hub[k] for k in ("id", "name", "lat", "lon")}, "routes": routes}
    path = MAP / "routes.json"
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    size = path.stat().st_size
    km = sorted(r["km"] for r in routes.values())
    far = sum(r["snap_km"] > 2 for r in routes.values())
    print(f"routes {len(routes)}, {size} bytes, km min {km[0]} median {km[len(km) // 2]} max {km[-1]}, "
          f"{far} places more than 2 km from the nearest routable road")
    if size > LIMIT:
        raise SystemExit(f"routes.json is {size} bytes, over {LIMIT}")


if __name__ == "__main__":
    main()
