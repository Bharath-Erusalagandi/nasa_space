# mapdata

Scripts that build the offline map files in `public/map/` and the list of places in `trend/places.json` for Eastern Province, Zambia.

## Rebuild

From the repo root, on a Linux machine with GDAL, Python 3 and docker:

```
bash mapdata/build.sh
```

Downloads go to `mapdata/raw/` and are reused when present. Delete a file there to fetch it again. The routing step needs docker (`sudo docker`) and pulls `ghcr.io/project-osrm/osrm-backend:v5.27.1`; the container is removed when the step ends. `python mapdata/preview.py <out.jpg>` draws every layer into one picture for a quick look.

## Steps

| Script | Reads | Writes |
|---|---|---|
| `boundaries.py` | geoBoundaries ZMB ADM1 and ADM2 (through its API), Natural Earth 1:10m borders and countries | `province.json`, `districts.json`, `frame.json`, `context.json` |
| `facilities.py` | Maina et al. 2019 public health facilities (figshare file found through the figshare API by the paper DOI) | `facilities.json` |
| `osm.py` | Geofabrik Zambia extract | `roads.json`, `rivers.json`, `towns.json`, `raw/routing.osm.pbf` |
| `places.py` | the files above | `trend/places.json` |
| `routes.py` | `raw/routing.osm.pbf`, `trend/places.json` | `routes.json` |
| `relief.py` | Copernicus GLO-90 DEM tiles from the public `copernicus-dem-90m` bucket | `relief.webp`, `relief.json` |
| `check.py` | everything | exit code 0 when all checks pass |

Each fetching script adds its dataset to `public/map/sources.json` with the licence it read from the source: the geoBoundaries API, the figshare API, and the Natural Earth terms page, Geofabrik page and Copernicus bucket readme (the script stops if the licence sentence is no longer there). Each entry also gets a short `credit` (`group` and `text`) from `CREDITS` in `common.py`; the map's attribution line is built from those. `python common.py` adds them to an existing `sources.json` without downloading anything.

## Choices

- Province: the geoBoundaries ADM1 feature named `Eastern`. Districts: ADM2 features whose inner point falls inside it. Boundaries are simplified at 0.001 degrees.
- Frame: province bounds padded by 0.25 degrees.
- Facilities: rows with country `Zambia` and Admin1 `Eastern`. Rows without coordinates, or more than 5 km outside the province polygon (measured in UTM 36S), are dropped and counted. The dataset has no district column, so `district` is the geoBoundaries district that contains the point, or the nearest one for points just outside the outline.
- Roads: OSM `highway` trunk, primary, secondary and tertiary, merged by class and name, clipped to the frame. Rivers: OSM `waterway=river` with a name. Both are simplified in UTM 36S, starting at 30 m and 50 m and raising the tolerance until the file is under its size limit (500 KB and 150 KB). Towns: OSM nodes with `place` town or city.
- Routes: OSRM car profile on the extract clipped to the frame plus 0.75 degrees, from Chipata to every town and facility, lines simplified at 100 m. `snap_km` is the straight-line gap between the place and the nearest road OSRM could reach; the line ends at that road.
- Relief: a multidirectional hillshade (vertical exaggeration 3) of the frame in Web Mercator, greys stretched to 70 to 235. `relief.json` gives its bounds in longitude and latitude and its pixel size.
- Places: the five reference towns with the plan's coordinates, every kept facility (id is a slug of its name, with `-2`, `-3` added on a clash), and one `cell` entry at the centre of each NASA POWER cell (0.5 x 0.625 degrees) that overlaps the province and holds no town or facility. A cell id like `-14.000_31.875` becomes the place id `cell-s14-000-31-875`.
