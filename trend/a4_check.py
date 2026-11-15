# written with Claude (Anthropic), see docs/AI_USE.md
import json
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from trend_detective import analyse, autocorrelation_bounds, default_end, fetch_power, trend  # noqa: E402

CACHE = HERE / "cache" / "a4"
START = date(1981, 1, 1)
END = default_end(date(2026, 11, 14))


def load(place):
    path = CACHE / f"{place['name'].lower()}.json"
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fetch_power(place["lat"], place["lon"], START, END)))
        time.sleep(1)
    return json.loads(path.read_text())


def show_p(p):
    return "<0.001" if round(p, 3) == 0 else f"{p:.3f}"


def show_ref_p(p):
    return p if isinstance(p, str) else f"{p:.3f}"


def main():
    ref = json.loads((HERE / "a4_reference.json").read_text())
    results = {p["name"]: analyse(load(p), p["name"], p["lat"], p["lon"]) for p in ref["places"]}
    mismatches = 0
    print(f"{'indicator':<20}{'place':<9}{'ours':>18}{'plan':>18}  agree")
    for key, row in ref["table"].items():
        for name, (slope, p) in row.items():
            t = results[name]["indicators"][key]["trend"]
            ours = (f"{t['slope_per_decade']:+.2f}", show_p(t["mk_p"]))
            plan = (f"{slope:+.2f}", show_ref_p(p))
            ok = ours == plan
            mismatches += not ok
            print(f"{key:<20}{name:<9}{ours[0] + ' (' + ours[1] + ')':>18}{plan[0] + ' (' + plan[1] + ')':>18}  {'yes' if ok else 'NO'}")

    flags = [(name, key) for name, r in results.items() for key, ind in r["indicators"].items()
             if ind["trend"] and ind["trend"]["autocorrelation_warning"]]
    print(f"\nautocorrelation caution (two-sided 95% bound): {len(flags)} of 35 series")
    for name, key in flags:
        print(f"  {name} {key}")
    one_sided = [(name, key) for name, r in results.items() for key, ind in r["indicators"].items()
                 if ind["trend"] and ind["trend"]["lag1_autocorrelation"] > autocorrelation_bounds(ind["trend"]["n"], 1.645)[1]]
    print(f"one-sided 95% bound would flag: {len(one_sided)} of 35 series, "
          f"Lundazi wet_days {'included' if ('Lundazi', 'wet_days') in one_sided else 'not included'}")

    katete = results["Katete"]["indicators"]["october_temp_c"]
    print(f"\nKatete October temperature, {results['Katete']['period']}: {katete['verdict']}")
    rows = [r for r in katete["series"] if r["value"] is not None]
    for size, (slope, p) in ref["katete_october_windows"].items():
        last = rows[-int(size):]
        t = trend([r["season"] for r in last], [r["value"] for r in last])
        print(f"  last {size} seasons: {t['slope_per_decade']:+.2f} per decade (p {t['mk_p']:.3f}); plan {slope:+.2f} (p {p:.3f})")

    print(f"\nmismatches: {mismatches} of 35")


if __name__ == "__main__":
    main()
