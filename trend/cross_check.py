# written with Claude (Anthropic), see docs/AI_USE.md
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_trends import START, short, write_json  # noqa: E402
from trend_detective import INDICATORS, MIN_SEASONS, default_end, seasonal_indicators, trend  # noqa: E402

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
NAME = "ECMWF ERA5 via Open-Meteo"


def parse_open_meteo(payload):
    daily = payload.get("daily") or {}
    days = [datetime.strptime(day, "%Y-%m-%d").date() for day in daily.get("time", [])]
    out = {}
    for name, field in (("PRECTOTCORR", "precipitation_sum"), ("T2M", "temperature_2m_mean")):
        out[name] = {day: float(v) for day, v in zip(days, daily.get(field, [])) if v is not None}
    return out


def fetch_open_meteo(lat, lon, start, end, timeout=120):
    query = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum,temperature_2m_mean",
        "timezone": "UTC",
        "models": "era5",
    })
    url = f"{ARCHIVE_URL}?{query}"
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 2:
                raise
            time.sleep(61)


def read_cache(path):
    try:
        payload = json.loads(path.read_text())
        return payload if isinstance(payload["daily"]["time"], list) else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_era5(cell, cache_dir, fetch, pause, end):
    path = cache_dir / f"{cell['id']}.json"
    payload = read_cache(path)
    if payload is not None:
        return payload, "cached"
    try:
        payload = fetch(cell["lat"], cell["lon"], START, end)
    finally:
        if pause > 0:
            time.sleep(pause)
    if not isinstance(payload.get("daily", {}).get("time"), list):
        raise ValueError(f"no daily data in response: {str(payload)[:120]}")
    write_json(path, payload)
    return payload, "downloaded"


def second_source(payload):
    data = parse_open_meteo(payload)
    series = seasonal_indicators(data["PRECTOTCORR"], data["T2M"])
    out = {}
    for key in INDICATORS:
        rows = series[key]
        values = [row["value"] for row in rows]
        enough = sum(v is not None for v in values) >= MIN_SEASONS
        out[key] = {"name": NAME, "trend": trend([row["season"] for row in rows], values) if enough else None}
    return out


def cross_check(trends_dir, cache_dir, fetch=fetch_open_meteo, pause=3.0, today=None):
    trends_dir, cache_dir = Path(trends_dir), Path(cache_dir)
    end = default_end(today or date.today())
    index = json.loads((trends_dir / "index.json").read_text())
    failed = []
    for cell in index["cells"]:
        if cell.get("error"):
            continue
        path = trends_dir / "cells" / f"{cell['id']}.json"
        try:
            result = json.loads(path.read_text())
            payload, how = load_era5(cell, cache_dir, fetch, pause, end)
            for key, extra in second_source(payload).items():
                if key in result["indicators"]:
                    result["indicators"][key]["second_source"] = extra
            write_json(path, result)
        except Exception as error:
            failed.append(cell["id"])
            print(f"failed {cell['id']}: {short(error)}", flush=True)
            continue
        print(f"{how} {cell['id']}", flush=True)
    print(f"failed cells: {', '.join(failed)}" if failed else "failed cells: none", flush=True)
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add an ERA5 trend beside each NASA POWER trend.")
    parser.add_argument("--trends", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path(__file__).resolve().parent / "cache" / "era5")
    parser.add_argument("--pause", type=float, default=3.0)
    args = parser.parse_args(argv)
    cross_check(args.trends, args.cache, pause=args.pause)


if __name__ == "__main__":
    main()
