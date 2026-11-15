#!/bin/bash
# rebuilds public/map/* and trend/places.json; run from the repo root
set -euo pipefail
cd "$(dirname "$0")"
rm -f ../public/map/sources.json
python boundaries.py
python facilities.py
python osm.py
python places.py
python routes.py
python relief.py
python check.py
