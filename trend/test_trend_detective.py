# written with Claude (Anthropic), see docs/AI_USE.md
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

import trend_detective as td  # noqa: E402

KEYS = ["wet_season_rain_mm", "wet_days", "heavy_rain_days", "wettest_day_mm",
        "rain_onset_day", "wet_season_temp_c", "october_temp_c"]


def days(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def power_payload(start, end, rain=lambda d: 0.0, temp=lambda d: 20.0, fill=-999.0):
    span = days(start, end)
    return {
        "header": {"fill_value": fill},
        "properties": {"parameter": {
            "PRECTOTCORR": {d.strftime("%Y%m%d"): rain(d) for d in span},
            "T2M": {d.strftime("%Y%m%d"): temp(d) for d in span},
        }},
    }


def december_rain_payload(start_year, seasons):
    def rain(d):
        return float(d.year - start_year + 1) if d.month == 12 else 0.0
    return power_payload(date(start_year, 7, 1), date(start_year + seasons, 6, 30), rain=rain)


def one_season(season=2000, rain=lambda d: 0.0, temp=lambda d: 20.0):
    span = days(date(season, 7, 1), date(season + 1, 6, 30))
    return {d: rain(d) for d in span}, {d: temp(d) for d in span}


def value(series, key, season=2000):
    return next(r["value"] for r in series[key] if r["season"] == season)


def fake_trend(slope, low, high, p, alpha=0.05):
    return {"slope_per_decade": slope, "ci_low_per_decade": low, "ci_high_per_decade": high, "mk_p": p,
            "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat",
            "significant": p < alpha}


# Mann-Kendall

def test_mk_short_monotonic_series():
    s, z, p = td.mann_kendall([1, 2, 3, 4, 5])
    assert s == 10
    assert z == pytest.approx(9 / math.sqrt(5 * 4 * 15 / 18))
    assert p == pytest.approx(0.0275, abs=1e-4)
    assert td.mann_kendall([5, 4, 3, 2, 1])[:2] == (-10, pytest.approx(-z))


def test_mk_ties_reduce_the_variance():
    s, z, p = td.mann_kendall([1, 2, 2, 3])
    assert s == 5
    assert z == pytest.approx(4 / math.sqrt((4 * 3 * 13 - 2 * 1 * 9) / 18))
    assert p == pytest.approx(2 * stats.norm.sf(z))


def test_mk_constant_series():
    assert td.mann_kendall([3, 3, 3, 3, 3]) == (0, 0.0, 1.0)


def test_mk_zero_s_gives_p_one():
    s, z, p = td.mann_kendall([1, 3, 3, 1])
    assert (s, z, p) == (0, 0.0, 1.0)


def test_trend_reports_mann_kendall_fields():
    t = td.trend(range(2000, 2010), range(10))
    assert t["mk_s"] == 45
    assert t["mk_z"] == pytest.approx(44 / math.sqrt(125))
    assert t["mk_p"] == pytest.approx(2 * stats.norm.sf(44 / math.sqrt(125)))
    assert t["significant"] and t["direction"] == "increasing"


# Sen slope, range and intercept

def test_sen_slope_on_exact_line():
    years = list(range(1990, 2000))
    t = td.trend(years, [2 * y + 5 for y in years])
    assert t["slope_per_year"] == pytest.approx(2.0)
    assert t["slope_per_decade"] == pytest.approx(20.0)
    assert t["ci_low_per_decade"] == pytest.approx(20.0)
    assert t["ci_high_per_decade"] == pytest.approx(20.0)
    down = td.trend(years, [10 - 0.5 * (y - 1990) for y in years])
    assert down["slope_per_decade"] == pytest.approx(-5.0)
    assert down["direction"] == "decreasing"


def test_sen_slope_ignores_one_outlier():
    years = list(range(2000, 2011))
    values = [float(y - 2000) for y in years]
    values[9] += 100
    t = td.trend(years, values)
    assert t["slope_per_decade"] == pytest.approx(10.0)
    assert t["ci_low_per_decade"] <= 10.0 <= t["ci_high_per_decade"]
    assert t["ols_slope_per_decade"] != pytest.approx(10.0)


def test_sen_range_is_the_rank_based_interval():
    rng = np.random.default_rng(7)
    years = np.arange(1981, 2026)
    values = 0.03 * years + rng.normal(0, 0.4, len(years))
    t = td.trend(years, values)
    ref = stats.theilslopes(values, years, alpha=0.95)
    assert t["slope_per_year"] == pytest.approx(ref.slope)
    assert t["ci_low_per_decade"] == pytest.approx(ref.low_slope * 10)
    assert t["ci_high_per_decade"] == pytest.approx(ref.high_slope * 10)


def test_intercept_rule():
    years = list(range(1981, 1993))
    values = [5, 7, 6, 9, 8, 11, 10, 12, 15, 13, 14, 17]
    t = td.trend(years, values)
    assert t["intercept"] == pytest.approx(np.median(values) - t["slope_per_year"] * np.median(years))
    years = list(range(2000, 2012))
    line = td.trend(years, [3.0 * (y - 2000) for y in years])
    assert line["intercept"] == pytest.approx(-6000.0)
    assert line["intercept"] + line["slope_per_year"] * 2005 == pytest.approx(15.0)


# least squares

def test_least_squares_on_exact_line():
    years = list(range(1990, 2000))
    t = td.trend(years, [2 * y for y in years])
    assert t["ols_slope_per_decade"] == pytest.approx(20.0)
    assert t["ols_p"] < 1e-10


def test_least_squares_matches_hand_formula():
    years = np.arange(10, dtype=float)
    values = np.array([3, 1, 4, 1, 5, 9, 2, 6, 5, 3], dtype=float)
    t = td.trend(years, values)
    b, a = np.polyfit(years, values, 1)
    resid = values - (a + b * years)
    se = math.sqrt(resid @ resid / 8) / math.sqrt(((years - years.mean()) ** 2).sum())
    assert t["ols_slope_per_decade"] == pytest.approx(10 * b)
    assert t["ols_p"] == pytest.approx(2 * stats.t.sf(abs(b / se), 8))


# autocorrelation caution

def test_autocorrelation_bounds():
    low, high = td.autocorrelation_bounds(12)
    assert low == pytest.approx((-1 - 1.96 * math.sqrt(10)) / 11)
    assert high == pytest.approx((-1 + 1.96 * math.sqrt(10)) / 11)


def test_alternating_residuals_are_flagged():
    years = list(range(1990, 2010))
    t = td.trend(years, [y + (-1) ** y for y in years])
    assert t["lag1_autocorrelation"] < -0.8
    assert t["autocorrelation_warning"]


def test_slow_wave_residuals_are_flagged():
    years = list(range(1981, 2021))
    t = td.trend(years, [math.sin(2 * math.pi * (y - 1981) / 20) for y in years])
    assert t["lag1_autocorrelation"] > 0.8
    assert t["autocorrelation_warning"]


def test_exact_line_is_not_flagged():
    years = list(range(1990, 2005))
    t = td.trend(years, [3 * y for y in years])
    assert t["lag1_autocorrelation"] == 0.0
    assert not t["autocorrelation_warning"]


# fewer than 10 values and None handling

def test_fewer_than_ten_values_raise():
    with pytest.raises(ValueError):
        td.trend(range(9), range(9))


def test_none_values_count_against_the_minimum():
    with pytest.raises(ValueError):
        td.trend(range(12), [1, None, 2, 3, None, 4, 5, None, 6, 7, 8, 9])


def test_none_values_are_dropped():
    years = list(range(2000, 2012))
    values = [float(i) for i in range(12)]
    values[3] = values[8] = None
    t = td.trend(years, values)
    kept = [(y, v) for y, v in zip(years, values) if v is not None]
    assert t["n"] == 10
    assert t["mk_s"] == td.trend([y for y, _ in kept], [v for _, v in kept])["mk_s"] == 45


def test_constant_series_is_flat():
    t = td.trend(range(2000, 2015), [4.0] * 15)
    assert t["slope_per_decade"] == 0.0
    assert t["direction"] == "flat"
    assert not t["significant"]
    assert t["mk_p"] == 1.0 and t["ols_p"] == 1.0


def test_alpha_is_used_and_reported():
    years = list(range(2000, 2012))
    values = [1, 3, 2, 4, 3, 5, 3, 6, 4, 5, 7, 5]
    p = td.trend(years, values)["mk_p"]
    assert 0.001 < p < 0.05
    loose, strict = td.trend(years, values), td.trend(years, values, alpha=0.001)
    assert loose["significant"] and not strict["significant"]
    assert strict["alpha"] == 0.001


# parse_power

def test_parse_power_drops_the_fill_value():
    payload = power_payload(date(2000, 1, 1), date(2000, 1, 3), rain=lambda d: 2.5)
    payload["properties"]["parameter"]["PRECTOTCORR"]["20000102"] = -999.0
    data = td.parse_power(payload)
    assert data["PRECTOTCORR"] == {date(2000, 1, 1): 2.5, date(2000, 1, 3): 2.5}
    assert data["T2M"][date(2000, 1, 2)] == 20.0


def test_parse_power_reads_the_header_fill_value():
    payload = power_payload(date(2000, 1, 1), date(2000, 1, 2), fill=-99.0)
    payload["properties"]["parameter"]["T2M"]["20000101"] = -99.0
    payload["properties"]["parameter"]["PRECTOTCORR"]["20000101"] = -999.0
    data = td.parse_power(payload)
    assert list(data["T2M"]) == [date(2000, 1, 2)]
    assert data["PRECTOTCORR"][date(2000, 1, 1)] == -999.0


# default_end

@pytest.mark.parametrize("today, end", [
    (date(2026, 11, 14), date(2026, 9, 15)),
    (date(2024, 3, 1), date(2024, 1, 1)),
])
def test_default_end_is_sixty_days_back(today, end):
    assert td.default_end(today) == end


# seasons

@pytest.mark.parametrize("season, label", [(1981, "1981/82"), (1999, "1999/00"), (2009, "2009/10")])
def test_season_labels(season, label):
    assert td.season_label(season) == label


def test_only_complete_seasons_are_kept():
    data = td.parse_power(power_payload(date(1981, 1, 1), date(2026, 9, 15)))
    series = td.seasonal_indicators(data["PRECTOTCORR"], data["T2M"])
    seasons = [r["season"] for r in series["wet_season_rain_mm"]]
    assert seasons == list(range(1981, 2026))
    assert series["october_temp_c"][0]["label"] == "1981/82"
    rain, _ = one_season(1990)
    assert [r["season"] for r in td.seasonal_indicators(rain)["wet_days"]] == [1990]
    rain.pop(date(1990, 7, 1))
    assert td.seasonal_indicators(rain)["wet_days"] == []


def test_wet_season_boundaries():
    edges = {date(2000, 10, 31): 100.0, date(2000, 11, 1): 1.0, date(2001, 4, 30): 2.0, date(2001, 5, 1): 100.0}
    rain, temp = one_season(2000, rain=lambda d: edges.get(d, 0.0))
    series = td.seasonal_indicators(rain, temp)
    assert value(series, "wet_season_rain_mm") == 3.0
    assert value(series, "wet_days") == 2


def test_leap_year_wet_season_has_182_days():
    rain, temp = one_season(2023, rain=lambda d: 1.0)
    assert value(td.seasonal_indicators(rain, temp), "wet_days", 2023) == 182
    rain, temp = one_season(2022, rain=lambda d: 1.0)
    assert value(td.seasonal_indicators(rain, temp), "wet_days", 2022) == 181


# the seven indicators

def test_wet_season_rain_total():
    rain, temp = one_season(rain=lambda d: 2.0 if d.month in (11, 12, 1, 2, 3, 4) else 50.0)
    assert value(td.seasonal_indicators(rain, temp), "wet_season_rain_mm") == pytest.approx(2.0 * 181)


def test_rainy_days_threshold_is_at_least_1_mm():
    rain, temp = one_season(rain=lambda d: {1: 1.0, 2: 0.99, 3: 5.0}.get(d.day, 0.0) if d.month == 1 else 0.0)
    assert value(td.seasonal_indicators(rain, temp), "wet_days") == 2


def test_heavy_rain_days_threshold_is_at_least_20_mm():
    rain, temp = one_season(rain=lambda d: {1: 20.0, 2: 19.9, 3: 45.0}.get(d.day, 0.0) if d.month == 2 else 0.0)
    assert value(td.seasonal_indicators(rain, temp), "heavy_rain_days") == 2


def test_wettest_day_is_the_wet_season_maximum():
    rain, temp = one_season(rain=lambda d: {date(2001, 1, 9): 63.5, date(2001, 6, 1): 90.0}.get(d, 3.0))
    assert value(td.seasonal_indicators(rain, temp), "wettest_day_mm") == 63.5


def test_wet_season_temperature_mean():
    rain, temp = one_season(temp=lambda d: 24.0 if d.month in (11, 12, 1) else 20.0 if d.month in (2, 3, 4) else 30.0)
    expected = (24.0 * (30 + 31 + 31) + 20.0 * (28 + 31 + 30)) / 181
    assert value(td.seasonal_indicators(rain, temp), "wet_season_temp_c") == pytest.approx(expected, abs=1e-4)


def test_october_temperature_is_the_start_year_october():
    rain, temp = one_season(temp=lambda d: 26.0 + (d.day % 2) if d.month == 10 else 15.0)
    assert value(td.seasonal_indicators(rain, temp), "october_temp_c") == pytest.approx(26.0 + 16 / 31, abs=1e-4)


def test_onset_counts_days_after_1_october():
    rain, temp = one_season(rain=lambda d: 2.5 if d >= date(2000, 10, 1) else 0.0)
    assert value(td.seasonal_indicators(rain, temp), "rain_onset_day") == 9


@pytest.mark.parametrize("amount, onset", [(25.0, 19), (24.99, None)])
def test_onset_threshold_is_inclusive(amount, onset):
    rain, temp = one_season(rain=lambda d: amount if d == date(2000, 10, 20) else 0.0)
    assert value(td.seasonal_indicators(rain, temp), "rain_onset_day") == onset


def test_onset_needs_the_rain_within_10_days():
    falls = {date(2000, 10, 3): 15.0, date(2000, 10, 13): 10.0, date(2000, 10, 22): 15.0}
    rain, temp = one_season(rain=lambda d: falls.get(d, 0.0))
    assert value(td.seasonal_indicators(rain, temp), "rain_onset_day") == 21


def test_onset_ignores_september_rain():
    falls = {date(2000, 9, 28): 20.0, date(2000, 10, 2): 6.0, date(2000, 10, 5): 20.0}
    rain, temp = one_season(rain=lambda d: falls.get(d, 0.0))
    assert value(td.seasonal_indicators(rain, temp), "rain_onset_day") == 4


def test_missing_days_give_none_only_where_needed():
    rain, temp = one_season(rain=lambda d: 3.0)
    rain.pop(date(2001, 2, 10))
    series = td.seasonal_indicators(rain, temp)
    assert value(series, "wet_season_rain_mm") is None
    assert value(series, "wettest_day_mm") is None
    assert value(series, "rain_onset_day") == 8
    assert value(series, "october_temp_c") == 20.0
    no_temp = td.seasonal_indicators(rain)
    assert value(no_temp, "wet_season_temp_c") is None and value(no_temp, "october_temp_c") is None


# analyse

def test_december_rain_payload_gives_310_mm_per_decade():
    result = td.analyse(december_rain_payload(1981, 12), "Test", -14.0, 31.875)
    rain = result["indicators"]["wet_season_rain_mm"]
    assert [r["value"] for r in rain["series"]] == [31.0 * (i + 1) for i in range(12)]
    assert rain["trend"]["slope_per_decade"] == pytest.approx(310.0)


def test_analyse_shape_and_period():
    result = td.analyse(december_rain_payload(1981, 12), "Katete", -14.06, 32.04)
    assert set(result) == {"place", "lat", "lon", "source", "period", "indicators"}
    assert (result["place"], result["lat"], result["lon"]) == ("Katete", -14.06, 32.04)
    assert result["period"] == "1981/82 to 1992/93"
    assert list(result["indicators"]) == KEYS
    assert all(w in result["source"] for w in ("NASA POWER", "MERRA-2", "PRECTOTCORR", "T2M"))
    for ind in result["indicators"].values():
        assert set(ind) == {"label", "unit", "definition", "series", "trend", "verdict"}
    assert result["indicators"]["october_temp_c"]["unit"] == "deg C"


def test_analyse_with_nine_seasons_has_no_trend():
    result = td.analyse(december_rain_payload(2000, 9), "Short")
    for ind in result["indicators"].values():
        assert ind["trend"] is None
        assert ind["verdict"] == "Not enough seasons to test (need at least 10)."


# verdicts

@pytest.mark.parametrize("t, unit, text", [
    (fake_trend(0.3612, 0.1104, 0.5822, 0.0071), "deg C",
     "Increasing by 0.36 deg C per decade (95% range 0.11 to 0.58); Mann-Kendall p = 0.007: statistically significant."),
    (fake_trend(-1.5, -4.2, 1.1, 0.294), "days",
     "Decreasing by 1.50 days per decade (95% range -4.20 to 1.10); Mann-Kendall p = 0.294: not statistically significant."),
    (fake_trend(0.42, 0.25, 0.6, 0.0002), "deg C",
     "Increasing by 0.42 deg C per decade (95% range 0.25 to 0.60); Mann-Kendall p < 0.001: statistically significant."),
    (fake_trend(0.0, -2.0, 1.5, 1.0), "days",
     "No change (0.00 days per decade; 95% range -2.00 to 1.50); Mann-Kendall p = 1.000: not statistically significant."),
    (None, "mm", "Not enough seasons to test (need at least 10)."),
])
def test_verdict_wording(t, unit, text):
    assert td.verdict(t, unit) == text
