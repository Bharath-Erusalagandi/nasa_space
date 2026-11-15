import json

import pytest
from agreement import agreement, load_pairs, read_rows, unknown_conditions
from confusion import confusion

import report


def test_agreement_matches_hand_calculation():
    # differences 2, -1, -1, 4: bias 1.0; SD = sqrt(18/3) = 2.4495; limits 1 +/- 1.96*2.4495
    r = agreement([72, 80, 65, 90], [70, 81, 66, 86], tolerance=3)
    assert r["n"] == 4
    assert r["bias"] == pytest.approx(1.0)
    assert r["sd"] == pytest.approx(2.4495, abs=1e-4)
    assert r["loa_low"] == pytest.approx(-3.8010, abs=1e-4)
    assert r["loa_high"] == pytest.approx(5.8010, abs=1e-4)
    assert r["mae"] == pytest.approx(2.0)
    assert r["within_tolerance"] == pytest.approx(0.75)

def test_rows_with_a_blank_reading_are_excluded_and_counted(tmp_path):
    f = tmp_path / "readings.csv"
    f.write_text("person,condition,reading,device_hr,ref_hr,device_spo2,ref_spo2,note\n"
                 "P01,rest,1,72,70,98,97,\nP01,rest,2,,71,98,98,sensor dropped\nP02,motion,1,95,80,91,98,\n")
    device, ref, excluded = load_pairs(f, "device_hr", "ref_hr", conditions=("rest", "post_exercise"))
    assert (device, ref, excluded) == ([72.0], [70.0], 1)

def test_confusion_counts_recall_and_accuracy():
    true = ["target"] * 3 + ["other"] * 2 + ["noise"] * 3
    pred = ["target", "target", "other", "other", "noise", "noise", "noise", "target"]
    r = confusion(true, pred)
    assert r["recall"] == {"noise": pytest.approx(2 / 3), "other": pytest.approx(0.5), "target": pytest.approx(2 / 3)}
    assert r["accuracy"] == pytest.approx(5 / 8)


PULSE_HEADER = "person,condition,reading,device_hr,ref_hr,device_spo2,ref_spo2,note\n"
MOSQUITO_HEADER = "clip,true_label,distance_cm,predicted_label,confidence\n"
WEATHER_HEADER = "hour_utc,device_temp_c,ref_temp_c,device_rh,ref_rh\n"


def test_agreement_with_a_single_pair_has_no_spread():
    r = agreement([72], [70], tolerance=5)
    assert r["n"] == 1
    assert r["bias"] == pytest.approx(2.0)
    assert r["sd"] is None
    assert r["loa_low"] is None and r["loa_high"] is None
    assert r["mae"] == pytest.approx(2.0)
    assert r["within_tolerance"] == pytest.approx(1.0)


def test_agreement_with_no_pairs_is_an_error():
    with pytest.raises(ValueError):
        agreement([], [], tolerance=5)


def test_limits_with_a_negative_bias():
    # differences -3, -5, -4: bias -4, SD 1, limits -4 +/- 1.96
    r = agreement([95, 94, 93], [98, 99, 97], tolerance=2)
    assert r["bias"] == pytest.approx(-4.0)
    assert r["sd"] == pytest.approx(1.0)
    assert r["loa_low"] == pytest.approx(-5.96)
    assert r["loa_high"] == pytest.approx(-2.04)
    assert r["mae"] == pytest.approx(4.0)
    assert r["within_tolerance"] == pytest.approx(0.0)


def test_within_tolerance_includes_the_boundary():
    r = agreement([75, 65, 76, 98.1], [70, 70, 70, 97.1], tolerance=5)
    assert r["within_tolerance"] == pytest.approx(0.75)
    assert agreement([98.1], [97.1], tolerance=1)["within_tolerance"] == pytest.approx(1.0)


def test_load_pairs_strips_spaces(tmp_path):
    f = tmp_path / "readings.csv"
    f.write_text("person, condition ,reading,device_hr,ref_hr,device_spo2,ref_spo2,note\n"
                 " P01 , rest , 1 , 72 ,  70 ,98,97, \n")
    assert load_pairs(f, "device_hr", "ref_hr", conditions=("rest",)) == ([72.0], [70.0], 0)


def test_load_pairs_excludes_and_counts_a_non_numeric_cell(tmp_path):
    f = tmp_path / "readings.csv"
    f.write_text(PULSE_HEADER + "P01,rest,1,72,70,98,97,\nP01,rest,2,err,71,98,98,\nP01,rest,3,73,n/a,98,98,\n")
    assert load_pairs(f, "device_hr", "ref_hr") == ([72.0], [70.0], 2)


def test_load_pairs_filters_by_condition(tmp_path):
    f = tmp_path / "readings.csv"
    f.write_text(PULSE_HEADER + "P01,rest,1,72,70,98,97,\nP01,post_exercise,1,110,108,97,97,\n"
                 "P01,motion,1,95,,91,98,\nP01,motion,2,99,80,90,98,\n")
    assert load_pairs(f, "device_hr", "ref_hr", conditions=("rest", "post_exercise")) == ([72.0, 110.0], [70.0, 108.0], 0)
    assert load_pairs(f, "device_hr", "ref_hr", conditions=("motion",)) == ([99.0], [80.0], 1)
    assert load_pairs(f, "device_hr", "ref_hr") == ([72.0, 110.0, 99.0], [70.0, 108.0, 80.0], 1)


def test_load_pairs_on_a_missing_or_header_only_file(tmp_path):
    f = tmp_path / "readings.csv"
    assert load_pairs(f, "device_hr", "ref_hr") == ([], [], 0)
    f.write_text(PULSE_HEADER)
    assert load_pairs(f, "device_hr", "ref_hr") == ([], [], 0)


def test_confusion_with_a_label_only_in_the_predictions():
    r = confusion(["target", "target", "noise"], ["target", "Aedes", "noise"])
    assert r["labels"] == ["Aedes", "noise", "target"]
    assert r["matrix"] == [[0, 0, 0], [0, 1, 0], [1, 0, 1]]
    assert r["recall"] == {"noise": pytest.approx(1.0), "target": pytest.approx(0.5)}
    assert "Aedes" not in r["recall"]
    assert r["accuracy"] == pytest.approx(2 / 3)


def write_csvs(root, pulse="", mosquito="", weather=""):
    for sub, name, header, body in (("pulse", "readings.csv", PULSE_HEADER, pulse),
                                    ("mosquito", "trials.csv", MOSQUITO_HEADER, mosquito),
                                    ("weather", "log.csv", WEATHER_HEADER, weather)):
        folder = root / "validation" / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(header + body)


PULSE_ROWS = ("P01,rest,1,72,70,98,97,\n"
              "P01,rest,2,80,81,97,98,\n"
              "P02,post_exercise,1,65,66,99,99,\n"
              "P02,post_exercise,2,90,86,96,99,\n"
              "P02,rest,3,,70,97,97,sensor dropped\n"
              "P01,motion,1,110,75,88,97,finger wiggled\n"
              "P01,motion,2,95,76,,97,no reading\n")
MOSQUITO_ROWS = ("c01,An. arabiensis,5,An. arabiensis,0.9\n"
                 "c02,An. arabiensis,30,Culex,0.6\n"
                 "c03,Culex,5,Culex,0.8\n"
                 "c04,noise,5,noise,0.7\n"
                 "c05,noise,30,An. arabiensis,0.55\n"
                 "c06,Culex,30,Aedes,0.5\n")
WEATHER_ROWS = ("2026-11-15T12:00Z,30.5,30.0,40,42\n"
                "2026-11-15T13:00Z,31.0,31.5,38,41\n"
                "2026-11-15T14:00Z,29.0,27.5,45,44\n")


def test_report_on_small_csvs(tmp_path):
    write_csvs(tmp_path, PULSE_ROWS, MOSQUITO_ROWS, WEATHER_ROWS)
    report.build(tmp_path)

    results = json.loads((tmp_path / "public" / "validation" / "results.json").read_text())
    assert set(results) == {"heart_rate", "spo2", "air_temp_c", "mosquito"}
    assert results["heart_rate"] == {"n": 4, "bias": 1.0, "sd": 2.45, "loa_low": -3.8, "loa_high": 5.8,
                                     "mae": 2.0, "within_tolerance": 1.0, "people": 2}
    # spo2 differences 1, -1, 0, -3, 0: bias -0.6, SD sqrt(9.2/4) = 1.5166
    assert results["spo2"] == {"n": 5, "bias": -0.6, "sd": 1.52, "loa_low": -3.57, "loa_high": 2.37,
                               "mae": 1.0, "within_tolerance": 0.8, "people": 2}
    # temperature differences 0.5, -0.5, 1.5: bias 0.5, SD 1
    assert results["air_temp_c"] == {"n": 3, "bias": 0.5, "sd": 1.0, "loa_low": -1.46, "loa_high": 2.46,
                                     "mae": 0.83, "within_tolerance": 0.67, "people": None}
    assert results["mosquito"] == {
        "labels": ["Aedes", "An. arabiensis", "Culex", "noise"],
        "matrix": [[0, 0, 0, 0], [0, 1, 1, 0], [1, 0, 1, 0], [0, 1, 0, 1]],
        "recall": {"An. arabiensis": 0.5, "Culex": 0.5, "noise": 0.5},
        "accuracy": 0.5,
        "n": 6,
    }

    md = (tmp_path / "validation" / "report" / "REPORT.md").read_text()
    assert "Not tested" not in md
    assert '"bench-compared on 2 adults against a consumer fingertip oximeter"' in md
    assert "| Rows excluded (blank or non-numeric reading) | 1 |" in md
    assert "| 95% limits of agreement | -3.80 to +5.80 bpm |" in md
    assert "| Within team target (+/- 5 bpm) | 100% (4 of 4) |" in md
    assert "| Within team target (+/- 2 points) | 80% (4 of 5) |" in md
    assert "| Within team target (+/- 1 °C) | 67% (2 of 3) |" in md
    assert "Failure case: finger moving" in md
    assert "| P01 | 1 | 110 | 75 | finger wiggled |" in md
    assert "| Bias (device minus reference) | +27.00 bpm |" in md
    assert "not clinically validated" in md
    assert "never tested" in md
    assert "not a medical device" in md
    assert "1 of 2 non-mosquito clips (50%)" in md
    assert "| 5 cm | 3 | 3 | 100% |" in md
    assert "| 30 cm | 0 | 3 | 0% |" in md
    assert '"recognises recorded wingbeats played from a speaker at 5 and 30 cm, 6 clips"' in md
    assert "A speaker is not a live mosquito." in md
    assert "not field accuracy" in md
    assert "NASA POWER" in md
    for kind in ("heart_rate", "spo2", "air_temp_c"):
        assert (tmp_path / "validation" / "report" / "plots" / f"{kind}_bland_altman.png").stat().st_size > 0
        assert f"plots/{kind}_bland_altman.png" in md
    assert not any(ord(c) in (0x2013, 0x2014) for c in md)


def test_report_on_header_only_files(tmp_path):
    write_csvs(tmp_path)
    for path in (tmp_path / "public" / "validation" / "results.json",):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    old_plot = tmp_path / "validation" / "report" / "plots" / "spo2_bland_altman.png"
    old_plot.parent.mkdir(parents=True)
    old_plot.write_bytes(b"x")

    assert report.build(tmp_path) == {}

    md = (tmp_path / "validation" / "report" / "REPORT.md").read_text()
    for heading in ("## Heart rate", "## SpO2", "## Air temperature", "## Mosquito listener"):
        assert f"{heading}\n\nNot tested\n" in md
    assert md.count("Not tested") == 4
    assert json.loads((tmp_path / "public" / "validation" / "results.json").read_text()) == {}
    assert not old_plot.exists()


def test_condition_spellings_are_normalised_and_unknown_ones_counted(tmp_path):
    f = tmp_path / "readings.csv"
    f.write_text(PULSE_HEADER + "P01,post-exercise,1,72,70,98,97,\nP01,Post exercise,2,80,81,97,98,\n"
                 "P01, REST ,3,65,66,99,99,\nP01,walking,4,90,86,96,99,\nP01,,5,90,86,96,99,\n"
                 "P01,motion,6,99,80,90,98,\n")
    assert load_pairs(f, "device_hr", "ref_hr", conditions=("rest", "post_exercise")) == (
        [72.0, 80.0, 65.0], [70.0, 81.0, 66.0], 2)
    assert unknown_conditions(read_rows(f)) == ["", "walking"]


def test_report_lists_unknown_conditions_and_blank_people(tmp_path):
    write_csvs(tmp_path, ",rest,1,72,70,98,97,\n,post-exercise,2,80,81,97,98,\n"
                         "P03,Post exercise,1,90,88,97,97,\nP03,walking,1,95,90,96,97,\nP04,,1,90,91,97,98,\n")
    results = report.build(tmp_path)
    assert results["heart_rate"]["n"] == 3
    assert results["heart_rate"]["people"] == 1
    md = (tmp_path / "validation" / "report" / "REPORT.md").read_text()
    assert "Rows left out because the condition is not rest, post_exercise or motion: 2 (values seen: blank, walking)." in md
    assert "The person was not recorded for 2 of 3 pairs." in md
    assert '"bench-compared on at least 1 adult against a consumer fingertip oximeter"' in md


def test_no_allowed_claim_without_pairs(tmp_path):
    write_csvs(tmp_path, "P01,motion,1,110,75,88,97,\n")
    assert report.build(tmp_path) == {}
    md = (tmp_path / "validation" / "report" / "REPORT.md").read_text()
    assert "No pairs with both readings." in md
    assert "Allowed claim" not in md
    assert json.loads((tmp_path / "public" / "validation" / "results.json").read_text()) == {}
