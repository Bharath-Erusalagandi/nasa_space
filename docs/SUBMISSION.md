# NASA Space Apps 2026 submission

`docs/SUBMISSION.md` is written from `docs/SUBMISSION.template.md` by `python scripts/fill_docs.py`. Edit the template, then run the script. Every number comes from `public/trends/`, `trend/places.json`, `public/map/sources.json` or `docs/validation_results.json`. Lines starting with TODO (team) are for the team to fill in before submitting.

## Project name

Orbit Health: Trend Detective

## High-level project summary

Is the rainy season in eastern Zambia changing, and does that matter for getting malaria medicine to villages before the roads close? Orbit Health lets you pick a place in Eastern Province and one of seven indicators built from NASA data, see 45 seasons (1981/82 to 2025/26), and read a four-line verdict: what is changing, where, how much, and whether it is statistically significant. After a correction for testing every cell, total wet-season rainfall has a significant trend in 0 of 28 NASA grid cells, while October temperature is rising significantly in 27 of them. The number of rainy days falls significantly in 5 cells, and the wettest day of the season gets heavier in 13. A village pod sends live pulse and air readings into the same screen, each shown beside its tested error or the words "not yet tested", and a danger-sign check turns a patient's answer into a medicine order and a delivery on real roads.

## Link to project demo

TODO (team): link to the 30-second video or the 7 slides. It must open without a login.

## Link to final project

TODO (team): link to the public repository. It must open without a login.

## Detailed project description

The app is one static page, `/mission/`, with a map and three panels in the order Detect -> Verify -> Act.

SKY tests seven seasonal indicators for the grid cell around the selected place: wet-season rainfall, rainy days, heavy-rain days, wettest day, start of the rains, wet-season temperature and October temperature. Each verdict gives Sen's slope per decade, its 95% range and a two-sided Mann-Kendall p, with the least-squares slope and t-test p beside it for comparison. A record switch reruns the test on the last 10, 20 or 30 seasons, so you can see how a short record changes the answer. The map colours every cell by its trend and outlines a cell only when it stays significant after a Benjamini-Hochberg correction across all 28 cells. October temperature rises by 0.23 to 0.45 °C per decade across the cells (Sen's slope).

GROUND shows pod K-01, read over USB through the browser's Web Serial API: heart rate, SpO2, air temperature and humidity, with the air temperature set against NASA POWER's 1981 to 2026-09-15 normal range for today's date. The validation CSV files in `validation/` hold no rows yet, so no pod sensor error has been measured and every reading on screen says "not yet tested".

ACTION applies a short rule-based danger-sign check, creates an order and sends a delivery along a road route computed offline with OSRM from OpenStreetMap, from Chipata to each of the 144 health facilities and the other reference towns. The moving vehicle is labelled as a simulation.

Limits we state on screen and in `docs/METHODS.md`: MERRA-2 is a model reanalysis; a cell value averages about 56 x 67 to 68 km and is not a village measurement; the onset rule is our own simple rule; the pod hardware has not yet been run with this software, and its sensors have not yet been compared with a reference.

## NASA data

NASA POWER daily point API (NASA Langley Research Center), with values from the MERRA-2 reanalysis (NASA GMAO): corrected precipitation (`PRECTOTCORR`) and 2 m air temperature (`T2M`), 1 January 1981 to 2026-09-15, one request per 0.5 x 0.625 degree cell, 28 cells. We use it to build seven seasonal indicators, test each one for a trend, and give the normal temperature range that the pod's live air reading is compared with.

TODO (team): paste the acknowledgement sentence that NASA POWER asks users to include. `docs/REFERENCES.md` gives the sentence and its source.

## Space agency partner and other data

- ECMWF ERA5 reanalysis through the Open-Meteo archive API: daily precipitation and mean 2 m temperature, used as a second source to cross-check the NASA trends in 28 of 28 cells.
- geoBoundaries Zambia ADM1 (Zambia Data Hub), Creative Commons Attribution 4.0 International (CC BY 4.0), used for province outline. https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ZMB/ADM1/geoBoundaries-ZMB-ADM1.geojson
- geoBoundaries Zambia ADM2 (GRID3, Office of the Surveyor General), Creative Commons Attribution 4.0 (CC BY 4.0), used for district outlines and facility districts. https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ZMB/ADM2/geoBoundaries-ZMB-ADM2.geojson
- Natural Earth 1:10m admin 0 boundary lines, Public domain (Natural Earth terms of use), used for international borders. https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_land.zip
- Natural Earth 1:10m admin 0 countries, Public domain (Natural Earth terms of use), used for country names and label points. https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip
- Public health facilities in sub Saharan Africa (Maina et al. 2019, Scientific Data, doi:10.1038/s41597-019-0142-2), CC0 (https://creativecommons.org/publicdomain/zero/1.0/), used for health facility names, types and locations. https://doi.org/10.6084/m9.figshare.7725374.v1
- OpenStreetMap Zambia extract (Geofabrik), Open Database License 1.0 (ODbL), (c) OpenStreetMap contributors, used for roads, rivers, towns and road routing (OSRM). https://download.geofabrik.de/africa/zambia-latest.osm.pbf
- Copernicus DEM GLO-90 (AWS Open Data, copernicus-dem-90m), Copernicus DEM GLO-90, free licence; produced using Copernicus WorldDEM-90 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved, used for hillshade relief (49 tiles). https://copernicus-dem-90m.s3.amazonaws.com

## Use of artificial intelligence

Claude (Anthropic), through Claude Code, wrote the code, tests, firmware, CAD scripts and documentation in this repository under the team's direction. Blender made the enclosure renders from the CAD model; they are renders, not AI images. The app makes no AI model calls when it runs. `docs/AI_USE.md` lists each tool, what it did and which files.

## Prior work

This is a new codebase written at the event. It follows the idea of an earlier project by another author: Orbit Health, Philip Mocanu's Cal Hacks 13.0 project (https://devpost.com/software/orbit-health). No code, data or assets from that project are used here.
