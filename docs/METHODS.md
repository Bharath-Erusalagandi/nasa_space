# Methods

Tables between `fill_docs` markers are written by `python scripts/fill_docs.py` from `public/trends/`. Edit the text around them, not the tables.

## The loop

Detect -> Verify -> Act. Detect: we test 45 seasons of NASA POWER data for each grid cell in Eastern Province, Zambia, and show the result in the SKY panel and on the map. Verify: pod K-01 sends live readings over USB, and the GROUND panel shows each one beside its tested error or the words "not yet tested". Act: a rule-based danger-sign check turns a patient's answer into a triage outcome, an order and a delivery along a road route computed offline, shown in the ACTION panel.

## Data

`trend/build_trends.py` sends one request per NASA POWER grid cell to the daily point API (`https://power.larc.nasa.gov/api/temporal/daily/point`, community `AG`). It asks for two parameters: `PRECTOTCORR`, corrected precipitation in mm per day, and `T2M`, mean air temperature at 2 m in °C. POWER takes both from the MERRA-2 reanalysis (NASA GMAO). The request runs from 1 January 1981 to 60 days before the build date, because the newest POWER days are preliminary. Responses are cached in `trend/cache/` and reused, so a second build downloads nothing. Values equal to the response's fill value are dropped.

The places come from `trend/places.json`, which `mapdata/places.py` writes: the five reference towns of the plan, every public health facility in the province from Maina et al. (2019), and one entry for each NASA cell that overlaps the province and holds no town or facility. Each place is assigned to the cell whose centre is nearest on the 0.5 x 0.625 degree grid, and the build makes one request per cell, not per place.

## Seasons

A season runs from 1 July to 30 June and takes the number of the year it starts in, so `1981` is 1981/82. A season is used only when the data reaches its 30 June. The wet season is 1 November to 30 April. A seasonal value is left empty when any day it needs is missing from the data; it is never filled in.

## Indicators

Each season gives one value per indicator. The table is copied from the cell files.

<!-- fill_docs:indicators -->
| Key | Indicator | Unit | Definition |
|---|---|---|---|
| `wet_season_rain_mm` | Wet-season rainfall | mm | Total rain from 1 Nov to 30 Apr. |
| `wet_days` | Rainy days | days | Days from 1 Nov to 30 Apr with at least 1 mm of rain. |
| `heavy_rain_days` | Heavy-rain days | days | Days from 1 Nov to 30 Apr with at least 20 mm of rain. |
| `wettest_day_mm` | Wettest day | mm | Largest one-day rainfall from 1 Nov to 30 Apr. |
| `rain_onset_day` | Start of the rains | days after 1 Oct | Days after 1 Oct until the rain of the last 10 days first adds up to at least 25 mm. |
| `wet_season_temp_c` | Wet-season temperature | °C | Mean air temperature from 1 Nov to 30 Apr. |
| `october_temp_c` | October temperature | °C | Mean air temperature in October, the hottest month. |
<!-- /fill_docs:indicators -->

The start of the rains counts days from 1 October to the first day on which the rain of the last 10 days adds up to at least 25 mm. If that never happens by 30 June, or a day is missing before it happens, the season has no value. We chose this rule for this tool; it is not an agronomic standard.

## Trend tests

`trend/trend_detective.py` runs every test. An indicator needs at least 10 seasons with a value; with fewer, the result is "Not enough seasons to test (need at least 10)" and there is no trend.

- Sen's slope: the median of the slopes between every pair of seasons. We report it per decade (slope per year x 10). The trend line drawn on the chart is `intercept + slope_per_year x season`, where the intercept is the median value minus the slope times the median season.
- 95% range: the confidence interval for Sen's slope from `scipy.stats.theilslopes` with alpha 0.05, per decade.
- Mann-Kendall test: S is the sum of the signs of every later-minus-earlier difference. Its variance includes the correction for tied values. Z uses a continuity correction of 1 toward zero, and p is two-sided from the normal distribution. A trend is called statistically significant when p < 0.05; otherwise the verdict says "not statistically significant".
- Least-squares comparison: the ordinary least-squares slope per decade and its two-sided t-test p from `scipy.stats.linregress`. The screen shows these beside the Sen and Mann-Kendall result; they do not decide the verdict.
- Autocorrelation caution: the engine takes the residuals around the Sen line, computes their lag-1 autocorrelation r, and compares it with the 95% bounds for white noise, (-1 - 1.96 x sqrt(n - 2)) / (n - 1) and (-1 + 1.96 x sqrt(n - 2)) / (n - 1). When r falls outside those bounds, the result carries `autocorrelation_warning` and the screen says neighbouring seasons are correlated, so p may be too small. The engine does not correct p for it.
- Shorter records: for the record switch the build also tests the last 10, 20 and 30 seasons of each series, with the same tests, when the window holds that many seasons and at least 10 values.
- False-discovery correction: for each indicator, the build takes the Mann-Kendall p of every cell and applies the Benjamini-Hochberg procedure (`scipy.stats.false_discovery_control`, method `bh`). The map outlines a cell as significant only when its q < 0.05. The SKY panel reports the cell's own p.

## Findings

One row per indicator across all cells in `public/trends/index.json`.

<!-- fill_docs:findings -->
| Indicator | Significant after correction (q < 0.05) | Of those, up / down | All cells, up / down / flat | p < 0.05 before correction | Sen's slope per decade, lowest to highest |
|---|---|---|---|---|---|
| Wet-season rainfall | 0 of 28 | 0 / 0 | 14 / 14 / 0 | 0 | -42.98 to +47.68 mm |
| Rainy days | 6 of 28 | 1 / 5 | 3 / 24 / 1 | 10 | -5.22 to +2.50 days |
| Heavy-rain days | 0 of 28 | 0 / 0 | 26 / 0 / 2 | 7 | 0.00 to +1.85 days |
| Wettest day | 13 of 28 | 13 / 0 | 28 / 0 / 0 | 16 | +1.11 to +11.65 mm |
| Start of the rains | 0 of 28 | 0 / 0 | 24 / 0 / 4 | 2 | 0.00 to +5.75 days |
| Wet-season temperature | 4 of 28 | 4 / 0 | 28 / 0 / 0 | 8 | +0.04 to +0.20 °C |
| October temperature | 27 of 28 | 27 / 0 | 28 / 0 / 0 | 27 | +0.23 to +0.45 °C |
<!-- /fill_docs:findings -->

Record length changes the answer. The next table counts the cells with Mann-Kendall p < 0.05 when only the last 10, 20 or 30 seasons are tested, against the full record (no correction for multiple tests in this table).

<!-- fill_docs:windows -->
| Indicator | Last 10 seasons | Last 20 seasons | Last 30 seasons | All seasons |
|---|---|---|---|---|
| Wet-season rainfall | 0 of 28 | 6 of 28 | 18 of 28 | 0 of 28 |
| Rainy days | 0 of 28 | 8 of 28 | 21 of 28 | 10 of 28 |
| Heavy-rain days | 0 of 28 | 25 of 28 | 28 of 28 | 7 of 28 |
| Wettest day | 1 of 28 | 17 of 28 | 28 of 28 | 16 of 28 |
| Start of the rains | 1 of 28 | 1 of 28 | 0 of 28 | 2 of 28 |
| Wet-season temperature | 0 of 28 | 4 of 28 | 0 of 28 | 8 of 28 |
| October temperature | 0 of 28 | 0 of 28 | 4 of 28 | 27 of 28 |
<!-- /fill_docs:windows -->

## Grid cells

<!-- fill_docs:grid -->
A NASA POWER cell is 0.5 degrees of latitude by 0.625 degrees of longitude, about 56 x 67 to 68 km across the 28 cells used here.
<!-- /fill_docs:grid -->

Every place in a cell shows that cell's trend, and the screen says the value belongs to the cell, not the village. A health post at the edge of a cell can be closer in climate to the next cell than to its own centre.

## Second-source cross-check

`trend/cross_check.py` downloads daily precipitation and mean 2 m temperature from the ECMWF ERA5 reanalysis through the Open-Meteo archive API for the centre of each cell, over the same dates. It builds the same seven indicators with the same code and runs the same trend test, then stores the result beside the NASA trend as `second_source`. A cell is missing from the cross-check when its Open-Meteo request failed. The ERA5 p values are not corrected for multiple tests.

<!-- fill_docs:cross_check -->
ERA5 trends exist for 28 of the 28 cells.

| Indicator | Cells with both | Same direction as NASA POWER | ERA5 p < 0.05 |
|---|---|---|---|
| Wet-season rainfall | 28 | 15 | 5 |
| Rainy days | 28 | 9 | 0 |
| Heavy-rain days | 28 | 13 | 8 |
| Wettest day | 28 | 25 | 3 |
| Start of the rains | 28 | 19 | 3 |
| Wet-season temperature | 28 | 28 | 12 |
| October temperature | 28 | 28 | 28 |
<!-- /fill_docs:cross_check -->

## The NASA normal beside the live air reading

`trend/normals.py` reads daily `T2M` for the pod's cell from NASA POWER, 1 January 1981 to 60 days before the run. For each calendar day it pools every value within 7 days either side, across all years, and stores the mean, the 10th and 90th percentiles and the count in `public/trends/pod_site.json`. The GROUND panel shows the live air reading against the 10th to 90th percentile band for today's date. The file in this repo is built for the venue, Austin, Texas, because that is where the pod will be during the demo.

## Pod events

The firmware prints one JSON object per line at 115200 baud. The app reads lines through the Web Serial API, turns each line into one event `{pod_id, kind, value, label, unit, quality, at}`, adds `pod_id` `K-01` and the time of arrival as `at`, and passes it to the pod store that the GROUND panel reads.

| Line | Event |
|---|---|
| `{"k":"hr","v":72,"q":0.93}` | `heart_rate`, bpm, quality from `q` |
| `{"k":"spo2","v":98,"q":0.9}` | `spo2`, % |
| `{"k":"temp","v":24.1}` | `air_temp_c`, °C |
| `{"k":"rh","v":41}` | `humidity_pct`, % |
| `{"k":"mosq","label":"An. arabiensis","conf":0.84}` | `mosquito`, label, quality from `conf` |
| `{"k":"dist","v":23.4}` | `distance_cm`, cm (car kit prototype only) |
| `{"k":"light","v":62}` | `light_pct`, % of the 5 V input range (car kit prototype only) |

`lib/pod/parseLine.ts` drops a line before it reaches the screen when it is not a JSON object, when `k` is not one of the seven above, when `v` is missing or not a finite number, when a mosquito line has no label, or when the value cannot be real: heart rate outside 30 to 220, SpO2 outside 70 to 100, air temperature outside -40 to 60, humidity outside 0 to 100. The store counts dropped lines. When no event has arrived for 5 seconds, the GROUND panel shows "pod offline".

## Mosquito models

"Listen for mosquitoes" opens the microphone the browser is given (the pod's microphone is a USB audio input) at 8 kHz with the browser's echo, noise and gain filters off. Every 0.5 s the newest 2.1 s of audio becomes a 128-band log-mel window (2048-point FFT, hop 512, decibels against the window's loudest bin with an 80 dB floor, then standardised within the window). Two small convolutional networks score it in the browser with no library (`lib/pod/mosquitoModel.ts`): a detector (mosquito or not) and a species model for the 8 species of the HumBugDB species task. A mosquito counts as heard when 3 of the last 4 windows pass the detector at 0.5; the species is the mean of the species model over those windows. Tapping a species card plays a held-out HumBugDB recording and scores the file the same way; that result is labelled as a recording, never as a live reading.

Both networks were trained by `models/mosquito/train.py` on HumBugDB (Kiskin et al. 2021). The species classes and the recording split follow the HumBugDB species notebook (Tanzania IHI cup recordings, 75% of recordings for training, seed 42); the detector uses every mosquito and background recording, split the same way. `lib/pod/mosquitoModel.test.ts` checks that the browser features and outputs match PyTorch on test recordings.

<!-- fill_docs:mosquito -->
Held-out test: split by recording, 75% train / 25% test, seed 42. No test recording was used in training or to pick the epoch.

| Model | Test set | Result |
|---|---|---|
| Detector: mosquito or not | 804 recordings, 14581 windows of 2.1 s | ROC AUC 0.991. At 0.5 it finds 95% of mosquito windows and flags 2% of background windows |
| Species: 8 classes | 353 recordings, 8937 windows | Balanced accuracy 55% per recording (mean over its windows), 48% per single window |

Species recall per recording: An. arabiensis 66% of 129, Cx. pipiens complex 71% of 84, Ae. aegypti 77% of 13, An. funestus 89% of 62, An. squamosus 57% of 23, An. coustani 31% of 13, Ma. uniformis 53% of 19, Ma. africanus 0% of 10.

By genus, which is what the conversation acts on: Anopheles 87% of 227, Culex 71% of 84, Aedes 77% of 13, Mansonia 69% of 29 (balanced 76%).

The recording on each species card is the longest test recording of that species the model gets right, so the cards show the model at its best; the figures above are the honest rate.
<!-- /fill_docs:mosquito -->

After a detection, the conversation in GROUND (`lib/mission/chat.ts`, scripted, no language model) asks what that mosquito makes relevant: net use for Anopheles, daytime bites for Aedes, night bites for Culex and Mansonia; fever in the last two days; for Aedes with fever, dengue symptoms; the WHO IMCI general danger signs; and then the disease's warning signs (Zambia's severe malaria signs for Anopheles; WHO dengue warning signs for Aedes with fever; WHO West Nile neurological signs for Culex with fever). Any danger or warning sign refers; a fever without one orders a malaria rapid test, as Zambia's guidelines test every fever.

Replay (`R`, from `public/pod/replay.json`) and the development simulator (`?sim=1`) feed the same store, each with its own source flag and a visible REPLAY or SIMULATION badge.

## Limits

- One dataset. MERRA-2 is a model reanalysis, and reanalysis trends can be affected by changes in the observations fed into it. The ERA5 cross-check above is a second reanalysis, not an independent measurement.
- The 45-season October warming is significant, but the last 20 seasons alone show no significant change (October row of the record-length table), so this record cannot say whether warming continues at the same rate.
- Cell values are averages over a whole grid cell (its size is given under Grid cells), not village measurements. That gap is the reason the pod exists.
- The pod drops any SpO2 reading below 70 as outside the sensor's usable range, so it cannot report severe hypoxaemia. A missing SpO2 on screen does not mean a normal one.
- The onset rule (25 mm in 10 days) is a simple rule chosen for this tool.

## What has not been validated

- The pod hardware has not been run with this software by the authors of this repo. The firmware compiles; the serial path is tested in `lib/pod/serial.test.ts` with a simulated port.
- No pod sensor has been compared with a reference. The CSV files in `validation/` hold only their header rows, so `docs/VALIDATION.md` reports every sensor as not tested and the screen says "not yet tested".
- The mosquito models are tested on held-out HumBugDB recordings only: lab cup and culture recordings from phones, not a laptop or pod microphone in a village. Accuracy through the pod's microphone, at a distance, with room noise, is not known. Two species cards show a photo of a related species because no openly licensed photo of An. squamosus or the African Mansonia species was found; each card says which species its photo shows.
- The conversation's questions and advice have not been reviewed by a clinician.
- The enclosure in `hardware/` is a CAD design with renders. Nobody has printed or assembled it.
- The danger-sign check and the order rules in `lib/mission/` are written for the demo and have not been reviewed by a clinician.
- Road routes come from OSRM on OpenStreetMap roads; travel times are the router's estimates for a car, not measured trips.
