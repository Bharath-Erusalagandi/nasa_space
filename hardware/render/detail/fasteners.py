"""screws, heat-set inserts, washers and rubber feet, with real threads, sockets, recesses and knurls.

local frame of every fastener: origin on the axis at the surface it seats on, +Z out of that surface
(screw: top of the head, shank along -Z; insert: open end face; washer and pad: bearing face).
writes build/detail/fasteners.blend (one collection per type) and fasteners_instances.json.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402

TAU = 2 * math.pi


def thread_r(d, p, th, z, internal=False):
    """iso metric 60 degree profile, right hand. external: crest at d/2; internal: root at d/2."""
    ph = (z / p - th / TAU) % 1.0
    x = np.abs(ph - 0.5) * 2
    r_maj, r_min = d / 2, d / 2 - 0.6134 * p
    if internal:
        r_maj, r_min = d / 2 + 0.03, d / 2 - 0.5413 * p
        return r_maj - (r_maj - r_min) * np.clip((x - 0.25) / (0.875 - 0.25), 0, 1)
    return r_min + (r_maj - r_min) * np.clip((x - 0.25) / (0.875 - 0.25), 0, 1)


def shank_rows(d, p, L, z_top, segs, th):
    rows = []
    r_min = d / 2 - 0.6134 * p
    for z in np.arange(-L + 0.02, z_top, p / 14):
        r = thread_r(d, p, th, z)
        r = np.minimum(r, r_min * 0.82 + (z + L) * 1.0)  # 45 degree point chamfer
        rows.append((r, z))
    return rows


def hex_r(s, th):
    a = (th + math.pi / 6) % (math.pi / 3) - math.pi / 6
    return (s / 2) / np.cos(a)


def cross_r(m, b, th):
    a = (th + math.pi / 4) % (math.pi / 2) - math.pi / 4
    return np.minimum(m / 2, (b / 2) / np.maximum(np.abs(np.sin(a)), 1e-3))


def csk_screw(name, d, p, L, dk, k, s, t):
    """iso 10642 countersunk hexagon socket screw."""
    segs = 96
    th = np.arange(segs) * TAU / segs
    rows = shank_rows(d, p, L, -k, segs, th)
    rows += [(d / 2, -k), (dk / 2 - 0.06, -0.16), (dk / 2 - 0.1, -0.04), (dk / 2 - 0.2, 0.0)]
    rh = hex_r(s, th)
    rows += [(rh * 1.07, 0.0), (rh, -0.07), (rh, -t), (rh * 0.35, -t - 0.28)]
    v, f = kit.rev_rows(rows, segs, pole_start=-L, pole_end=-t - 0.35)
    ob = kit.mesh_obj(name, v, f, kit.M("black_oxide"))
    return kit.auto_smooth(ob, 40)


def pan_screw(name, d, p, L, dk, k, m, b, t, mat="steel_zinc"):
    """iso 7045 pan head with a type H cross recess."""
    segs = 128
    th = np.arange(segs) * TAU / segs
    rows = shank_rows(d, p, L, -k - 0.1, segs, th)
    rows += [(d / 2 + 0.05, -k - 0.02), (d / 2 + 0.15, -k)]
    rf = k * 0.28
    for a in np.linspace(-90, 0, 4):
        rows.append((dk / 2 - rf + rf * math.cos(math.radians(a)), -k + rf + rf * math.sin(math.radians(a))))
    # domed top from the side to the flat
    for u in np.linspace(0.1, 1, 8):
        r = (dk / 2) * (1 - 0.42 * u)
        z = -k + rf + (k - rf) * math.sin(u * math.pi / 2)
        rows.append((r, z))
    rows += [(cross_r(m * 1.12, b * 1.5, th), 0.0), (cross_r(m, b, th), -0.08),
             (cross_r(m * 0.62, b * 0.85, th), -t * 0.6), (cross_r(m * 0.22, b * 0.6, th), -t)]
    v, f = kit.rev_rows(rows, segs, pole_start=-L, pole_end=-t - 0.12)
    return kit.auto_smooth(kit.mesh_obj(name, v, f, kit.M(mat)), 40)


def insert_m3(name, L=5.7):
    """brass heat-set insert, m3 x 5.7: two knurl bands of opposite hand, a relief groove, lead-in."""
    segs = 144
    th = np.arange(segs) * TAU / segs
    teeth, r_v, h = 18, 2.18, 0.17
    tan_a = math.tan(math.radians(30))

    def knurl(z, hand):
        u = teeth * (th - hand * z * tan_a / r_v) / TAU
        tri = 1 - np.abs(2 * (u % 1.0) - 1)
        return r_v + h * np.clip(tri * 1.25, 0, 1)

    rows = [(1.62, 0.0), (2.05, 0.0), (2.2, -0.12)]
    for z in np.arange(-0.3, -2.45, -0.05):
        rows.append((knurl(z, +1), z))
    rows += [(2.12, -2.5), (2.02, -2.62), (2.02, -2.95), (2.12, -3.05)]
    for z in np.arange(-3.1, -4.95, -0.05):
        rows.append((knurl(z, -1), z))
    rows += [(2.15, -5.0), (1.98, -L + 0.12), (1.9, -L), (1.62, -L)]
    for z in np.arange(-L + 0.1, -0.1, 0.035):
        rows.append((thread_r(3.0, 0.5, th, z, internal=True), z))
    rows.append((1.62, -0.06))
    v, f = kit.rev_rows(rows, segs, closed=True)
    return kit.auto_smooth(kit.mesh_obj(name, v, f, kit.M("brass")), 50)


def washer(name, di, do, t, mat="stainless"):
    c = 0.06
    prof = [(di / 2 + c, 0), (do / 2 - c, 0), (do / 2, c), (do / 2, t - c), (do / 2 - c, t), (di / 2 + c, t),
            (di / 2, t - c), (di / 2, c)]
    return kit.auto_smooth(kit.lathe(name, prof, 96, kit.M(mat), closed=True), 40)


def foot_pad(name, d=9.5, h=2.8):
    """polyurethane bump-on: flat adhesive face, short wall, dome."""
    r = d / 2
    prof = [(r - 0.15, 0.0), (r, 0.12), (r, 0.9)]
    for a in np.linspace(0.08, 1, 16):
        prof.append((r * math.cos(a * math.pi / 2) ** 0.8, 0.9 + (h - 0.9) * math.sin(a * math.pi / 2)))
    prof[-1] = (0.0, h)
    prof = [p for p in prof if p[0] > 1e-4]
    return kit.lathe(name, prof, 96, kit.M("pu_black"), pole_start=0.0, pole_end=h)


def types():
    return {
        "m3x10_csk": lambda: csk_screw("m3x10_csk", 3.0, 0.5, 10.0, 6.3, 1.7, 2.0, 1.2),
        "m3x8_csk": lambda: csk_screw("m3x8_csk", 3.0, 0.5, 8.0, 6.3, 1.7, 2.0, 1.2),
        "m3x10_pan": lambda: pan_screw("m3x10_pan", 3.0, 0.5, 10.0, 5.6, 2.4, 3.1, 0.62, 1.4),
        "m2x6_pan": lambda: pan_screw("m2x6_pan", 2.0, 0.4, 6.0, 4.0, 1.6, 2.0, 0.48, 1.0),
        "m3_insert": lambda: insert_m3("m3_insert"),
        "m3_washer": lambda: washer("m3_washer", 3.2, 7.0, 0.5),
        "m2_washer": lambda: washer("m2_washer", 2.2, 5.0, 0.3),
        "foot_pad": lambda: foot_pad("foot_pad"),
    }


def instances(L):
    """(part name, type, origin mm, +Z direction) in the pod frame, from layout.json."""
    P, DV = L["P"], L["DV"]
    out = []
    Y, NY, Z, NZ = (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)
    plate_out = P["D"] + P["plate_t"] - P["spigot_t"]
    for i, (x, z) in enumerate(DV["corner_bosses"]):
        out.append((f"screw_rear_plate_{i + 1}", "m3x10_csk", (x, plate_out, z), Y))
        out.append((f"insert_corner_{i + 1}", "m3_insert", (x, DV["back_in"], z), Y))
    ear_y1 = P["wall"] + P["cradle_boss_h"] + P["ear_t"]
    csk_top = ear_y1 - 0.4 + (P["m3_csk_d"] - P["m3_clear"]) / 2
    for i, (x, z) in enumerate(DV["cradle_bosses"]):
        out.append((f"screw_cradle_{i + 1}", "m3x10_csk", (x, csk_top, z), Y))
        out.append((f"insert_cradle_{i + 1}", "m3_insert", (x, P["wall"] + P["cradle_boss_h"], z), Y))
    kx, kz = P["keyhole_c"]
    for i, x in enumerate((kx - 11.0, kx + 11.0)):
        out.append((f"screw_cable_clamp_{i + 1}", "m3x10_csk", (x, plate_out + 3.0, kz), Y))
        out.append((f"insert_plate_clamp_{i + 1}", "m3_insert", (x, plate_out, kz), Y))
    for i, (x, z) in enumerate(L["clip_screws"]):
        out.append((f"screw_capsule_clip_{i + 1}", "m3x8_csk", (x, P["D"] - P["spigot_t"], z), NY))
        out.append((f"insert_capsule_clip_{i + 1}", "m3_insert", (x, plate_out, z), NY))
    y_fl = P["wall"] + P["spk_rim_t"] + 5.2
    spk_boss_top = y_fl
    for i, (x, z) in enumerate(DV["spk_bosses"]):
        out.append((f"insert_speaker_{i + 1}", "m3_insert", (x, spk_boss_top, z), Y))
        out.append((f"washer_speaker_clamp_{i + 1}", "m3_washer", (x, y_fl + P["spk_clamp_t"], z), Y))
        out.append((f"screw_speaker_clamp_{i + 1}", "m3x10_pan", (x, y_fl + P["spk_clamp_t"] + 0.5 + 2.4, z), Y))
    cam_back = DV["cam_board_y0"] + P["cam_board"][2]
    for i, (x, z) in enumerate(DV["cam_posts"]):
        out.append((f"screw_camera_{i + 1}", "m2x6_pan", (x, cam_back + 1.6, z), Y))
    for i, (x, y) in enumerate(L["max_holes"]):
        out.append((f"washer_max30101_{i + 1}", "m2_washer", (x, y, DV["max_bot"]), NZ))
        out.append((f"screw_max30101_{i + 1}", "m2x6_pan", (x, y, DV["max_bot"] - 0.3 - 1.6), NZ))
    hub_top = DV["hub_z0"] + P["hub"][2]
    for i, (x, y) in enumerate(L["hub_holes"]):
        out.append((f"screw_hub_{i + 1}", "m2x6_pan", (x, y, hub_top + 1.6), Z))
    vis_top = DV["vis_z0"] + P["vision"][2]
    for i, (x, y) in enumerate(L["vision_holes"]):
        out.append((f"screw_vision_{i + 1}", "m2x6_pan", (x, y, vis_top + 1.6), Z))
    pad_z = -P["foot_h"] + P["pad_depth"]
    for i, (fx, fy) in enumerate([(22.0, 8.0), (22.0, 64.0), (P["W"] - 22.0, 8.0), (P["W"] - 22.0, 64.0)]):
        py = fy + P["foot_h"] + (P["foot_l"] - P["foot_h"]) / 2
        out.append((f"foot_pad_{i + 1}", "foot_pad", (fx, py, pad_z), NZ))
    return out


def matrix(origin, zdir):
    M = kit.frame_matrix(origin, zdir)
    return [list(r) for r in M]


def main():
    args = kit.argv()
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    objs = {n: f() for n, f in types().items()}
    groups = {n: [o] for n, o in objs.items()}
    meta = {"units": "mm", "origin": __doc__.split("\n\n")[1].strip(),
            "types": {"m3x10_csk": "ISO 10642 M3x10, 6.3 head (actual, 6.72 theoretical), 2.0 hex socket",
                      "m3x8_csk": "ISO 10642 M3x8", "m3x10_pan": "ISO 7045 M3x10 pan, H cross recess",
                      "m2x6_pan": "ISO 7045 M2x6 pan, H cross recess",
                      "m3_insert": "brass heat-set insert M3 x 5.7, 4.4 to 4.7 knurl",
                      "m3_washer": "ISO 7089 M3", "m2_washer": "ISO 7089 M2",
                      "foot_pad": "polyurethane bump-on 9.5 x 2.8"}}
    kit.save("fasteners", meta, groups)
    inst = [{"part": p, "file": "fasteners.blend", "collection": t, "matrix": matrix(o, zd), "origin_mm": o}
            for p, t, o, zd in instances(L)]
    (kit.OUT / "fasteners_instances.json").write_text(json.dumps(inst, indent=1))
    print(len(inst), "fastener instances")
    if "--preview" in args:
        lineup = ["m3x10_csk", "m3x8_csk", "m3x10_pan", "m2x6_pan", "m3_insert", "m3_washer", "m2_washer",
                  "foot_pad"]
        from mathutils import Euler
        x = 0.0
        for n in lineup:
            o = objs[n]
            head_r = {"m3x10_csk": 3.15, "m3x8_csk": 3.15, "m3x10_pan": 2.8, "m2x6_pan": 2.0}.get(n)
            if head_r:
                o.rotation_euler = Euler((math.radians(90), 0, math.radians(14)))
                o.location = (x, 0, head_r)
            else:
                o.location = (x, 0, 5.7 if n == "m3_insert" else 0)
            x += 9.0
        # a second insert on its side to show the knurl bands
        dup = objs["m3_insert"].copy()
        kit.link(dup)
        dup.rotation_euler = (math.radians(90), 0, math.radians(70))
        dup.location = (38, -9, 2.32)
        kit.preview("fasteners", list(objs.values()) + [dup], az=-6, el=38, lens=100, ground_z=0.0,
                    fill=1.0, fstop=16)


if __name__ == "__main__":
    main()
