# written with Claude (Anthropic), see docs/AI_USE.md
import json
from datetime import date, timedelta
import pytest
from normals import normals_by_day
import normals as nm

def test_normal_for_one_calendar_day_across_years():
    # 14 Nov of 2000..2009 holds 0..9: mean 4.5, 10th percentile 0.9, 90th percentile 8.1
    temp = {date(2000 + i, 11, 14): float(i) for i in range(10)}
    n = normals_by_day(temp, half_window=0)["11-14"]
    assert n["n"] == 10
    assert n["mean"] == pytest.approx(4.5)
    assert n["p10"] == pytest.approx(0.9)
    assert n["p90"] == pytest.approx(8.1)

def test_window_pulls_in_neighbouring_days():
    temp = {date(2000 + i, 11, d): float(i) for i in range(10) for d in (13, 14, 15)}
    assert normals_by_day(temp, half_window=1)["11-14"]["n"] == 30


def test_29_february_uses_every_year():
    temp = {}
    for year in range(2000, 2009):
        temp[date(year, 2, 28)] = 1.0
        temp[date(year, 3, 1)] = 3.0
        if year % 4 == 0:
            temp[date(year, 2, 29)] = 2.0
    # with no window only the three leap days count; with a window of 1 each other year adds 28 Feb and 1 Mar
    assert normals_by_day(temp, half_window=0)["02-29"]["n"] == 3
    n = normals_by_day(temp, half_window=1)["02-29"]
    assert n["n"] == 3 * 3 + 6 * 2
    assert n["mean"] == pytest.approx(2.0)


def test_29_february_window_in_a_common_year():
    temp = {date(2001, 2, 28) - timedelta(days=i): 1.0 for i in range(8)}
    temp |= {date(2001, 3, 1) + timedelta(days=i): 1.0 for i in range(8)}
    # 22 Feb to 7 Mar lie within 7 days of the point between 28 Feb and 1 Mar
    assert normals_by_day(temp, half_window=7)["02-29"]["n"] == 14


def test_window_wraps_the_year_end():
    temp = {date(2000, 12, 31): 1.0, date(2001, 1, 1): 2.0, date(2001, 1, 2): 3.0, date(2001, 12, 31): 4.0}
    jan1 = normals_by_day(temp, half_window=1)["01-01"]
    # 1 Jan 2001 takes 31 Dec 2000, 1 Jan and 2 Jan; 1 Jan 2002 takes 31 Dec 2001
    assert jan1["n"] == 4
    assert jan1["mean"] == pytest.approx(2.5)
    dec31 = normals_by_day(temp, half_window=1)["12-31"]
    assert dec31["n"] == 3
    assert dec31["mean"] == pytest.approx((1.0 + 2.0 + 4.0) / 3)


def test_every_calendar_day_has_a_key_in_order():
    out = normals_by_day({date(2001, 6, 1): 20.0}, half_window=0)
    assert len(out) == 366
    assert list(out)[:2] == ["01-01", "01-02"] and list(out)[-1] == "12-31"
    assert out["06-02"] == {"mean": None, "p10": None, "p90": None, "n": 0}


def power_t2m_payload(start, end, temp):
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    t2m = {d.strftime("%Y%m%d"): temp(d) for d in days}
    rain = {d.strftime("%Y%m%d"): 0.0 for d in days}
    return {"header": {"fill_value": -999}, "properties": {"parameter": {"T2M": t2m, "PRECTOTCORR": rain}}}


def test_command_line_writes_the_pod_site_file(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(lat, lon, start, end, timeout=120):
        calls.append((lat, lon, start, end))
        return power_t2m_payload(date(2000, 1, 1), date(2003, 12, 31), lambda d: 20.0 + d.month / 3)

    monkeypatch.setattr(nm, "fetch_power", fake_fetch)
    out = tmp_path / "pod_site.json"
    args = ["--lat", "-14.06", "--lon", "32.04", "--name", "Test pod", "--out", str(out),
            "--cache", str(tmp_path / "cache")]
    nm.main(args)
    data = json.loads(out.read_text())
    assert set(data) == {"place", "cell", "lat", "lon", "source", "period", "half_window", "normals"}
    assert data["place"] == "Test pod"
    assert data["cell"] == "-14.000_31.875"
    assert (data["lat"], data["lon"]) == (-14.06, 32.04)
    assert data["half_window"] == 7
    assert data["period"] == "2000-01-01 to 2003-12-31"
    assert len(data["normals"]) == 366
    day = data["normals"]["07-15"]
    assert day["n"] == 4 * 15
    assert day["mean"] == round(day["mean"], 2) and day["p10"] == round(day["p10"], 2)
    assert calls[0][2] == date(1981, 1, 1)

    nm.main(args)
    assert len(calls) == 1
