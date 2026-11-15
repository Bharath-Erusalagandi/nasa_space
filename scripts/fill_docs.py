import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

SHORT = {
    "wet_season_rain_mm": "rain",
    "wet_days": "wet_days",
    "heavy_rain_days": "heavy",
    "wettest_day_mm": "wettest",
    "rain_onset_day": "onset",
    "wet_season_temp_c": "wet_temp",
    "october_temp_c": "october",
    "wet_season_humidity_pct": "humidity",
    "wet_season_soil_wetness_pct": "soil",
}
BLOCKS = ("indicators", "findings", "windows", "cross_check", "grid", "mosquito")
WINDOWS = ("10", "20", "30")
PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
SENSORS = {"heart_rate": ("Heart rate", "bpm"), "spo2": ("SpO2", "points"), "air_temp_c": ("Air temperature", "°C")}


def fill(template, values):
    names = PLACEHOLDER.findall(template)
    for name in names:
        if name not in values:
            raise ValueError(f"unknown placeholder: {name}")
        if values[name] is None:
            raise ValueError(f"no value for placeholder: {name}")
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def replace_block(text, name, body):
    pattern = re.compile(rf"(<!-- fill_docs:{name} -->\n).*?(<!-- /fill_docs:{name} -->)", re.S)
    if not pattern.search(text):
        raise ValueError(f"missing block: {name}")
    return pattern.sub(lambda m: m.group(1) + body.rstrip("\n") + "\n" + m.group(2), text)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def load(root):
    root = Path(root)
    index = read_json(root / "public" / "trends" / "index.json")
    ok = [c for c in index["cells"] if not c.get("error")]
    files = {c["id"]: read_json(root / "public" / "trends" / "cells" / f"{c['id']}.json") for c in ok}
    return {
        "index": index,
        "cells": ok,
        "files": files,
        "places": read_json(root / "trend" / "places.json", []),
        "sources": read_json(root / "public" / "map" / "sources.json", []),
        "validation": read_json(root / "docs" / "validation_results.json"),
    }


def keys(data):
    found = [k for k in SHORT if any(k in c["indicators"] for c in data["cells"])]
    return found + sorted({k for c in data["cells"] for k in c["indicators"]} - set(found))


def meta(data, key):
    for cell in data["files"].values():
        if cell and key in cell["indicators"]:
            return cell["indicators"][key]
    return {"label": key, "unit": "", "definition": ""}


def show_unit(unit):
    return unit.replace("deg C", "°C")


def rate_unit(unit):
    return "days" if unit.startswith("days") else show_unit(unit)


def tested(data, key):
    return [c["indicators"][key] for c in data["cells"]
            if c["indicators"].get(key, {}).get("slope_per_decade") is not None]


def slope_range(rows):
    slopes = [r["slope_per_decade"] for r in rows]
    return (f"{min(slopes):.2f}", f"{max(slopes):.2f}") if slopes else (None, None)


def signed(x):
    return "0.00" if f"{x:.2f}" in ("0.00", "-0.00") else f"{x:+.2f}"


def indicator_table(data):
    lines = ["| Key | Indicator | Unit | Definition |", "|---|---|---|---|"]
    for key in keys(data):
        m = meta(data, key)
        lines.append(f"| `{key}` | {m['label']} | {show_unit(m['unit'])} | {m['definition']} |")
    return "\n".join(lines)


def findings_table(data):
    lines = [
        "| Indicator | Significant after correction (q < 0.05) | Of those, up / down | All cells, up / down / flat "
        "| p < 0.05 before correction | Sen's slope per decade, lowest to highest |",
        "|---|---|---|---|---|---|",
    ]
    for key in keys(data):
        m = meta(data, key)
        rows = tested(data, key)
        sig = [r for r in rows if r["significant_fdr"]]
        up_down = Counter(r["direction"] for r in sig)
        every = Counter(r["direction"] for r in rows)
        raw = sum(r["significant"] for r in rows)
        span = (f"{signed(min(r['slope_per_decade'] for r in rows))} to "
                f"{signed(max(r['slope_per_decade'] for r in rows))} {rate_unit(m['unit'])}") if rows else "no trend"
        lines.append(f"| {m['label']} | {len(sig)} of {len(rows)} | {up_down['increasing']} / {up_down['decreasing']} "
                     f"| {every['increasing']} / {every['decreasing']} / {every['flat']} | {raw} | {span} |")
    return "\n".join(lines)


def windows_table(data):
    lines = ["| Indicator | Last 10 seasons | Last 20 seasons | Last 30 seasons | All seasons |", "|---|---|---|---|---|"]
    for key in keys(data):
        found = [(cell or {}).get("indicators", {}).get(key, {}).get("windows", {}) for cell in data["files"].values()]
        cols = []
        for size in WINDOWS:
            tested_ = [w[size] for w in found if w.get(size)]
            cols.append(f"{sum(t['mk_p'] < 0.05 for t in tested_)} of {len(tested_)}")
        rows = tested(data, key)
        cols.append(f"{sum(r['significant'] for r in rows)} of {len(rows)}")
        lines.append(f"| {meta(data, key)['label']} | " + " | ".join(cols) + " |")
    return "\n".join(lines)


def era5_rows(data, key):
    out = []
    for cid, cell in data["files"].items():
        extra = (cell or {}).get("indicators", {}).get(key, {}).get("second_source") or {}
        if extra.get("trend"):
            nasa = next(c for c in data["cells"] if c["id"] == cid)["indicators"].get(key, {})
            out.append((nasa, extra["trend"]))
    return out


def cross_checked(data):
    return sum(any((i.get("second_source") or {}).get("trend") for i in (cell or {}).get("indicators", {}).values())
               for cell in data["files"].values())


def cross_check_table(data):
    lines = [
        f"ERA5 trends exist for {cross_checked(data)} of the {len(data['cells'])} cells.",
        "",
        "| Indicator | Cells with both | Same direction as NASA POWER | ERA5 p < 0.05 |",
        "|---|---|---|---|",
    ]
    for key in keys(data):
        pairs = era5_rows(data, key)
        same = sum(n.get("direction") == e["direction"] for n, e in pairs)
        sig = sum(e["mk_p"] < 0.05 for _, e in pairs)
        lines.append(f"| {meta(data, key)['label']} | {len(pairs)} | {same} | {sig} |")
    return "\n".join(lines)


def validation_summary(results):
    if not results:
        return ("The validation CSV files in `validation/` hold no rows yet, so no pod sensor error has been "
                "measured and every reading on screen says \"not yet tested\".")
    parts = []
    for kind, (name, unit) in SENSORS.items():
        r = results.get(kind)
        if r:
            who = f" from {r['people']} people" if r.get("people") else ""
            parts.append(f"{name}: {r['n']} pairs{who}, 95% limits of agreement {r['loa_low']:+.1f} to "
                         f"{r['loa_high']:+.1f} {unit}.")
    if results.get("mosquito"):
        m = results["mosquito"]
        parts.append(f"Mosquito listener: {m['n']} clips, {m['accuracy'] * 100:.0f}% correct.")
    missing = [SENSORS[k][0] for k in SENSORS if k not in results] + ([] if "mosquito" in results else ["mosquito listener"])
    if missing:
        parts.append(f"Not yet tested: {', '.join(missing)}.")
    return " ".join(parts)


def other_data(sources):
    return "\n".join(f"- {s['name']}, {s['licence']}, used for {s['used_for']}. {s['url']}" for s in sources)


KM_PER_DEGREE = 111.195
CELL_LAT, CELL_LON = 0.5, 0.625


def cell_km(data):
    ns, ew = set(), set()
    for cell in data["cells"]:
        b = cell.get("bounds") or {"south": cell["lat"] - CELL_LAT / 2, "north": cell["lat"] + CELL_LAT / 2,
                                   "west": cell["lon"] - CELL_LON / 2, "east": cell["lon"] + CELL_LON / 2}
        mid = math.radians((b["south"] + b["north"]) / 2)
        ns.add(round((b["north"] - b["south"]) * KM_PER_DEGREE))
        ew.add(round((b["east"] - b["west"]) * KM_PER_DEGREE * math.cos(mid)))
    if not ns:
        return None
    span = lambda v: str(min(v)) if min(v) == max(v) else f"{min(v)} to {max(v)}"
    return f"{span(ns)} x {span(ew)}"


def grid_sentence(data):
    return (f"A NASA POWER cell is {CELL_LAT} degrees of latitude by {CELL_LON} degrees of longitude, "
            f"about {cell_km(data)} km across the {len(data['cells'])} cells used here.")


def credits(sources):
    rows = ["| Data | Licence | Used for |", "|---|---|---|"]
    rows += [f"| [{s['name']}]({s['url']}) | {s['licence']} | {s['used_for']} |" for s in sources]
    return "\n".join(rows)


def pct(x):
    return f"{round(x * 100)}%"


def mosquito_block(root):
    r = read_json(Path(root) / "models" / "mosquito" / "results.json")
    if not r:
        return "Not trained yet. Run `models/mosquito/train.py` on a machine with the HumBugDB audio."
    s, d = r["species"], r["detector"]
    recall = ", ".join(f"{k} {pct(v)} of {s['recording_count'][k]}" for k, v in s["recording_recall"].items())
    return "\n".join([
        f"Held-out test: split {r['split']}, seed {r['seed']}. No test recording was used in training or to pick the epoch.",
        "",
        "| Model | Test set | Result |",
        "|---|---|---|",
        f"| Detector: mosquito or not | {d['test_recordings']} recordings, {d['test_windows']} windows of 2.1 s | ROC AUC {d['roc_auc']:.3f}. At 0.5 it finds {pct(d['recall'])} of mosquito windows and flags {pct(d['false_alarm_rate'])} of background windows |",
        f"| Species: 8 classes | {s['test_recordings']} recordings, {s['test_windows']} windows | Balanced accuracy {pct(s['recording_balanced_accuracy'])} per recording (mean over its windows), {pct(s['window_balanced_accuracy'])} per single window |",
        "",
        f"Species recall per recording: {recall}.",
    ] + ([
        "",
        "By genus, which is what the conversation acts on: " + ", ".join(
            f"{k} {pct(v)} of {r['species_group']['count'][k]}" for k, v in r["species_group"]["recall"].items())
        + f" (balanced {pct(r['species_group']['balanced_accuracy'])}).",
    ] if "species_group" in r else []) + ([
        "",
        "The same test recordings through a simulated phone speaker, room and room noise (one random path per window, `models/mosquito/channel.py`): "
        f"the detector finds {pct(d['through_the_air']['recall'])} of mosquito windows and flags {pct(d['through_the_air']['false_alarm_rate'])} of background windows; "
        f"the species model is right for {pct(s['through_the_air']['recording_balanced_accuracy'])} of recordings (balanced) and names the right genus for {pct(s['through_the_air']['recording_genus_accuracy'])}. "
        "This is a simulation. The models have not been measured with a real phone and laptop.",
    ] if "through_the_air" in d and "through_the_air" in s else []) + ([
        "",
        f"Voices, none of them a mosquito: of {d['voices']['speech_windows']} windows of read speech from speakers the detector never heard (LibriSpeech dev-clean), "
        f"it flags {pct(d['voices']['speech_flagged'])} as recorded and {pct(d['voices']['speech_flagged_through_the_air'])} through the simulated path; "
        f"of {d['voices']['tone_windows']} synthetic steady tones in the voice range, {pct(d['voices']['tones_flagged'])} and {pct(d['voices']['tones_flagged_through_the_air'])}.",
    ] if d.get("voices", {}).get("speech_windows") else []) + [
        "",
        "The recording for each species on the phone page is, of the 30 longest test recordings, the one the model gets right as recorded and through the most of 8 simulated paths, so the page shows the model at its best; the figures above are the honest rate.",
    ])


def values(root):
    data = load(root)
    index = data["index"]
    out = {
        "generated": index["generated"],
        "period": index["period"],
        "end_date": index.get("data_end"),
        "n_cells": len(data["cells"]),
        "n_cells_failed": len(index["cells"]) - len(data["cells"]),
        "n_places": len(data["places"]),
        "n_towns": sum(p.get("kind") == "town" for p in data["places"]),
        "n_facilities": sum(p.get("kind") == "facility" for p in data["places"]),
        "n_cross_checked": cross_checked(data),
        "validation_summary": validation_summary(data["validation"]),
        "other_data": other_data(data["sources"]),
        "cell_km": cell_km(data),
    }
    seasons = [r["n"] for c in data["cells"] for r in c["indicators"].values() if r.get("n")]
    out["n_seasons"] = max(seasons) if seasons else None
    for key, short in SHORT.items():
        rows = tested(data, key)
        sig = [r for r in rows if r["significant_fdr"]]
        out[f"n_{short}_significant"] = len(sig)
        out[f"n_{short}_not_significant"] = len(rows) - len(sig)
        out[f"n_{short}_significant_increasing"] = sum(r["direction"] == "increasing" for r in sig)
        out[f"n_{short}_significant_decreasing"] = sum(r["direction"] == "decreasing" for r in sig)
        out[f"{short}_slope_min"], out[f"{short}_slope_max"] = slope_range(rows)
        out[f"n_{short}_era5_increasing_significant"] = sum(
            e["direction"] == "increasing" and e["mk_p"] < 0.05 for _, e in era5_rows(data, key))
    return out


def run(root):
    root = Path(root)
    docs = root / "docs"
    data = load(root)
    submission = fill((docs / "SUBMISSION.template.md").read_text(encoding="utf-8"), values(root))
    (docs / "SUBMISSION.md").write_text(submission, encoding="utf-8")
    methods = (docs / "METHODS.md").read_text(encoding="utf-8")
    bodies = {"indicators": indicator_table(data), "findings": findings_table(data),
              "windows": windows_table(data), "cross_check": cross_check_table(data),
              "grid": grid_sentence(data), "mosquito": mosquito_block(root)}
    for name in BLOCKS:
        methods = replace_block(methods, name, bodies[name])
    (docs / "METHODS.md").write_text(methods, encoding="utf-8")
    readme = root / "README.md"
    readme.write_text(replace_block(readme.read_text(encoding="utf-8"), "credits", credits(data["sources"])), encoding="utf-8")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
    print("wrote docs/SUBMISSION.md and the generated blocks of docs/METHODS.md and README.md")
