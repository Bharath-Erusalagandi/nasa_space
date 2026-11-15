import argparse
import sys
from calendar import isleap
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_trends import cell_id, load_cell, power_cell, write_json  # noqa: E402
from trend_detective import default_end, fetch_power, parse_power  # noqa: E402

SOURCE = "NASA POWER daily point API (MERRA-2 reanalysis): T2M (daily mean air temperature at 2 m, deg C)"


def calendar_keys():
    first = date(2000, 1, 1)
    return [(first + timedelta(days=i)).strftime("%m-%d") for i in range(366)]


def normals_by_day(temp, half_window=7):
    values = {key: [] for key in calendar_keys()}
    for day, value in temp.items():
        for offset in range(-half_window, half_window + 1):
            values[(day - timedelta(days=offset)).strftime("%m-%d")].append(value)
        # a common year has no 29 Feb, so measure from the point between 28 Feb and 1 Mar
        if not isleap(day.year) and abs((day - date(day.year, 3, 1)).days + 0.5) <= half_window:
            values["02-29"].append(value)
    out = {}
    for key, found in values.items():
        if not found:
            out[key] = {"mean": None, "p10": None, "p90": None, "n": 0}
            continue
        x = np.asarray(found, dtype=float)
        p10, p90 = np.percentile(x, [10, 90])
        out[key] = {"mean": float(x.mean()), "p10": float(p10), "p90": float(p90), "n": len(found)}
    return out


def rounded(normal):
    return {k: v if k == "n" or v is None else round(v, 2) for k, v in normal.items()}


def pod_site(temp, place, lat, lon, half_window=7):
    return {
        "place": place,
        "cell": cell_id(power_cell(lat, lon)),
        "lat": lat,
        "lon": lon,
        "source": SOURCE,
        "period": f"{min(temp).isoformat()} to {max(temp).isoformat()}",
        "half_window": half_window,
        "normals": {key: rounded(n) for key, n in normals_by_day(temp, half_window).items()},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Daily NASA POWER temperature normals for the pod site.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(__file__).resolve().parent / "cache" / "normals")
    parser.add_argument("--half-window", type=int, default=7)
    args = parser.parse_args(argv)
    cell = power_cell(args.lat, args.lon)
    payload, how = load_cell(cell, args.cache, fetch_power, 0, default_end(date.today()))
    temp = parse_power(payload)["T2M"]
    if not temp:
        sys.exit(f"no T2M values for cell {cell_id(cell)}")
    site = pod_site(temp, args.name or f"{args.lat}, {args.lon}", args.lat, args.lon, args.half_window)
    write_json(args.out, site)
    print(f"{how} {site['cell']}, {site['period']}, wrote {args.out}")


if __name__ == "__main__":
    main()
