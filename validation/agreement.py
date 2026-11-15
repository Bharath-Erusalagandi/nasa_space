import csv
import math
import re
from pathlib import Path

CONDITIONS = ("rest", "post_exercise", "motion")


def agreement(device, reference, tolerance=None):
    if len(device) != len(reference):
        raise ValueError("device and reference need the same number of readings")
    if not device:
        raise ValueError("no pairs to compare")
    diffs = [d - r for d, r in zip(device, reference)]
    n = len(diffs)
    bias = sum(diffs) / n
    sd = math.sqrt(sum((x - bias) ** 2 for x in diffs) / (n - 1)) if n > 1 else None
    within = None
    if tolerance is not None:
        # rounding keeps a difference like 98.1 - 97.1 on the boundary
        within = sum(round(abs(x), 9) <= tolerance for x in diffs) / n
    return {
        "n": n,
        "bias": bias,
        "sd": sd,
        "loa_low": None if sd is None else bias - 1.96 * sd,
        "loa_high": None if sd is None else bias + 1.96 * sd,
        "mae": sum(abs(x) for x in diffs) / n,
        "within_tolerance": within,
    }


def read_rows(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = []
        for row in csv.DictReader(f):
            clean = {k.strip(): (v or "").strip() for k, v in row.items() if isinstance(k, str)}
            if any(clean.values()):
                rows.append(clean)
    return rows


def number(text):
    try:
        x = float(text)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def condition(row):
    return re.sub(r"[\s-]+", "_", row.get("condition", "").strip().lower())


def unknown_conditions(rows):
    return sorted({condition(row) for row in rows if condition(row) not in CONDITIONS})


def select_pairs(rows, device_col, ref_col, conditions=None):
    wanted = None if conditions is None else {c.lower() for c in conditions}
    pairs, excluded = [], 0
    for row in rows:
        if wanted is not None and condition(row) not in wanted:
            continue
        d, r = number(row.get(device_col, "")), number(row.get(ref_col, ""))
        if d is None or r is None:
            excluded += 1
        else:
            pairs.append((row, d, r))
    return pairs, excluded


def load_pairs(path, device_col, ref_col, conditions=None):
    rows = read_rows(path)
    pairs, excluded = select_pairs(rows, device_col, ref_col, conditions)
    if conditions is not None:
        excluded += sum(condition(row) not in CONDITIONS for row in rows)
    return [d for _, d, _ in pairs], [r for _, _, r in pairs], excluded
