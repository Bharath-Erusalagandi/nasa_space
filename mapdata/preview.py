import json
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.image import imread

from common import MAP, PLACES, read_geojson


def lines(ax, name, **style):
    for g, _ in read_geojson(MAP / name):
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "Polygon":
                part = part.exterior
            x, y = part.xy
            ax.plot(x, y, **style)


def main(out):
    fr = json.loads((MAP / "frame.json").read_text())
    rb = json.loads((MAP / "relief.json").read_text())
    fig, ax = plt.subplots(figsize=(10, 10), dpi=100)
    # equirectangular preview, so the mercator relief is only roughly aligned
    ax.imshow(imread(MAP / "relief.webp"), extent=(rb["west"], rb["east"], rb["south"], rb["north"]), alpha=0.5)
    lines(ax, "districts.json", color="#999", lw=0.5)
    lines(ax, "province.json", color="#333", lw=1.2)
    lines(ax, "context.json", color="#a33", lw=1, ls="--")
    lines(ax, "rivers.json", color="#48c", lw=0.6)
    lines(ax, "roads.json", color="#c80", lw=0.7)
    routes = json.loads((MAP / "routes.json").read_text())["routes"]
    for r in routes.values():
        if len(r["line"]) > 1:
            x, y = zip(*r["line"])
            ax.plot(x, y, color="#0a0", lw=0.4, alpha=0.5)
    colors = {"town": "#000", "facility": "#d22", "cell": "#26f"}
    for p in json.loads(PLACES.read_text()):
        ax.plot(p["lon"], p["lat"], "o", ms=2.5 if p["kind"] == "facility" else 5, color=colors[p["kind"]])
    ax.set_xlim(fr["west"], fr["east"])
    ax.set_ylim(fr["south"], fr["north"])
    ax.set_aspect(1 / 0.97)
    fig.savefig(out, bbox_inches="tight", pil_kwargs={"quality": 80})


if __name__ == "__main__":
    main(sys.argv[1])
