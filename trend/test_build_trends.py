# written with Claude (Anthropic), see docs/AI_USE.md
import json
from datetime import date
import pytest
import build_trends as bt
from test_trend_detective import december_rain_payload

def test_power_cell_snaps_to_the_nasa_grid():
    # checked against the live API: points in one predicted cell return identical data
    assert bt.power_cell(-14.06, 32.04) == (-14.0, 31.875)
    assert bt.power_cell(-13.80, 32.25) == (-14.0, 32.5)
    assert bt.power_cell(-14.30, 32.04) == (-14.5, 31.875)

def test_cell_id_and_bounds():
    assert bt.cell_id((-14.0, 31.875)) == "-14.000_31.875"
    assert bt.cell_bounds((-14.0, 31.875)) == {"south": -14.25, "north": -13.75, "west": 31.5625, "east": 32.1875}

def test_window_trends_use_only_the_last_seasons():
    series = [{"season": 1981 + i, "label": "", "value": 900 + 3 * i} for i in range(45)]
    w = bt.window_trends(series)
    assert w["10"]["n"] == 10
    assert w["10"]["slope_per_decade"] == pytest.approx(30.0)
    assert bt.window_trends(series[:12])["20"] is None

def test_q_values_follow_benjamini_hochberg():
    # p = 0.01, 0.04, 0.03, 0.005 -> q = 0.02, 0.04, 0.04, 0.02
    cells = [{"indicators": {"x": {"mk_p": p}}} for p in (0.01, 0.04, 0.03, 0.005)]
    bt.add_q_values(cells)
    assert [c["indicators"]["x"]["q"] for c in cells] == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert all(c["indicators"]["x"]["significant_fdr"] for c in cells)

PLACES = [
    {"id": "katete", "name": "Katete", "lat": -14.06, "lon": 32.04},
    {"id": "near-katete", "name": "Near Katete", "lat": -13.80, "lon": 32.15},   # same cell
    {"id": "chipata", "name": "Chipata", "lat": -13.63, "lon": 32.65},
]

def counting_fetch(calls, fail_lon=None):
    def fetch(lat, lon, start, end, timeout=120):
        calls.append((lat, lon))
        if lon == fail_lon:
            raise OSError("network down")
        return december_rain_payload(1981, 12)
    return fetch

def test_posts_in_one_cell_share_one_download(tmp_path):
    calls = []
    index = bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch(calls), pause=0, today=date(2026, 11, 14))
    assert len(calls) == 2
    assert {p["id"]: p["cell"] for p in index["places"]} == {
        "katete": "-14.000_31.875", "near-katete": "-14.000_31.875", "chipata": "-13.500_32.500"}
    assert json.loads((tmp_path / "out" / "cells" / "-14.000_31.875.json").read_text())["indicators"]["wet_season_rain_mm"]["windows"]["10"]["n"] == 10

def test_second_build_downloads_nothing(tmp_path):
    bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch([]), pause=0, today=date(2026, 11, 14))
    calls = []
    bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch(calls), pause=0, today=date(2026, 11, 14))
    assert calls == []

def test_build_survives_a_failed_cell(tmp_path):
    index = bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch([], fail_lon=32.5), pause=0, today=date(2026, 11, 14))
    by_id = {c["id"]: c for c in index["cells"]}
    assert "error" in by_id["-13.500_32.500"]
    assert by_id["-14.000_31.875"]["indicators"]["wet_season_rain_mm"]["slope_per_decade"] == pytest.approx(310.0)


SUMMARY_KEYS = {"n", "slope_per_decade", "ci_low_per_decade", "ci_high_per_decade", "mk_p", "q",
                "significant", "significant_fdr", "direction", "autocorrelation_warning"}
TODAY = date(2026, 11, 14)


def run(tmp_path, places=PLACES, calls=None, **kw):
    fetch = kw.pop("fetch", None) or counting_fetch([] if calls is None else calls)
    return bt.build(places, tmp_path / "cache", tmp_path / "out", fetch=fetch, pause=0, today=TODAY, **kw)


def test_grid_tie_rounds_to_the_even_neighbour():
    assert bt.power_cell(-13.75, 32.0)[0] == -14.0


def test_extra_place_keys_pass_through(tmp_path):
    places = [{**PLACES[0], "kind": "facility", "type": "Health Post", "district": "Katete"}]
    index = run(tmp_path, places)
    assert index["places"] == [{"id": "katete", "name": "Katete", "lat": -14.06, "lon": 32.04,
                                "kind": "facility", "type": "Health Post", "district": "Katete",
                                "cell": "-14.000_31.875"}]


@pytest.mark.parametrize("broken", ["", '{"properties": {"param', "not json"])
def test_unreadable_cache_is_downloaded_again(tmp_path, broken):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "-14.000_31.875.json").write_text(broken)
    calls = []
    index = run(tmp_path, PLACES[:1], calls)
    assert calls == [(-14.0, 31.875)]
    assert "error" not in index["cells"][0]
    assert json.loads((cache / "-14.000_31.875.json").read_text())["properties"]["parameter"]


def test_pause_only_after_a_real_download(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(bt.time, "sleep", waits.append)
    bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch([]), pause=0.5, today=TODAY)
    assert waits == [0.5, 0.5]
    waits.clear()
    bt.build(PLACES, tmp_path / "cache", tmp_path / "out", fetch=counting_fetch([]), pause=0.5, today=TODAY)
    assert waits == []


def test_summaries_have_exactly_the_documented_keys(tmp_path):
    index = run(tmp_path)
    good = [c for c in index["cells"] if "error" not in c]
    assert good
    for cell in good:
        assert list(cell["indicators"]) == list(bt.INDICATORS)
        for summary in cell["indicators"].values():
            assert set(summary) == SUMMARY_KEYS


def test_indicator_without_a_trend_gets_nulls_and_false(tmp_path):
    index = run(tmp_path, PLACES[:1], fetch=lambda *a, **k: december_rain_payload(1981, 9))
    assert "error" not in index["cells"][0]
    summary = index["cells"][0]["indicators"]["wet_season_rain_mm"]
    assert summary == {"n": None, "slope_per_decade": None, "ci_low_per_decade": None, "ci_high_per_decade": None,
                    "mk_p": None, "q": None, "significant": False, "significant_fdr": False,
                    "direction": None, "autocorrelation_warning": False}


def test_cells_are_sorted_by_id(tmp_path):
    places = [PLACES[2], {"id": "far", "name": "Far", "lat": -12.29, "lon": 33.18}, PLACES[0]]
    ids = [c["id"] for c in run(tmp_path, places)["cells"]]
    assert ids == sorted(ids) and len(ids) == 3


def test_failed_cell_entry_and_no_cell_file(tmp_path):
    index = run(tmp_path, fetch=counting_fetch([], fail_lon=32.5))
    failed = next(c for c in index["cells"] if c["id"] == "-13.500_32.500")
    assert set(failed) == {"id", "lat", "lon", "bounds", "error"}
    assert "network down" in failed["error"]
    assert not (tmp_path / "out" / "cells" / "-13.500_32.500.json").exists()
    assert not (tmp_path / "cache" / "-13.500_32.500.json").exists()


def test_index_header_and_file_on_disk(tmp_path):
    index = run(tmp_path)
    assert index["generated"] == "2026-11-14"
    assert index["period"] == "1981/82 to 1992/93"
    assert index["source"] == bt.SOURCE
    assert json.loads((tmp_path / "out" / "index.json").read_text()) == index


def test_fetch_asks_for_the_full_record(tmp_path):
    asked = []

    def fetch(lat, lon, start, end, timeout=120):
        asked.append((start, end))
        return december_rain_payload(1981, 12)

    run(tmp_path, PLACES[:1], fetch=fetch)
    assert asked == [(date(1981, 1, 1), bt.default_end(TODAY))]


def test_cell_file_carries_the_cell_and_all_windows(tmp_path):
    run(tmp_path, PLACES[:1])
    data = json.loads((tmp_path / "out" / "cells" / "-14.000_31.875.json").read_text())
    assert data["cell"] == {"id": "-14.000_31.875", "lat": -14.0, "lon": 31.875,
                            "bounds": bt.cell_bounds((-14.0, 31.875))}
    windows = data["indicators"]["wet_season_rain_mm"]["windows"]
    assert windows["10"]["n"] == 10 and windows["20"] is None and windows["30"] is None


def test_window_needs_ten_values_among_the_last_n():
    series = [{"season": 1981 + i, "label": "", "value": None if i % 2 else float(i)} for i in range(30)]
    w = bt.window_trends(series)
    assert w["10"] is None
    assert w["20"]["n"] == 10
    assert w["30"]["n"] == 15


def test_q_values_skip_missing_p():
    cells = [{"indicators": {"x": {"mk_p": 0.01, "q": None}}}, {"indicators": {"x": {"mk_p": None, "q": None}}},
             {"error": "x"}]
    bt.add_q_values(cells)
    assert cells[0]["indicators"]["x"]["q"] == pytest.approx(0.01)
    assert cells[1]["indicators"]["x"]["q"] is None


def test_zero_sen_slope_with_a_significant_test_takes_the_sign_of_s():
    import trend_detective as td
    # 30 dry seasons then 10 with one heavy day: most pairwise slopes are 0, but S = 300
    t = td.trend(range(1981, 2021), [0] * 30 + [1] * 10)
    assert t["slope_per_decade"] == 0.0 and t["mk_s"] == 300 and t["significant"]
    assert t["direction"] == "increasing"
    assert td.verdict(t, "days") == (
        f"Increasing, though the median change rounds to 0.00 days per decade "
        f"(95% range 0.00 to {td._num(t['ci_high_per_decade'])}); Mann-Kendall p < 0.001: statistically significant.")
    falling = td.trend(range(1981, 2021), [1] * 10 + [0] * 30)
    assert falling["direction"] == "decreasing"
    assert falling["slope_per_decade"] == 0.0


def test_index_records_the_last_day_of_data(tmp_path):
    def fetch(lat, lon, start, end, timeout=120):
        payload = december_rain_payload(1981, 12)
        t2m = payload["properties"]["parameter"]["T2M"]
        t2m["19930630"] = -999.0
        for name in ("PRECTOTCORR", "RH2M", "GWETROOT"):
            payload["properties"]["parameter"][name].pop("19930630")
        return payload

    index = run(tmp_path, PLACES[:1], fetch=fetch)
    assert index["data_end"] == "1993-06-29"
    assert {"generated", "source", "period", "cells", "places"} <= set(index)


BAD_PAYLOADS = {
    "empty": {"properties": {"parameter": {}}},
    "no_t2m": {"properties": {"parameter": {"PRECTOTCORR": {"19810101": 0.0}}}},
    "error": {"messages": ["Error: the server could not process the request"],
              "properties": {"parameter": {"PRECTOTCORR": {"19810101": 0.0}, "T2M": {"19810101": 20.0}}}},
}


@pytest.mark.parametrize("name", BAD_PAYLOADS)
def test_a_bad_response_fails_the_cell_and_is_not_cached(tmp_path, name):
    index = run(tmp_path, PLACES[:1], fetch=lambda *a, **k: BAD_PAYLOADS[name])
    assert "error" in index["cells"][0]
    assert not (tmp_path / "cache" / "-14.000_31.875.json").exists()


@pytest.mark.parametrize("name", BAD_PAYLOADS)
def test_a_bad_cached_response_is_fetched_again(tmp_path, name):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "-14.000_31.875.json").write_text(json.dumps(BAD_PAYLOADS[name]))
    calls = []
    index = run(tmp_path, PLACES[:1], calls)
    assert calls == [(-14.0, 31.875)]
    assert "error" not in index["cells"][0]
