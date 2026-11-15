"""the pod's one external cable: usb-c to usb-c, 4.0 mm braided nylon jacket.

pod frame (identity seat). the hub end plugs into the ch334f upstream receptacle, the cable is tied to the
tray anchor with a nylon tie, leaves through the rear plate keyhole and clamp, drops to the bench and lies on it;
the far plug rests on the bench. every curve keeps a bend radius of at least 4 x 4.0 mm.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import parts  # noqa: E402
import usb  # noqa: E402

OD = 4.0


def braid(carriers=16, lay=11.0, amp=0.11, fibres=3):
    half = carriers // 2

    def f(i, th, s):
        a = half * (th / (2 * math.pi) + s / lay)
        b = half * (th / (2 * math.pi) - s / lay)
        fa, fb = a % 1.0, b % 1.0
        top_a = (np.floor(a) + np.floor(b)) % 2 == 0

        def hump(x):
            return np.sqrt(np.clip(1 - (2 * x - 1) ** 2, 0, 1)) * (0.85 + 0.15 * np.cos(2 * math.pi * fibres * x))

        ha, hb = hump(fa), hump(fb)
        return amp * np.where(top_a, ha + 0.25 * hb, hb + 0.25 * ha) - amp * 0.6
    return f


def tie(y, cable_c, anchor):
    """nylon 2.5 mm cable tie around the cable and through the tray anchor slot (all in the xz plane at y)."""
    cx, cz = cable_c
    x0, x1, z_top, z_slot = anchor
    pts = [(cx + 0.8, cz + 2.62), (cx - 1.0, cz + 2.55), (cx - 2.65, cz + 1.4), (x0 - 0.1, z_top + 0.9),
           (x0 - 0.5, z_top - 0.3), (x0 - 0.5, z_slot + 0.5), (x0 + 0.4, z_slot), (cx, z_slot), (x1 - 0.4, z_slot),
           (x1 + 0.5, z_slot + 0.5), (x1 + 0.5, z_top - 0.3), (x1 + 0.1, z_top + 0.9), (cx + 2.65, cz + 1.4),
           (cx + 1.9, cz + 2.4)]
    P = kit.catmull([(x, y, z) for x, z in pts], step=0.1)
    v, f, _ = kit.strip_mesh(P, 2.5, 1.0, (0, 1, 0), edge_r=0.15)
    strap = kit.mesh_obj("tie_strap", v, f, kit.M("nylon_natural"))
    # serrations on the inner face are below what shows; the head is a real block with its pawl window
    head = kit.cube("tie_head", (4.2, 3.6, 3.1), (cx + 1.5, y, cz + 2.55 + 1.55), kit.M("nylon_natural"), bevel=0.45)
    tail_P = np.array([(cx + 3.2 + u, y, cz + 2.9 - 0.1 * u) for u in np.linspace(0, 1.4, 8)])
    v, f, _ = kit.strip_mesh(tail_P, 2.5, 1.0, (0, 1, 0), edge_r=0.15)
    tail = kit.mesh_obj("tie_tail", v, f, kit.M("nylon_natural"))
    return [kit.auto_smooth(strap, 40), head, tail]


def build(L):
    P, DV = L["P"], L["DV"]
    kx = P["keyhole_c"][0]
    cz = DV["cable_z"]
    hub_face = 48.8 + 16.353  # vendor hub: board centre y + receptacle mouth
    objs, exit_z = usb.usb_c_plug("plug_hub", overmold=(12.0, 6.4), length=12.0, boot_len=6.0, cable_d=OD)
    tip_y = hub_face + 0.3 - 6.65
    usb.seat(objs, (kx, tip_y, cz), (0, 1, 0), (1, 0, 0))
    y0 = tip_y + exit_z
    g = kit.GROUND_Z + OD / 2
    plate_out = P["D"] + P["plate_t"] - P["spigot_t"] + 3.0
    ctrl = [(kx, y0, cz), (kx, 92.0, cz), (kx, plate_out + 4.0, cz - 0.3), (kx + 0.5, 118.0, cz - 5.5),
            (kx + 1.5, 131.0, cz - 16.0), (kx + 3.5, 145.0, g + 4.0), (kx + 7.5, 162.0, g + 0.2), (kx + 15.0, 180.0, g),
            (kx + 48.0, 214.0, g), (kx + 88.0, 236.0, g), (kx + 128.0, 247.0, g)]
    C = kit.catmull(ctrl, t0=(0, 1, 0), step=0.2)
    C[:, 2] = np.maximum(C[:, 2], g)
    jacket = kit.tube("usb_cable_jacket", C, OD / 2, kit.M("braid_black"), segs=96, rfun=braid(), n0=(1, 0, 0))
    objs.append(kit.auto_smooth(jacket, 60))
    d = C[-1] - C[-5]
    d /= np.linalg.norm(d)
    far, far_exit = usb.usb_c_plug("plug_far", overmold=(12.0, 6.4), length=15.0, boot_len=8.5, cable_d=OD)
    side = np.cross(d, (0, 0, 1))
    origin = C[-1] + d * far_exit
    origin[2] = kit.GROUND_Z + 3.2
    usb.seat(far, origin, -d, side)
    objs += far
    anchor_x0, anchor_x1 = kx - 5.0, kx + 5.0
    z_top = cz - OD / 2 - 0.2
    z_slot = DV["tray_z1"] + 2.0
    objs += tie(88.0, (kx, cz), (anchor_x0, anchor_x1, z_top, z_slot))
    bends = parts.report_bends("usb_cable", {"usb_cable": (C, OD)})
    return objs, bends


def main():
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    objs, bends = build(L)
    meta = {"units": "mm", "frame": "pod frame (identity seat)",
            "origin": __doc__.strip(), "bends": bends}
    kit.save("usb_cable", meta)
    kit.report("usb_cable", bends=bends)
    if "--preview" in kit.argv():
        import bpy
        sc = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        ctx = kit.load_context(["tray", "ch334f_pcb", "ch334f_chip", "ch334f_usb_c", "rear_plate", "cable_clamp"])
        plate = [o for o in ctx if o.name in ("ctx_rear_plate",)]
        kit.preview("usb_cable", sc + ctx, az=150, el=34, lens=70, target=(85, 165, 0), radius=125,
                    ground_z=kit.GROUND_Z)
        kit.preview("usb_cable", sc + ctx, az=-35, el=48, lens=100, target=(33, 79, 20), radius=20,
                    ground_z=kit.GROUND_Z, hide=plate, name="usb_cable_tie", fstop=22)


if __name__ == "__main__":
    main()
