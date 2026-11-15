"""reusable wiring pieces in mm: insulated wires with stranded ends, solder joints, heat shrink, twisted pairs."""

import math

import numpy as np

import kit


def strands(name, P, r_cond, n=7, lay=6.0, mat="tin"):
    """stranded conductor: one core and six helical strands along path P."""
    rs = r_cond / 3.0
    T, N, B = kit.frames(P)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    objs = [kit.tube(name + "_core", P, rs * 1.02, kit.M(mat), segs=8)]
    for k in range(n - 1):
        ph = 2 * math.pi * k / (n - 1) + 2 * math.pi * s / lay
        Q = P + (2 * rs) * (np.cos(ph)[:, None] * N + np.sin(ph)[:, None] * B)
        objs.append(kit.tube(f"{name}_s{k}", Q, rs, kit.M(mat), segs=8))
    return kit.join(objs, name)


def wire(name, P, od, insul, strip0=0.0, strip1=0.0, tinned=True, cond_frac=0.42, segs=18):
    """insulated wire on path P (mm). strip0/strip1: bare length at the start/end.
    returns the objects (insulation, then exposed conductors)."""
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    L = s[-1]
    m = (s >= strip0) & (s <= L - strip1)
    objs = []
    ins = P[m]
    if len(ins) > 1:
        ob = kit.tube(name, ins, od / 2, kit.M(insul), segs=segs)
        objs.append(ob)
    rc = od / 2 * cond_frac * 2
    for k, (lo, hi) in enumerate(((0, strip0 + 0.3), (L - strip1 - 0.3, L))):
        if hi - lo <= 0.31:
            continue
        mm = (s >= lo) & (s <= hi)
        if mm.sum() > 1:
            if tinned:
                # tinned ends: strands wetted into one smooth rod with a faint lay
                objs.append(kit.tube(f"{name}_end{k}", P[mm], rc / 2, kit.M("solder"), segs=12,
                                     rfun=lambda i, th, ss: 0.02 * np.cos(6 * th + ss * 2.1)))
            else:
                objs.append(strands(f"{name}_end{k}", P[mm], rc / 2, mat="tin"))
    return objs


def solder_joint(name, P, r_max, r_min=0.3, flat=1.0):
    """smooth solder fillet along a lap joint path P."""
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    u = s / s[-1]
    r = r_min + (r_max - r_min) * np.sin(np.pi * u) ** 0.5
    return kit.tube(name, P, r, kit.M("solder"), segs=24,
                    rfun=lambda i, th, ss: -0.12 * r_max * np.abs(np.sin(th)) * flat)


def heatshrink(name, P, r_mid, r_end, mat="heatshrink_black"):
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    u = s / s[-1]
    ramp = np.clip(np.minimum(u, 1 - u) / 0.12, 0, 1)
    r = r_end + (r_mid - r_end) * (3 * ramp ** 2 - 2 * ramp ** 3)
    # shrink wrinkles along the length
    return kit.tube(name, P, r, kit.M(mat), segs=28,
                    rfun=lambda i, th, ss: 0.012 * np.sin(5 * th + ss * 1.7) * np.sin(ss * 3.1))


def pair(C, sep, pitch, ramp=8.0, n0=None):
    """two paths twisted around centre path C with centre distance sep; twist fades in and out over `ramp` mm."""
    T, N, B = kit.frames(C, n0)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]
    w = np.clip(np.minimum(s, s[-1] - s) / ramp, 0, 1)
    w = 3 * w ** 2 - 2 * w ** 3
    ph = 2 * np.pi * np.cumsum(np.r_[0, np.diff(s)] * w) / pitch
    off = (sep / 2) * (np.cos(ph)[:, None] * N + np.sin(ph)[:, None] * B)
    return C + off, C - off


def report_bends(tag, paths_od):
    out = {}
    for nm, (P, od) in paths_od.items():
        r, at = kit.min_bend_radius(P, where=True)
        out[nm] = {"length_mm": round(kit.path_len(P), 1), "min_bend_radius_mm": round(r, 2),
                   "od_mm": od, "radius_over_od": round(r / od, 2), "tightest_at": at}
        print(f"{tag} {nm}: length {out[nm]['length_mm']} mm, min bend r {r:.1f} mm = {r / od:.1f} x od at {at}", flush=True)
    return out
