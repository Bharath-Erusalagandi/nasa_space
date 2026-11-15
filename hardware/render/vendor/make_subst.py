"""STEP stand-ins for the two footprints on the Vision AI V2 layout that have no model at all.

microsd_short_mr267.step: SD-TF-MR267 short body push socket, outline and pads from Seeed's footprint,
height 1.45 [E]. Origin and axes follow the KiCad footprint (y flipped, z up from the copper).
usage: python -I make_subst.py <out_dir>
"""

import sys
from pathlib import Path

from build123d import Align, Box, Color, Compound, Pos, export_step

A = (Align.MIN, Align.MIN, Align.MIN)


def blk(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=A)


def tagged(shape, name, rgb):
    shape.label, shape.color = name, Color(*rgb)
    return shape


def microsd(out):
    # footprint y grows down the page; step y is up, so the body sits at y -0.76 .. -6.6
    h, t = 1.45, 0.15
    shell = blk(-5.62, 5.63, -6.6, -0.76, 0, h) - blk(-5.62 + t, 5.63 - t, -6.6 + t, -0.5, 0.0, h - t)
    tabs = [blk(x - 0.6, x + 0.6, y - 0.5, y + 0.5, 0, 0.15) for x, y in
            ((-5.225, -1.61), (-5.225, -6.06), (5.225, -6.06), (5.225, -1.61))]
    base = blk(-5.4, 5.4, -6.4, -0.9, 0, 0.45)
    tails = [blk(x - 0.18, x + 0.18, -0.95, 0.2, 0, 0.12) for x in (3.85, 2.75, 1.65, 0.55, -0.55, -1.65, -2.75, -3.85)]
    gnd = blk(-2.2, -1.8, -0.95, 0.2, 0, 0.12)
    parts = [tagged(shell, "shell", (0.75, 0.76, 0.78))]
    parts += [tagged(s, f"tab{k}", (0.75, 0.76, 0.78)) for k, s in enumerate(tabs)]
    parts += [tagged(base, "insulator", (0.08, 0.08, 0.08))]
    parts += [tagged(s, f"contact{k}", (0.83, 0.69, 0.22)) for k, s in enumerate(tails + [gnd])]
    asm = Compound(children=parts)
    asm.label = "SD-TF-MR267"
    export_step(asm, str(out / "microsd_short_mr267.step"))


def oesip(out):
    """MAX30101 14-pin OESIP, 5.6 x 3.3 x 1.55 (Maxim outline 21-0880): black body, cover glass, two optical cavities.
    cavity sizes and positions are read off product photos [E]."""
    L, W, H, g = 5.6, 3.3, 1.55, 0.25
    body = blk(-L / 2, L / 2, -W / 2, W / 2, 0.05, H - g)
    led = blk(-2.3, -0.6, -0.8, 0.8, H - g - 0.35, H - g)
    pd = blk(0.2, 2.3, -0.8, 0.8, H - g - 0.35, H - g)
    body -= led
    body -= pd
    glass = blk(-L / 2, L / 2, -W / 2, W / 2, H - g, H)
    floor_led = blk(-2.3, -0.6, -0.8, 0.8, H - g - 0.36, H - g - 0.34)
    die = blk(0.6, 1.9, -0.55, 0.55, H - g - 0.36, H - g - 0.3)
    pads = [blk(x - 0.2, x + 0.2, y0, y0 + 0.4, 0, 0.05)
            for x in (-2.4, -1.6, -0.8, 0.0, 0.8, 1.6, 2.4) for y0 in (-1.6, 1.2)]
    parts = [tagged(body, "body", (0.02, 0.02, 0.02)), tagged(glass, "cover_glass", (0.9, 0.95, 0.95)),
             tagged(floor_led, "led_dies", (0.6, 0.55, 0.45)), tagged(die, "photodiode", (0.12, 0.12, 0.2))]
    parts += [tagged(p, f"pad{k}", (0.83, 0.69, 0.22)) for k, p in enumerate(pads)]
    asm = Compound(children=parts)
    asm.label = "MAX30101_OESIP"
    export_step(asm, str(out / "max30101_oesip.step"))


if __name__ == "__main__":
    o = Path(sys.argv[1])
    o.mkdir(parents=True, exist_ok=True)
    microsd(o)
    oesip(o)
