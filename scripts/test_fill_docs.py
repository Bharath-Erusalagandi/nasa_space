import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fill_docs  # noqa: E402

KEYS = ["wet_season_rain_mm", "october_temp_c"]


def summary(slope, q, mk_p=0.01, direction=None):
    return {
        "n": 45, "slope_per_decade": slope, "ci_low_per_decade": slope - 1, "ci_high_per_decade": slope + 1,
        "mk_p": mk_p, "q": q, "significant": mk_p < 0.05, "significant_fdr": q < 0.05,
        "direction": direction or ("increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"),
        "autocorrelation_warning": False,
    }


def trend(slope, p):
    return {"n": 45, "slope_per_decade": slope, "mk_p": p, "direction": "increasing" if slope > 0 else "decreasing"}


def indicator(label, unit, definition, era5=None):
    out = {"label": label, "unit": unit, "definition": definition, "series": [], "trend": None,
           "windows": {"10": trend(-1.0, 0.4), "20": trend(-0.5, 0.03), "30": None}}
    if era5 is not None:
        out["second_source"] = {"name": "ECMWF ERA5 via Open-Meteo", "trend": era5}
    return out


def make_root(tmp_path, validation=None):
    trends = tmp_path / "public" / "trends"
    (trends / "cells").mkdir(parents=True)
    cells = [
        {"id": "a", "lat": -14.0, "lon": 32.5, "indicators": {
            "wet_season_rain_mm": summary(-12.5, 0.8, 0.4), "october_temp_c": summary(0.3, 0.01)}},
        {"id": "b", "lat": -13.5, "lon": 32.5, "indicators": {
            "wet_season_rain_mm": summary(20.0, 0.9, 0.6), "october_temp_c": summary(0.45, 0.02)}},
        {"id": "c", "lat": -13.0, "lon": 32.5, "indicators": {
            "wet_season_rain_mm": summary(3.0, 0.9, 0.7), "october_temp_c": summary(0.2, 0.2, 0.08)}},
        {"id": "bad", "lat": -12.5, "lon": 32.5, "error": "URLError: timed out"},
    ]
    index = {"generated": "2026-11-14", "data_end": "2026-09-12", "source": "NASA POWER",
             "period": "1981/82 to 2025/26", "cells": cells, "places": []}
    (trends / "index.json").write_text(json.dumps(index))
    for cid, era5 in (("a", trend(0.4, 0.001)), ("b", None), ("c", trend(-0.1, 0.5))):
        cell = {"indicators": {
            "wet_season_rain_mm": indicator("Wet-season rainfall", "mm", "Total rain from 1 Nov to 30 Apr.",
                                            trend(5.0, 0.7) if era5 else None),
            "october_temp_c": indicator("October temperature", "deg C", "Mean air temperature in October.", era5),
        }}
        (trends / "cells" / f"{cid}.json").write_text(json.dumps(cell))
    (tmp_path / "trend").mkdir()
    places = [{"id": "katete", "kind": "town"}, {"id": "x", "kind": "facility"}, {"id": "y", "kind": "facility"},
              {"id": "cell-1", "kind": "cell"}]
    (tmp_path / "trend" / "places.json").write_text(json.dumps(places))
    (tmp_path / "public" / "map").mkdir(parents=True)
    sources = [{"name": "OpenStreetMap", "licence": "ODbL", "url": "https://osm.org", "fetched": "2026-11-14",
                "used_for": "roads"}]
    (tmp_path / "public" / "map" / "sources.json").write_text(json.dumps(sources))
    (tmp_path / "docs").mkdir()
    if validation is not None:
        (tmp_path / "docs" / "validation_results.json").write_text(json.dumps(validation))
    return tmp_path


def test_fill_replaces_every_placeholder():
    assert fill_docs.fill("{{a}} and {{ b }}", {"a": 1, "b": "two"}) == "1 and two"


def test_fill_fails_on_an_unknown_placeholder():
    with pytest.raises(ValueError, match="unknown placeholder: c"):
        fill_docs.fill("{{a}} {{c}}", {"a": 1})


def test_fill_fails_when_a_value_is_missing():
    with pytest.raises(ValueError, match="no value for placeholder: a"):
        fill_docs.fill("{{a}}", {"a": None})


def test_values_count_cells_and_significant_results(tmp_path):
    values = fill_docs.values(make_root(tmp_path))
    assert values["n_cells"] == 3
    assert values["n_cells_failed"] == 1
    assert values["n_rain_significant"] == 0
    assert values["n_rain_not_significant"] == 3
    assert values["n_october_significant"] == 2
    assert values["october_slope_min"] == "0.20"
    assert values["october_slope_max"] == "0.45"
    assert values["n_facilities"] == 2
    assert values["n_towns"] == 1
    assert values["end_date"] == "2026-09-12"
    assert values["n_cross_checked"] == 2
    assert values["n_october_era5_increasing_significant"] == 1


def test_validation_summary_says_nothing_was_tested_without_results(tmp_path):
    text = fill_docs.values(make_root(tmp_path))["validation_summary"]
    assert "no rows yet" in text


def test_validation_summary_reports_measured_sensors(tmp_path):
    results = {"heart_rate": {"n": 48, "bias": 1.0, "sd": 2.45, "loa_low": -3.8, "loa_high": 5.8, "mae": 2.1,
                              "within_tolerance": 0.9, "people": 8}}
    text = fill_docs.values(make_root(tmp_path, results))["validation_summary"]
    assert "48 pairs from 8 people" in text
    assert "-3.8 to +5.8 bpm" in text


def test_findings_table_counts_directions_and_slope_range(tmp_path):
    table = fill_docs.findings_table(fill_docs.load(make_root(tmp_path)))
    october = next(line for line in table.splitlines() if line.startswith("| October temperature"))
    assert october == "| October temperature | 2 of 3 | 2 / 0 | 3 / 0 / 0 | 2 | +0.20 to +0.45 °C |"


def test_indicator_table_copies_label_unit_and_definition(tmp_path):
    table = fill_docs.indicator_table(fill_docs.load(make_root(tmp_path)))
    assert "| `october_temp_c` | October temperature | °C | Mean air temperature in October. |" in table


def test_windows_table_counts_cells_with_p_below_005(tmp_path):
    table = fill_docs.windows_table(fill_docs.load(make_root(tmp_path)))
    assert "| October temperature | 0 of 3 | 3 of 3 | 0 of 0 | 2 of 3 |" in table


def test_replace_block_keeps_text_outside_the_markers():
    text = "head\n<!-- fill_docs:x -->\nold\n<!-- /fill_docs:x -->\ntail\n"
    out = fill_docs.replace_block(text, "x", "new")
    assert out == "head\n<!-- fill_docs:x -->\nnew\n<!-- /fill_docs:x -->\ntail\n"
    assert fill_docs.replace_block(out, "x", "new") == out


def test_replace_block_fails_without_markers():
    with pytest.raises(ValueError, match="missing block: x"):
        fill_docs.replace_block("no markers here", "x", "new")


def test_run_writes_submission_and_methods_blocks(tmp_path):
    root = make_root(tmp_path)
    (root / "docs" / "SUBMISSION.template.md").write_text("{{n_cells}} cells, {{n_october_significant}} warming\n")
    blocks = "".join(f"<!-- fill_docs:{name} -->\n<!-- /fill_docs:{name} -->\n" for name in fill_docs.BLOCKS)
    (root / "docs" / "METHODS.md").write_text("# Methods\n" + blocks)
    (root / "README.md").write_text("# App\n<!-- fill_docs:credits -->\n<!-- /fill_docs:credits -->\n")
    fill_docs.run(root)
    assert "| [OpenStreetMap](https://osm.org) | ODbL | roads |" in (root / "README.md").read_text()
    assert (root / "docs" / "SUBMISSION.md").read_text() == "3 cells, 2 warming\n"
    methods = (root / "docs" / "METHODS.md").read_text()
    assert "| October temperature | 2 of 3 |" in methods
    assert "{{" not in methods


def test_zero_slope_significant_cell_counts_under_its_direction(tmp_path):
    root = make_root(tmp_path)
    path = root / "public" / "trends" / "index.json"
    index = json.loads(path.read_text())
    index["cells"][2]["indicators"]["october_temp_c"] = summary(0.0, 0.01, 0.001, direction="increasing")
    path.write_text(json.dumps(index))
    table = fill_docs.findings_table(fill_docs.load(root))
    october = next(line for line in table.splitlines() if line.startswith("| October temperature"))
    assert october == "| October temperature | 3 of 3 | 3 / 0 | 3 / 0 / 0 | 3 | 0.00 to +0.45 °C |"
    assert fill_docs.values(root)["n_october_significant_increasing"] == 3


def test_cell_size_comes_from_the_grid_and_the_cell_latitudes(tmp_path):
    root = make_root(tmp_path)
    assert fill_docs.values(root)["cell_km"] == "56 x 67 to 68"
