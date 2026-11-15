import io
import json
import urllib.error
from datetime import date, timedelta
import pytest
import cross_check as cc
from cross_check import parse_open_meteo


def open_meteo_payload(start, end, rain, temp):
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    return {"daily": {"time": [d.isoformat() for d in days],
                      "precipitation_sum": [rain(d) for d in days],
                      "temperature_2m_mean": [temp(d) for d in days]}}


def test_parse_open_meteo_drops_null_rain():
    payload = {"daily": {"time": ["2000-11-01", "2000-11-02", "2000-11-03"],
                         "precipitation_sum": [1.5, None, 0.0],
                         "temperature_2m_mean": [24.1, 23.0, 22.5]}}
    out = parse_open_meteo(payload)
    assert out["PRECTOTCORR"] == {date(2000, 11, 1): 1.5, date(2000, 11, 3): 0.0}
    assert out["T2M"] == {date(2000, 11, 1): 24.1, date(2000, 11, 2): 23.0, date(2000, 11, 3): 22.5}


def test_parse_open_meteo_drops_null_temperature():
    payload = {"daily": {"time": ["2000-11-01", "2000-11-02"],
                         "precipitation_sum": [0.0, 2.0],
                         "temperature_2m_mean": [None, 21.0]}}
    out = parse_open_meteo(payload)
    assert len(out["PRECTOTCORR"]) == 2
    assert out["T2M"] == {date(2000, 11, 2): 21.0}


def test_parse_open_meteo_empty_payload():
    assert parse_open_meteo({}) == {"PRECTOTCORR": {}, "T2M": {}}
    assert parse_open_meteo({"daily": {}}) == {"PRECTOTCORR": {}, "T2M": {}}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_asks_for_era5_and_retries_once_after_429(monkeypatch):
    urls, waits = [], []

    def fake_urlopen(url, timeout):
        urls.append(url)
        if len(urls) == 1:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        return Response(json.dumps({"daily": {"time": []}}).encode())

    monkeypatch.setattr(cc.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(cc.time, "sleep", waits.append)
    payload = cc.fetch_open_meteo(-14.0, 31.875, date(1981, 1, 1), date(2026, 9, 15))
    assert payload == {"daily": {"time": []}}
    assert waits == [61]
    assert len(urls) == 2
    url = urls[0]
    assert url.startswith("https://archive-api.open-meteo.com/v1/archive?")
    for part in ("latitude=-14.0", "longitude=31.875", "start_date=1981-01-01", "end_date=2026-09-15",
                 "daily=precipitation_sum%2Ctemperature_2m_mean", "timezone=UTC", "models=era5"):
        assert part in url


def test_fetch_gives_up_after_a_second_429(monkeypatch):
    def fake_urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(cc.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(cc.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        cc.fetch_open_meteo(-14.0, 31.875, date(1981, 1, 1), date(2026, 9, 15))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def cell_file(cid):
    indicators = {key: {"label": key, "trend": None} for key in cc.INDICATORS}
    return {"place": cid, "indicators": indicators, "cell": {"id": cid}}


def trends_dir(tmp_path):
    out = tmp_path / "trends"
    index = {"cells": [{"id": "a", "lat": -14.0, "lon": 31.875},
                       {"id": "b", "lat": -13.5, "lon": 32.5},
                       {"id": "c", "lat": -12.5, "lon": 33.125, "error": "failed"}],
             "places": []}
    write(out / "index.json", index)
    write(out / "cells" / "a.json", cell_file("a"))
    write(out / "cells" / "b.json", cell_file("b"))
    return out, index


def warming_payload(start, end):
    # october warms by 0.1 deg C per year, every december day has 2 mm of rain
    return open_meteo_payload(start, end,
                              rain=lambda d: 2.0 if d.month == 12 else 0.0,
                              temp=lambda d: 20.0 + 0.1 * (d.year - 2000) if d.month == 10 else 20.0)


def test_cross_check_adds_second_source_and_skips_failed_cells(tmp_path, capsys):
    out, index = trends_dir(tmp_path)
    asked = []

    def fake_fetch(lat, lon, start, end, timeout=120):
        asked.append((lat, lon))
        if lat == -13.5:
            raise OSError("network down")
        return warming_payload(date(2000, 1, 1), date(2015, 12, 31))

    failed = cc.cross_check(out, tmp_path / "cache", fetch=fake_fetch, pause=0, today=date(2026, 11, 14))
    assert asked == [(-14.0, 31.875), (-13.5, 32.5)]
    assert failed == ["b"]
    a = json.loads((out / "cells" / "a.json").read_text())
    second = a["indicators"]["october_temp_c"]["second_source"]
    assert second["name"] == "ECMWF ERA5 via Open-Meteo"
    assert second["trend"]["slope_per_decade"] == pytest.approx(1.0)
    assert second["trend"]["direction"] == "increasing"
    assert a["indicators"]["wet_season_rain_mm"]["second_source"]["trend"]["direction"] == "flat"
    assert set(a["indicators"]) == set(cc.INDICATORS)
    # humidity and soil wetness come from NASA only; ERA5 rain and temperature cannot check them
    assert all(("second_source" in v) == (k not in cc.NASA_ONLY) for k, v in a["indicators"].items())
    assert "second_source" not in json.loads((out / "cells" / "b.json").read_text())["indicators"]["october_temp_c"]
    assert json.loads((out / "index.json").read_text()) == index
    assert "b" in capsys.readouterr().out

    cc.cross_check(out, tmp_path / "cache", fetch=fake_fetch, pause=0, today=date(2026, 11, 14))
    assert asked.count((-14.0, 31.875)) == 1


def test_short_record_gives_a_null_second_source_trend(tmp_path):
    out, _ = trends_dir(tmp_path)

    def fake_fetch(lat, lon, start, end, timeout=120):
        return warming_payload(date(2000, 1, 1), date(2005, 12, 31))

    assert cc.cross_check(out, tmp_path / "cache", fetch=fake_fetch, pause=0) == []
    a = json.loads((out / "cells" / "a.json").read_text())
    assert a["indicators"]["october_temp_c"]["second_source"] == {"name": "ECMWF ERA5 via Open-Meteo", "trend": None}


def test_fetch_is_asked_for_1981_to_the_default_end(tmp_path):
    out, _ = trends_dir(tmp_path)
    spans = []

    def fake_fetch(lat, lon, start, end, timeout=120):
        spans.append((start, end))
        return warming_payload(date(2000, 1, 1), date(2015, 12, 31))

    cc.cross_check(out, tmp_path / "cache", fetch=fake_fetch, pause=0, today=date(2026, 11, 14))
    assert spans[0] == (date(1981, 1, 1), date(2026, 9, 15))
