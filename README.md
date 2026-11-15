# Orbit Health

Orbit Health is one web page, `/mission/`, for one question: is the  rainy season in Eastern Province, Zambia changing, and what should a health team do about it? It follows the loop Detect -> Verify -> Act. SKY tests 45 seasons of NASA POWER data for the grid cell around a village. GROUND shows live readings from a USB pod, K-01, each beside its tested error. ACTION turns a patient's danger-sign answer into a medicine order and a delivery on real roads.

The app is static. It reads JSON files under `public/` that the Python scripts in this repo write, works with Wi-Fi off, and makes no AI model calls. `docs/METHODS.md` explains the statistics and lists every limit, `docs/VALIDATION.md` holds the pod sensor checks, and `docs/SUBMISSION.md` is the NASA Space Apps entry.

## Run it

You need Python 3.10 or newer and Node 22. Run every command from the repo root.

### Python: tests and data

```
python3 -m venv .venv
. .venv/bin/activate
pip install -r trend/requirements.txt -r validation/requirements.txt
python -m pytest trend validation scripts -q
```

Build the trend files from NASA POWER, then add the ERA5 cross-check, then write the numbers into the docs:

```
python trend/build_trends.py --places trend/places.json --out public/trends
python trend/cross_check.py --trends public/trends
python scripts/fill_docs.py
```

`build_trends.py` downloads one file per grid cell into `trend/cache/` and pauses 1 second between requests. A second run reads the cache and downloads nothing. `cross_check.py` does the same for ERA5 into `trend/cache/era5/`, with a 3 second pause; a cell whose request fails is listed at the end and keeps its NASA result. Both scripts take `--cache <folder>` to reuse a cache kept somewhere else. Run `build_trends.py` before `cross_check.py`: the build rewrites the cell files and drops the ERA5 results.

### Web app

```
npm ci
npm test
npm run typecheck
npm run build
npm start
```

`npm test` runs the unit tests (vitest). `npm run build` writes the static site to `out/`, and `npm start` serves `out/` at http://localhost:3000. Open http://localhost:3000/mission/.

Browser checks (Playwright; they build nothing, so run `npm run build` first):

```
npx playwright install chromium
npm run e2e
```

### Keys and query flags

| Key or flag | What it does |
|---|---|
| `?place=<id>` | Selects a place by its id in `trend/places.json`, for example `/mission/?place=katete`. |
| `?story=1` | Story mode. Right and left arrows step through the demo. |
| `R` | Starts or stops replay of `public/pod/replay.json`, under a REPLAY badge. Without the file, a message says no replay is recorded yet. |
| `?sim=1` | Starts the development simulator, under a SIMULATION badge. |
| `?record=1` | Records pod events and shows a "Download session" button. |

### Connect the pod

Flash `firmware/pod_k01` as described in `firmware/README.md` and plug the pod into the laptop. Open http://localhost:3000/mission/ in Chrome or Edge (Web Serial works only there, and only on `localhost` or HTTPS), press "Connect pod" in the GROUND panel and pick the pod's port. After the first time, the page opens the same port by itself. When no reading arrives for 5 seconds, the panel shows "pod offline".

### Record a replay

Open http://localhost:3000/mission/?record=1, connect the pod, take the readings you want to replay, then press "Download session". Save the file as `public/pod/replay.json` and run `npm run build` again so `out/` includes it. `R` then replays it.

### Fill the validation CSVs

Write real paired readings into `validation/pulse/readings.csv`, `validation/mosquito/trials.csv` and `validation/weather/log.csv` (the columns are in the header rows and in plan section A7), then run:

```
python validation/report.py
python scripts/fill_docs.py
npm run build
```

`report.py` rewrites `docs/VALIDATION.md`, `docs/validation_results.json` and `public/validation/results.json`, which the GROUND panel reads. A sensor with no data is left out of the two JSON files, so the screen says "not yet tested" for it. Rows with a blank reading or an unknown condition are left out and counted.

### Rebuild the normals for the venue

The GROUND panel compares the live air reading with NASA POWER's normal range for today's date at the pod's location. `public/trends/pod_site.json` is built for Austin, Texas. To build it for another place, give its latitude and longitude:

```
python trend/normals.py --lat 30.2672 --lon -97.7431 --name "Austin, Texas" --out public/trends/pod_site.json
```

### Rebuild the map data

`mapdata/build.sh` downloads about 700 MB into `mapdata/raw/` and rewrites `public/map/*` and `trend/places.json`. It needs GDAL, osmium-tool and docker (for the OSRM router) on the path, and the Python packages shapely, pyproj and openpyxl:

```
pip install shapely pyproj openpyxl
bash mapdata/build.sh
```

`mapdata/README.md` describes each step. After a map rebuild, run the trend build again so the places match.

### The enclosure

`hardware/cad/README.md` has the commands that rebuild the CAD files and renders in `hardware/out/`.

## Layout

```
app/, components/   Next.js 15 app; components/mission/ is the Mission view, the rest is BoardUI
lib/                pod events (lib/pod), trend files (lib/trends), triage, orders and story (lib/mission), map
public/trends/      index.json, one file per grid cell, pod_site.json
public/map/         province, districts, roads, rivers, towns, facilities, routes, relief, sources.json
trend/              trend engine, trend build, ERA5 cross-check, normals, places.json, tests
validation/         validation CSVs and report.py
mapdata/            scripts that build public/map/ and trend/places.json
firmware/pod_k01/   Arduino sketch for the pod
firmware/pod_uno/   early prototype on an Arduino Uno robot car kit (see firmware/README.md)
hardware/           CAD source (cad/) and its outputs (out/)
docs/               METHODS, VALIDATION, SUBMISSION, REFERENCES, AI_USE
scripts/            fill_docs.py, which writes the numbers into the docs
e2e/                Playwright checks
```

## What has been tested

The firmware compiles. The pod hardware has not been run with this software by the authors of this repo; the serial path is tested with a simulated port. The validation CSV files are empty until people fill them, so every pod reading says "not yet tested". The enclosure is a CAD design with renders and has not been built. `docs/METHODS.md` lists the rest.

## Credits and licences

NASA POWER data: NASA Langley Research Center POWER project, values from the MERRA-2 reanalysis (NASA GMAO). Cross-check: ECMWF ERA5 reanalysis through the Open-Meteo archive API. The citations are in `docs/REFERENCES.md`. Map and facility data:

<!-- fill_docs:credits -->
| Data | Licence | Used for |
|---|---|---|
| [geoBoundaries Zambia ADM1 (Zambia Data Hub)](https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ZMB/ADM1/geoBoundaries-ZMB-ADM1.geojson) | Creative Commons Attribution 4.0 International (CC BY 4.0) | province outline |
| [geoBoundaries Zambia ADM2 (GRID3, Office of the Surveyor General)](https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ZMB/ADM2/geoBoundaries-ZMB-ADM2.geojson) | Creative Commons Attribution 4.0 (CC BY 4.0) | district outlines and facility districts |
| [Natural Earth 1:10m admin 0 boundary lines](https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_boundary_lines_land.zip) | Public domain (Natural Earth terms of use) | international borders |
| [Natural Earth 1:10m admin 0 countries](https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip) | Public domain (Natural Earth terms of use) | country names and label points |
| [Public health facilities in sub Saharan Africa (Maina et al. 2019, Scientific Data, doi:10.1038/s41597-019-0142-2)](https://doi.org/10.6084/m9.figshare.7725374.v1) | CC0 (https://creativecommons.org/publicdomain/zero/1.0/) | health facility names, types and locations |
| [OpenStreetMap Zambia extract (Geofabrik)](https://download.geofabrik.de/africa/zambia-latest.osm.pbf) | Open Database License 1.0 (ODbL), (c) OpenStreetMap contributors | roads, rivers, towns and road routing (OSRM) |
| [Copernicus DEM GLO-90 (AWS Open Data, copernicus-dem-90m)](https://copernicus-dem-90m.s3.amazonaws.com) | Copernicus DEM GLO-90, free licence; produced using Copernicus WorldDEM-90 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved | hillshade relief (49 tiles) |
<!-- /fill_docs:credits -->

## Earlier project

This is a new codebase written at RiverHacks x NASA Space Apps 2026. It follows the idea of an earlier project by another author: Orbit Health, Philip Mocanu's Cal Hacks 13.0 project (https://devpost.com/software/orbit-health). No code, data or assets from that project are used here.

## Licence

The team still has to choose an open-source licence before publishing this repository.
