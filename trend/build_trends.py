import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trend_detective import (  # noqa: E402
    PARAMETERS, REQUIRED,
    INDICATORS, MIN_SEASONS, SOURCE, analyse, default_end, fetch_power, parse_power, trend,
)

START = date(1981, 1, 1)
LAT_STEP = 0.5
LON_STEP = 0.625
SUMMARY_NUMBERS = ("n", "slope_per_decade", "ci_low_per_decade", "ci_high_per_decade", "mk_p")


def power_cell(lat, lon):
    cell_lat = round(lat / LAT_STEP) * LAT_STEP
    cell_lon = round((lon + 180) / LON_STEP) * LON_STEP - 180
    return round(cell_lat, 4), round(cell_lon, 4)


def cell_id(cell):
    return f"{cell[0]:.3f}_{cell[1]:.3f}"


def cell_bounds(cell):
    lat, lon = cell
    return {
        "south": lat - LAT_STEP / 2,
        "north": lat + LAT_STEP / 2,
        "west": lon - LON_STEP / 2,
        "east": lon + LON_STEP / 2,
    }


def window_trends(series, sizes=(10, 20, 30)):
    out = {}
    for size in sizes:
        rows = series[-size:]
        values = [row["value"] for row in rows]
        enough = len(rows) == size and sum(v is not None for v in values) >= MIN_SEASONS
        out[str(size)] = trend([row["season"] for row in rows], values) if enough else None
    return out


def summary(result):
    if result is None:
        return {**dict.fromkeys(SUMMARY_NUMBERS), "q": None, "significant": False, "significant_fdr": False,
                "direction": None, "autocorrelation_warning": False}
    return {
        **{key: result[key] for key in SUMMARY_NUMBERS},
        "q": None,
        "significant": bool(result["mk_p"] < 0.05),
        "significant_fdr": False,
        "direction": result["direction"],
        "autocorrelation_warning": result["autocorrelation_warning"],
    }


def add_q_values(cells):
    keys = {key for cell in cells for key in cell.get("indicators", {})}
    for key in keys:
        found = [cell["indicators"][key] for cell in cells
                 if cell.get("indicators", {}).get(key, {}).get("mk_p") is not None]
        if not found:
            continue
        qs = stats.false_discovery_control([s["mk_p"] for s in found], method="bh")
        for s, q in zip(found, qs):
            s["q"] = float(q)
            s["significant_fdr"] = bool(q < 0.05)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False))
    os.replace(tmp, path)


def payload_problem(payload):
    errors = [m for m in payload.get("messages") or [] if "error" in str(m).lower()] + list(payload.get("errors") or [])
    if errors:
        return f"error in response: {str(errors[0])[:120]}"
    params = (payload.get("properties") or {}).get("parameter")
    if not isinstance(params, dict) or not params:
        return f"no data in response: {str(payload.get('messages') or payload)[:120]}"
    missing = [name for name in REQUIRED if not params.get(name)]
    return f"response lacks {' and '.join(missing)}" if missing else None


def read_cache(path, need=REQUIRED):
    # a cached file from before a variable was added lacks it, and is downloaded again
    try:
        payload = json.loads(path.read_text())
        if payload_problem(payload) is not None:
            return None
        return payload if all(payload["properties"]["parameter"].get(name) for name in need) else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def load_cell(cell, cache_dir, fetch, pause, end, need=REQUIRED):
    path = cache_dir / f"{cell_id(cell)}.json"
    payload = read_cache(path, need)
    if payload is not None:
        return payload, "cached"
    try:
        payload = fetch(cell[0], cell[1], START, end)
    finally:
        if pause > 0:
            time.sleep(pause)
    problem = payload_problem(payload)
    if problem:
        raise ValueError(problem)
    write_json(path, payload)
    return payload, "downloaded"


def short(error):
    return f"{type(error).__name__}: {error}"[:200]


def build(places, cache_dir, out_dir, fetch=fetch_power, pause=1.0, today=None):
    today = today or date.today()
    cache_dir, out_dir = Path(cache_dir), Path(out_dir)
    cells = {}
    rows = []
    for place in places:
        cell = power_cell(place["lat"], place["lon"])
        cells[cell_id(cell)] = cell
        rows.append({**place, "cell": cell_id(cell)})

    end = default_end(today)
    entries, counts = [], {"downloaded": 0, "cached": 0, "failed": 0}
    source = period = data_end = None
    for cid in sorted(cells):
        cell = cells[cid]
        head = {"id": cid, "lat": cell[0], "lon": cell[1], "bounds": cell_bounds(cell)}
        try:
            payload, how = load_cell(cell, cache_dir, fetch, pause, end, need=PARAMETERS)
            result = analyse(payload, cid, cell[0], cell[1])
            for indicator in result["indicators"].values():
                indicator["windows"] = window_trends(indicator["series"])
            result["cell"] = head
            write_json(out_dir / "cells" / f"{cid}.json", result)
        except Exception as error:
            (out_dir / "cells" / f"{cid}.json").unlink(missing_ok=True)
            entries.append({**head, "error": short(error)})
            counts["failed"] += 1
            print(f"failed {cid}: {short(error)}", flush=True)
            continue
        counts[how] += 1
        print(f"{how} {cid}", flush=True)
        last = max((day for series in parse_power(payload).values() for day in series), default=None)
        if last and (data_end is None or last > data_end):
            data_end = last
        source = source or result["source"]
        period = period or result["period"]
        entries.append({**head, "indicators": {k: summary(v["trend"]) for k, v in result["indicators"].items()}})

    add_q_values(entries)
    index = {"generated": today.isoformat(), "data_end": data_end and data_end.isoformat(), "source": source,
             "period": period, "cells": entries, "places": rows}
    write_json(out_dir / "index.json", index)
    print(f"{len(entries)} cells: {counts['downloaded']} downloaded, {counts['cached']} cached, "
          f"{counts['failed']} failed", flush=True)
    return index


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build per-cell trend files from NASA POWER.")
    parser.add_argument("--places", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(__file__).resolve().parent / "cache")
    parser.add_argument("--pause", type=float, default=1.0)
    args = parser.parse_args(argv)
    places = json.loads(args.places.read_text())
    build(places, args.cache, args.out, pause=args.pause)


if __name__ == "__main__":
    main()
