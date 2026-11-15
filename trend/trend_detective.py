# written with Claude (Anthropic), see docs/AI_USE.md
import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import numpy as np
from scipy import stats

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOURCE = (
    "NASA POWER daily point API (MERRA-2 reanalysis): "
    "PRECTOTCORR (rain, mm/day) and T2M (air temperature at 2 m, deg C)"
)
MIN_SEASONS = 10

INDICATORS = {
    "wet_season_rain_mm": ("Wet-season rainfall", "mm", "mm", "Total rain from 1 Nov to 30 Apr."),
    "wet_days": ("Rainy days", "days", "days", "Days from 1 Nov to 30 Apr with at least 1 mm of rain."),
    "heavy_rain_days": ("Heavy-rain days", "days", "days", "Days from 1 Nov to 30 Apr with at least 20 mm of rain."),
    "wettest_day_mm": ("Wettest day", "mm", "mm", "Largest one-day rainfall from 1 Nov to 30 Apr."),
    "rain_onset_day": (
        "Start of the rains",
        "days after 1 Oct",
        "days",
        "Days after 1 Oct until the rain of the last 10 days first adds up to at least 25 mm.",
    ),
    "wet_season_temp_c": ("Wet-season temperature", "deg C", "deg C", "Mean air temperature from 1 Nov to 30 Apr."),
    "october_temp_c": ("October temperature", "deg C", "deg C", "Mean air temperature in October, the hottest month."),
}


def fetch_power(lat, lon, start, end, timeout=120):
    query = urllib.parse.urlencode({
        "parameters": "PRECTOTCORR,T2M",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    })
    with urllib.request.urlopen(f"{POWER_URL}?{query}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_power(payload):
    fill = payload.get("header", {}).get("fill_value", -999)
    params = payload["properties"]["parameter"]
    out = {}
    for name in ("PRECTOTCORR", "T2M"):
        out[name] = {
            datetime.strptime(day, "%Y%m%d").date(): float(value)
            for day, value in params.get(name, {}).items()
            if value is not None and value != fill
        }
    return out


def default_end(today):
    return today - timedelta(days=60)


def season_label(season):
    return f"{season}/{(season + 1) % 100:02d}"


def _days(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _window(data, start, end):
    days = _days(start, end)
    if any(day not in data for day in days):
        return None
    return np.array([data[day] for day in days])


def _onset(rain, season, total=25.0, window=10):
    # the day on which rain since 1 Oct over the last `window` days first reaches `total`
    first = date(season, 10, 1)
    recent = []
    for day in _days(first, date(season + 1, 6, 30)):
        if day not in rain:
            return None
        recent = (recent + [rain[day]])[-window:]
        if sum(recent) >= total:
            return (day - first).days
    return None


def _round(value):
    return None if value is None else round(float(value), 4)


def seasonal_indicators(rain, temp=None, wet_mm=1.0, heavy_mm=20.0, onset_mm=25.0, onset_days=10):
    temp = temp or {}
    out = {key: [] for key in INDICATORS}
    if not rain:
        return out
    first, last = min(rain), max(rain)
    start = first.year if first <= date(first.year, 7, 1) else first.year + 1
    for season in range(start, last.year):
        if date(season + 1, 6, 30) > last:
            break
        wet = _window(rain, date(season, 11, 1), date(season + 1, 4, 30))
        wet_t = _window(temp, date(season, 11, 1), date(season + 1, 4, 30))
        oct_t = _window(temp, date(season, 10, 1), date(season, 10, 31))
        values = {
            "wet_season_rain_mm": None if wet is None else wet.sum(),
            "wet_days": None if wet is None else int((wet >= wet_mm).sum()),
            "heavy_rain_days": None if wet is None else int((wet >= heavy_mm).sum()),
            "wettest_day_mm": None if wet is None else wet.max(),
            "rain_onset_day": _onset(rain, season, onset_mm, onset_days),
            "wet_season_temp_c": None if wet_t is None else wet_t.mean(),
            "october_temp_c": None if oct_t is None else oct_t.mean(),
        }
        for key, value in values.items():
            out[key].append({"season": season, "label": season_label(season), "value": _round(value)})
    return out


def mann_kendall(values):
    x = np.asarray(values, dtype=float)
    n = len(x)
    s = sum(np.sign(x[j] - x[i]) for i in range(n - 1) for j in range(i + 1, n))
    _, counts = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in counts)) / 18.0
    if s == 0 or var <= 0:
        z = 0.0
    else:
        z = (s - np.sign(s)) / math.sqrt(var)
    p = 2 * stats.norm.sf(abs(z))
    return int(s), float(z), float(p)


def lag1_autocorrelation(residuals):
    r = np.asarray(residuals, dtype=float)
    d = r - r.mean()
    denom = float((d * d).sum())
    if denom == 0:
        return 0.0
    return float((d[:-1] * d[1:]).sum() / denom)


def autocorrelation_bounds(n, z=1.96):
    half = z * math.sqrt(n - 2)
    return (-1 - half) / (n - 1), (-1 + half) / (n - 1)


def trend(years, values, alpha=0.05):
    pairs = [(float(y), float(v)) for y, v in zip(years, values) if v is not None]
    if len(pairs) < MIN_SEASONS:
        raise ValueError(f"need at least {MIN_SEASONS} values, got {len(pairs)}")
    x = np.array([p[0] for p in pairs])
    y = np.array([p[1] for p in pairs])
    n = len(x)
    i, j = np.triu_indices(n, k=1)
    keep = x[j] != x[i]
    slope = float(np.median((y[j] - y[i])[keep] / (x[j] - x[i])[keep]))
    _, _, low, high = stats.theilslopes(y, x, alpha=1 - alpha)
    intercept = float(np.median(y) - slope * np.median(x))
    s, z, p = mann_kendall(y)
    ols = stats.linregress(x, y)
    ols_p = 1.0 if math.isnan(ols.pvalue) else float(ols.pvalue)
    r1 = lag1_autocorrelation(y - (intercept + slope * x))
    lower, upper = autocorrelation_bounds(n)
    # tied low counts can give a zero median slope under a significant test; then the sign of S decides
    sign = slope if slope != 0 or p >= alpha else s
    direction = "increasing" if sign > 0 else "decreasing" if sign < 0 else "flat"
    return {
        "n": n,
        "slope_per_year": slope,
        "slope_per_decade": slope * 10,
        "ci_low_per_decade": float(low) * 10,
        "ci_high_per_decade": float(high) * 10,
        "intercept": intercept,
        "mk_s": s,
        "mk_z": z,
        "mk_p": p,
        "ols_slope_per_decade": float(ols.slope) * 10,
        "ols_p": ols_p,
        "lag1_autocorrelation": r1,
        "autocorrelation_warning": bool(r1 < lower or r1 > upper),
        "direction": direction,
        "significant": bool(p < alpha),
        "alpha": alpha,
    }


def format_p(p):
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def _num(x):
    text = f"{x:.2f}"
    return "0.00" if text == "-0.00" else text


def verdict(result, unit):
    if result is None:
        return f"Not enough seasons to test (need at least {MIN_SEASONS})."
    rng = f"95% range {_num(result['ci_low_per_decade'])} to {_num(result['ci_high_per_decade'])}"
    rate = f"{abs(result['slope_per_decade']):.2f} {unit} per decade"
    if result["direction"] == "flat":
        head = f"No change ({rate}; {rng})"
    elif _num(abs(result["slope_per_decade"])) == "0.00":
        head = f"{result['direction'].capitalize()}, though the median change rounds to {rate} ({rng})"
    else:
        head = f"{result['direction'].capitalize()} by {rate} ({rng})"
    judged = "statistically significant" if result["significant"] else "not statistically significant"
    return f"{head}; Mann-Kendall {format_p(result['mk_p'])}: {judged}."


def analyse(payload, place, lat=None, lon=None):
    data = parse_power(payload)
    series = seasonal_indicators(data["PRECTOTCORR"], data["T2M"])
    seasons = [row["season"] for rows in series.values() for row in rows]
    period = f"{season_label(min(seasons))} to {season_label(max(seasons))}" if seasons else ""
    indicators = {}
    for key, (label, unit, rate_unit, definition) in INDICATORS.items():
        rows = series[key]
        values = [row["value"] for row in rows]
        has = sum(v is not None for v in values)
        result = trend([row["season"] for row in rows], values) if has >= MIN_SEASONS else None
        indicators[key] = {
            "label": label,
            "unit": unit,
            "definition": definition,
            "series": rows,
            "trend": result,
            "verdict": verdict(result, rate_unit),
        }
    return {"place": place, "lat": lat, "lon": lon, "source": SOURCE, "period": period, "indicators": indicators}


def card(indicator):
    rows = [r for r in indicator["series"] if r["value"] is not None]
    lines = [indicator["label"], f"  {indicator['definition']}"]
    if rows:
        lines.append(f"  Seasons: {rows[0]['label']} to {rows[-1]['label']} ({len(rows)} with a value)")
    lines.append(f"  {indicator['verdict']}")
    t = indicator["trend"]
    if t:
        lines.append(f"  Least squares: {t['ols_slope_per_decade']:+.2f} per decade, t-test {format_p(t['ols_p'])}")
        if t["autocorrelation_warning"]:
            lines.append(f"  Caution: neighbouring seasons are correlated (lag-1 r = {t['lag1_autocorrelation']:.2f}), so p may be too small.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seasonal rain and temperature trends from NASA POWER.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = fetch_power(args.lat, args.lon, date(1981, 1, 1), default_end(date.today()))
    result = analyse(payload, args.name or f"{args.lat}, {args.lon}", args.lat, args.lon)
    if args.json:
        json.dump(result, sys.stdout, indent=1)
        print()
        return
    print(f"{result['place']} ({args.lat}, {args.lon}), {result['period']}")
    print(f"Source: {result['source']}\n")
    print("\n\n".join(card(ind) for ind in result["indicators"].values()))


if __name__ == "__main__":
    main()
