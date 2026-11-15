# NASA Space Apps 2026 submission

`docs/SUBMISSION.md` is written from `docs/SUBMISSION.template.md` by `python scripts/fill_docs.py`. Edit the template, then run the script. Every number comes from `public/trends/`, `trend/places.json`, `public/map/sources.json` or `docs/validation_results.json`. Lines starting with TODO (team) are for the team to fill in before submitting.

## Project name

Project Astrophage

## High-level project summary

Is the rainy season in eastern Zambia changing, and does that matter for getting malaria medicine to villages before the roads close? Project Astrophage lets you pick a place in Eastern Province and one of nine indicators built from NASA data, see {{n_seasons}} seasons ({{period}}), and read a four-line verdict: what is changing, where, how much, and whether it is statistically significant. After a correction for testing every cell, total wet-season rainfall has a significant trend in {{n_rain_significant}} of {{n_cells}} NASA grid cells, while October temperature is rising significantly in {{n_october_significant}} of them. The number of rainy days falls significantly in {{n_wet_days_significant_decreasing}} cells, and the wettest day of the season gets heavier in {{n_wettest_significant_increasing}}. A village pod sends live pulse and air readings into the same screen, each shown beside its tested error or the words "not yet tested", and a danger-sign check turns a patient's answer into a medicine order and a delivery on real roads.

## Link to project demo

TODO (team): link to the 30-second video or the 7 slides. It must open without a login.

## Link to final project

TODO (team): link to the public repository. It must open without a login.

## Detailed project description

The app is one static page, `/mission/`, with a map and three panels in the order Detect -> Verify -> Act.

SKY tests nine seasonal indicators for the grid cell around the selected place: wet-season rainfall, rainy days, heavy-rain days, wettest day, start of the rains, wet-season temperature, October temperature, wet-season humidity and wet-season soil wetness. Each verdict gives Sen's slope per decade, its 95% range and a two-sided Mann-Kendall p, with the least-squares slope and t-test p beside it for comparison. A record switch reruns the test on the last 10, 20 or 30 seasons, so you can see how a short record changes the answer. The map colours every cell by its trend and outlines a cell only when it stays significant after a Benjamini-Hochberg correction across all {{n_cells}} cells. October temperature rises by {{october_slope_min}} to {{october_slope_max}} °C per decade across the cells (Sen's slope).

GROUND shows pod K-01, read over USB through the browser's Web Serial API: heart rate, SpO2, air temperature and humidity, with the air temperature set against NASA POWER's 1981 to {{end_date}} normal range for today's date. {{validation_summary}}

ACTION applies a short rule-based danger-sign check, creates an order and sends a delivery along a road route computed offline with OSRM from OpenStreetMap, from Chipata to each of the {{n_facilities}} health facilities and the other reference towns. The moving vehicle is labelled as a simulation.

Limits we state on screen and in `docs/METHODS.md`: MERRA-2 is a model reanalysis; a cell value averages about {{cell_km}} km and is not a village measurement; the onset rule is our own simple rule; the pod hardware has not yet been run with this software, and its sensors have not yet been compared with a reference.

## NASA data

NASA POWER daily point API (NASA Langley Research Center), with values from the MERRA-2 reanalysis (NASA GMAO): corrected precipitation (`PRECTOTCORR`), 2 m air temperature (`T2M`), 2 m relative humidity (`RH2M`) and root-zone soil wetness (`GWETROOT`), 1 January 1981 to {{end_date}}, one request per 0.5 x 0.625 degree cell, {{n_cells}} cells. We use it to build nine seasonal indicators, test each one for a trend, and give the normal temperature range that the pod's live air reading is compared with.

The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division. The data was obtained from the POWER Project's Daily 2.10.3 version on 2026/11/14.

NASA GIBS (Global Imagery Browse Services, NASA ESDIS): the map's Satellite ground shows the MODIS Terra corrected reflectance, true colour, picture of 20 August 2025. It is the one thing the page loads from the internet, and only when that ground is chosen. We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), part of NASA's Earth Science Data and Information System (ESDIS).

## Space agency partner and other data

- SerpApi (Google Scholar and Google News search): `trend/evidence.py` searches for published research and news about each indicator's change in Zambia and saves the titles and links, which "How we know" lists under "What others have found". The search runs when the data is built, not when the page is used.

- ECMWF ERA5 reanalysis through the Open-Meteo archive API: daily precipitation and mean 2 m temperature, used as a second source to cross-check the NASA trends in {{n_cross_checked}} of {{n_cells}} cells.
{{other_data}}

## Use of artificial intelligence

Claude (Anthropic), through Claude Code, wrote the code, tests, firmware, CAD scripts and documentation in this repository under the team's direction. Blender made the enclosure renders from the CAD model; they are renders, not AI images. The app makes no AI model calls when it runs. `docs/AI_USE.md` lists each tool, what it did and which files.

## Prior work

This is a new codebase written at the event. It follows the idea of an earlier project by another author: Orbit Health, Philip Mocanu's Cal Hacks 13.0 project (https://devpost.com/software/orbit-health). No code, data or assets from that project are used here.
