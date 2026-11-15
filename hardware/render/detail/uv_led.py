"""5 mm water-clear uv led (t-1 3/4) with its lead frame, a 68 ohm axial resistor and two wires to the xiao.

built in the led's own frame (origin at the centre of the flange underside, +Z out through the dome,
flat and cathode toward -X), then seated in the pod frame at P.led_c on DV.led_flange_z0.
the whole asset (led, resistor, joints, wires) is saved in the pod frame, so its seating matrix is identity.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import parts  # noqa: E402
from mathutils import Matrix  # noqa: E402

WIRE_OD = 1.3  # 26 awg pvc hook-up wire


def epoxy():
    prof = [(0.6, 0.07), (2.3, 0.03), (2.82, 0.0), (2.9, 0.06), (2.9, 0.94), (2.84, 1.0), (2.52, 1.0),
            (2.5, 1.04), (2.48, 4.0), (2.47, 6.1)]
    for a in np.linspace(8, 88, 14):
        prof.append((2.47 * math.cos(math.radians(a)), 6.1 + 2.5 * math.sin(math.radians(a))))
    ob = kit.lathe("uv_led_epoxy", prof, 128, kit.M("epoxy_clear"), pole_start=0.08, pole_end=8.6)
    flat = kit.cube("flat_cut", (3, 8, 1.3), (-2.58 - 1.5, 0, 0.5), None)
    kit.boolean(ob, flat)
    return kit.auto_smooth(ob, 30)


def lead_frame():
    m = kit.M("silver_plate")
    objs = []
    # cathode: flat lead widening into the anvil that carries the reflector cup
    cath = [(-1.52, -10.0), (-1.02, -10.0), (-1.02, -1.6), (-0.82, -1.1), (-0.82, 0.0), (-0.77, 3.6),
            (0.78, 4.35), (0.78, 4.9), (-1.77, 4.9), (-1.77, 0.0), (-1.72, -1.1), (-1.52, -1.6)]
    objs.append(kit.prism_xz("uv_led_cathode", cath, -0.25, 0.25, m, bevel=0.04))
    anode = [(1.02, -12.0), (1.52, -12.0), (1.52, -1.6), (1.72, -1.1), (1.72, 4.6), (1.65, 5.3), (0.92, 5.3),
             (0.85, 4.6), (0.82, -1.1), (1.02, -1.6)]
    objs.append(kit.prism_xz("uv_led_anode", anode, -0.25, 0.25, m, bevel=0.04))
    cup = kit.lathe("uv_led_cup", [(0.95, 4.85), (0.95, 5.45), (0.78, 5.47), (0.33, 5.07)], 64, m,
                    pole_start=4.85, pole_end=5.07)
    objs.append(kit.auto_smooth(cup, 40))
    die = kit.cube("uv_led_die", (0.3, 0.3, 0.14), (0, 0, 5.07 + 0.07), kit.M("led_die"), bevel=0.01)
    pad = kit.lathe("uv_led_die_pad", [(0.055, 5.21), (0.055, 5.23)], 24, kit.M("gold"), pole_start=5.21,
                    pole_end=5.23)
    bw = kit.catmull([(0, 0, 5.22), (0.25, 0, 5.78), (0.85, 0, 5.75), (1.2, 0, 5.3)], step=0.02)
    wire = kit.tube("uv_led_bond_wire", bw, 0.0125, kit.M("gold"), segs=8)
    ball = kit.lathe("uv_led_bond_ball", [(0.04, 5.3), (0.045, 5.33), (0.02, 5.36)], 16, kit.M("gold"),
                     pole_start=5.3, pole_end=5.37)
    ball.data.transform(Matrix.Translation((1.2, 0, 0)))
    return objs + [die, pad, wire, ball]


def resistor(z_top):
    """axial carbon film 1/4 w, 68 ohm 5 % (blue grey black gold), vertical, top lead end at z_top."""
    segs = 64
    body_top = z_top - 7.0
    L = 6.3
    bt = body_top
    prof = [(0.3, z_top), (0.3, bt + 0.25), (0.62, bt + 0.05), (1.02, bt - 0.12), (1.18, bt - 0.45),
            (1.2, bt - 0.8), (1.2, bt - 1.4), (1.17, bt - 1.65), (1.06, bt - 1.95), (1.05, bt - 2.25),
            (1.05, bt - 2.65), (1.05, bt - 3.15), (1.06, bt - 4.35), (1.17, bt - 4.65), (1.2, bt - 4.9),
            (1.2, bt - 5.4), (1.18, bt - 5.85), (1.02, bt - 6.18), (0.62, bt - L - 0.05), (0.3, bt - L - 0.25),
            (0.3, bt - L - 8.0)]
    bands = [("band_blue", bt - 0.8, bt - 1.4), ("band_grey", bt - 1.75, bt - 2.25),
             ("band_black", bt - 2.65, bt - 3.15), ("band_gold", bt - 4.9, bt - 5.4)]
    # refine rows so band edges are crisp
    zs = sorted({z for _, z in prof} | {z for _, a, b in bands for z in (a + 0.01, a, b, b - 0.01)}, reverse=True)
    rz = np.array([[r, z] for r, z in prof])[::-1]
    rows = []
    for z in zs:
        r = float(np.interp(z, rz[:, 1], rz[:, 0]))
        if any(b <= z <= a for _, a, b in bands) and r > 0.5:
            r += 0.012
        rows.append((r, z))
    mats = ["tin", "resistor_body"] + [b[0] for b in bands]
    v, f = kit.rev_rows(rows, segs, pole_start=z_top + 0.0, pole_end=bt - L - 8.0)
    idx = []
    # faces: pole_start fan comes last in rev_rows ordering; compute per row band material
    nrows = len(rows)
    row_mat = []
    for i in range(nrows - 1):
        zm = (rows[i][1] + rows[i + 1][1]) / 2
        rm = (rows[i][0] + rows[i + 1][0]) / 2
        k = 1 if rm > 0.45 else 0
        for j, (_, a, b) in enumerate(bands):
            if b <= zm <= a and rm > 0.5:
                k = 2 + j
        row_mat.append(k)
    for k in row_mat:
        idx += [k] * segs
    idx += [0] * segs * 2
    ob = kit.mesh_obj("resistor_68r", v, f, mats=[kit.M(m) for m in mats], mat_idx=idx)
    return kit.auto_smooth(ob, 40), bt - L - 8.0


def build(L):
    P, DV = L["P"], L["DV"]
    lx, ly = P["led_c"]
    z0 = DV["led_flange_z0"]
    seat = Matrix.Translation((lx, ly, z0))

    local = [epoxy()] + lead_frame()
    rz_top = -9.0
    res, res_bot = resistor(rz_top)
    res.data.transform(Matrix.Translation((1.27, 0.55, 0)))
    local.append(res)
    # anode to resistor lap joint, cathode and resistor tails to the wires
    local.append(parts.solder_joint("joint_anode_resistor",
                                    np.array([(1.27, 0.28, z) for z in np.linspace(-9.3, -12.15, 24)]), 0.62))
    red_y, blk_y = 0.55 + 0.52, 0.5
    local.append(parts.solder_joint("joint_resistor_red",
                                    np.array([(1.27, 0.8, z) for z in np.linspace(res_bot + 3.2, res_bot + 0.2, 24)]),
                                    0.6))
    local.append(parts.heatshrink("shrink_red", np.array([(1.27, 0.8, z) for z in
                                                          np.linspace(res_bot + 4.6, res_bot - 3.6, 60)]), 1.05, 0.93))
    local.append(parts.solder_joint("joint_cathode_black",
                                    np.array([(-1.27, 0.25, z) for z in np.linspace(-6.8, -9.9, 24)]), 0.6))
    local.append(parts.heatshrink("shrink_black", np.array([(-1.27, 0.25, z) for z in np.linspace(-5.4, -13.6, 60)]),
                                  1.0, 0.9))
    kit.place(local, seat)

    def pod(x, y, z):
        return np.array((lx + x, ly + y, z0 + z))

    red_start = pod(1.27, red_y, res_bot + 3.2)
    blk_start = pod(-1.27, blk_y, -6.8)
    # twisted pair from below the resistor to the xiao's 5V and GND pads (pod frame)
    C = kit.catmull([pod(0, 2.0, res_bot - 7.0), (92.6, 48.5, 52.5), (98.0, 56.5, 43.0)], t0=(0, 0.15, -1),
                    t1=(0.35, 0.7, -0.6), step=0.2)
    A, B = parts.pair(C, WIRE_OD * 1.02, 18.0, ramp=8.0)
    if np.linalg.norm(A[0] - red_start) > np.linalg.norm(B[0] - red_start):
        A, B = B, A
    pad_z = DV["vis_z0"] + P["vision"][2] + 8.5 + P["xiao"][2]
    x5v, xgnd, ypad = 104.9, 107.44, 68.2

    def tail(x):
        return [(x, 61.5, pad_z + 4.6), (x, 65.0, pad_z + 1.3), (x, ypad + 0.9, pad_z + 0.26)]

    red = kit.catmull([red_start, red_start + (0, 0, -6.0)] + list(A[30:-4:5]) + tail(x5v),
                      t0=(0, 0, -1), t1=(0, 1, -0.05), step=0.2)
    blk = kit.catmull([blk_start, blk_start + (0, 0, -8.0), pod(-1.0, 1.0, res_bot - 1.0)] + list(B[30:-4:5]) +
                      tail(xgnd), t0=(0, 0, -1), t1=(0, 1, -0.05), step=0.2)
    objs = list(local)
    objs += parts.wire("wire_red", red, WIRE_OD, "pvc_red", strip0=3.0, strip1=2.6)
    objs += parts.wire("wire_black", blk, WIRE_OD, "pvc_wire_black", strip0=3.1, strip1=2.6)
    for nm, x in (("pad_joint_5v", x5v), ("pad_joint_gnd", xgnd)):
        objs.append(parts.solder_joint(nm, np.array([(x, y, pad_z + 0.2) for y in np.linspace(ypad - 1.3, ypad + 1.0,
                                                                                              24)]), 0.62, flat=2.5))
    bends = parts.report_bends("uv_led", {"wire_red": (red, WIRE_OD), "wire_black": (blk, WIRE_OD)})
    return objs, bends


def main():
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    objs, bends = build(L)
    meta = {"units": "mm", "frame": "pod frame (identity seat)",
            "origin": __doc__.strip(), "bends": bends,
            "assumptions": ["wires end on the xiao 5V and GND pin pads; pad positions estimated from the "
                            "xiao pinout, check against the vendor model",
                            "always on when powered: switching from a gpio needs a mosfet that is not in the CAD"]}
    kit.save("uv_led", meta)
    kit.report("uv_led", bends=bends)
    if "--preview" in kit.argv():
        sc = list(bkit for bkit in __import__("bpy").context.scene.objects if bkit.type == "MESH")
        P, DV = L["P"], L["DV"]
        lx, ly = P["led_c"]
        kit.preview("uv_led", sc, az=-40, el=12, lens=100, target=(lx, ly, DV["led_flange_z0"] - 7.0),
                    radius=18.0, ground_z=DV["led_flange_z0"] - 34.0, fstop=22, fill=1.15)
        ctx = kit.load_context(["vision_ai_v2_pcb", "xiao_sockets", "xiao_nrf52840_pcb", "xiao_shield", "xiao_usb_c",
                                "vision_ai_v2_parts", "tray"])
        kit.preview("uv_led", sc + ctx, az=-60, el=22, lens=85, target=(98, 55, 62), radius=48.0,
                    ground_z=kit.GROUND_Z, name="uv_led_wires")


if __name__ == "__main__":
    main()
