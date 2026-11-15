"""usb audio adapter on the tray, its usb lead to the hub, and the speaker lead.

no product is named for the adapter, so this is a generic unbranded usb sound card that fills the CAD
envelope (60 x 25 x 12): moulded dark grey case with a parting line, a status led window, a 3.5 mm output
jack (green) and mic jack (pink) on the +Y face, and a captive 3.0 mm usb lead leaving the +Y face through
a strain relief. the lead is cut short and its four wires are soldered into the hub port at x 3.04,
y 6.35 to 13.97 of the ch334f step. a right-angle 3.5 mm plug in the output jack carries a red and black
twisted pair up to the speaker's solder tabs (tab position estimated, check against the speaker model).
pod frame (identity seat) for both assets.
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
import usb_pigtails  # noqa: E402

OD = 3.0
SPK_WIRE = 1.25


def jack_hole(body, x, y_face, z, ring_mat, name):
    hole = kit.lathe("jh", [(2.0, -0.5), (2.0, 9.0)], 48, None, pole_start=-0.5, pole_end=9.0)
    kit.transform(hole, kit.frame_matrix((x, y_face + 0.5, z), (0, -1, 0)))
    kit.boolean(body, hole)
    ring = kit.lathe(name + "_ring", [(2.05, 0.0), (3.4, 0.0), (3.55, 0.12), (3.55, 0.35), (3.4, 0.45), (2.05, 0.45),
                                      (2.0, 0.3)], 64, kit.M(ring_mat), closed=True)
    kit.transform(ring, kit.frame_matrix((x, y_face - 0.2, z), (0, 1, 0)))
    bush = kit.lathe(name + "_bush", [(1.78, 0.0), (2.02, 0.0), (2.02, 3.0), (1.78, 3.0)], 48, kit.M("nickel_satin"),
                     closed=True)
    kit.transform(bush, kit.frame_matrix((x, y_face, z), (0, -1, 0)))
    return [kit.auto_smooth(ring, 40), kit.auto_smooth(bush, 40)]


def adapter(L):
    P, DV = L["P"], L["DV"]
    x0, x1, y0, y1 = L["adapter_box"]
    z0 = DV["tray_z1"]
    h = P["adapter"][2] - 0.4
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    body = kit.plan_block("audio_adapter_case", x1 - x0, y1 - y0, h, 4.0, 1.8, kit.M("abs_grey"), n=6.0,
                          groove=(h * 0.45, 0.15, 0.25))
    body.data.transform(kit.Matrix.Translation((cx, cy, z0)))
    zj = z0 + h * 0.5
    objs = []
    objs += jack_hole(body, 62.0, y1, zj, "lacquer_jack_green", "jack_out")
    objs += jack_hole(body, 53.0, y1, zj, "lacquer_jack_pink", "jack_mic")
    led = kit.lathe("audio_adapter_led", [(1.0, 0.0), (0.98, 0.15)] +
                    [(0.95 * math.cos(math.radians(a)), 0.15 + 0.35 * math.sin(math.radians(a))) for a in (30, 60, 80)],
                    32, kit.M("led_lens_green"), pole_start=0.0, pole_end=0.5)
    led.data.transform(kit.Matrix.Translation((66.0, cy, z0 + h - 0.05)))
    kit.auto_smooth(body, 35)
    objs = [body, led] + objs
    # captive usb lead, strain relief on the +Y face
    xs, zs = 16.0, z0 + 4.2
    boot = kit.lathe("audio_usb_boot", [(3.2, 0.0)] + [(3.2 - 1.45 * u ** 0.8 - (0.15 if 0.3 < u < 0.85 and
                                                                                  int(u * 10) % 2 else 0), 7.5 * u)
                                                       for u in np.linspace(0.05, 1, 24)],
                     48, kit.M("tpe_black"), pole_start=0.0, pole_end=7.5)
    kit.transform(boot, kit.frame_matrix((xs, y1 - 0.4, zs), (0, 1, 0)))
    objs.append(kit.auto_smooth(boot, 40))
    tray = DV["tray_z1"] + OD / 2
    C = kit.smooth_path([(xs, y1 + 5.5, zs), (xs + 0.6, y1 + 10.0, tray + 0.6), (17.4, 42.5, tray + 0.3)],
                        t0=(0, 1, 0), t1=(0.25, 1, 0.0), step=0.2, floor=tray)
    objs.append(kit.tube("audio_usb_jacket", C, OD / 2, kit.M("pvc_black"), segs=32))
    objs.append(parts.heatshrink("audio_usb_shrink", C[-30:], OD / 2 + 0.28, OD / 2 + 0.12))
    fan, _ = usb.fan_to_pads("audio_usb", C[-1], C[-1] - C[-6], usb_pigtails.port_pads(L, 0, "low"),
                             usb_pigtails.HUB_TOP)
    bends = parts.report_bends("audio_adapter", {"audio_usb_jacket": (C, OD)})
    return objs + fan, bends, (62.0, y1, zj)


def speaker_lead(L, jack):
    P = L["P"]
    jx, jy, jz = jack
    objs = []
    # right-angle 3.5 mm plug: nickel collar, moulded l-shaped body, boot upward
    collar = kit.lathe("trs_collar", [(1.78, 0.0), (1.78, 0.6), (2.3, 0.6), (2.3, 0.9)], 48, kit.M("nickel"),
                       pole_start=0.0, pole_end=0.9)
    kit.transform(collar, kit.frame_matrix((jx, jy - 0.3, jz), (0, 1, 0)))
    objs.append(collar)
    body_P = kit.smooth_path([(jx, jy + 0.9, jz), (jx, jy + 5.0, jz), (jx, jy + 7.4, jz + 2.6), (jx, jy + 7.4, jz + 9.5)],
                             t0=(0, 1, 0), t1=(0, 0, 1), step=0.1, k=0.5)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(body_P, axis=0), axis=1))]
    r = 3.0 - 0.25 * np.clip((s - 0.0) / 1.0, 0, 1) * 0 + 0.0 * s
    body = kit.tube("trs_body", body_P, r, kit.M("tpe_black"), segs=48)
    objs.append(kit.auto_smooth(body, 50))
    top = body_P[-1]
    bootP = np.array([top + (0, 0, u) for u in np.linspace(0, 7.0, 40)])
    br = np.array([2.6 - 1.2 * (u / 7.0) ** 0.8 - (0.12 if 1.5 < u < 6 and int(u * 2) % 2 else 0)
                   for u in np.linspace(0, 7.0, 40)])
    objs.append(kit.auto_smooth(kit.tube("trs_boot", bootP, br, kit.M("tpe_black"), segs=40), 40))
    cable_start = top + (0, 0, 6.0)
    # tab position on the speaker basket, estimated: radius 16 at -60 deg seen from the front, 8.6 behind the face
    gx, gz = P["grille_c"]
    tabs = [(gx + 16.5 * math.cos(math.radians(a)), P["wall"] + 6.2, gz + 16.5 * math.sin(math.radians(a)))
            for a in (-52, -68)]
    C = kit.smooth_path([cable_start, cable_start + (0, 0, 6), (jx - 4.0, 30.0, 48.0), (52.0, 18.0, 47.5),
                         ((tabs[0][0] + tabs[1][0]) / 2, 12.0, (tabs[0][2] + tabs[1][2]) / 2 + 0.5)],
                        t0=(0, 0, 1), t1=(-0.1, -1, 0.1), step=0.2)
    C = kit.relax(C, 4.2 * SPK_WIRE * 1.6)
    A, B = parts.pair(C, SPK_WIRE * 1.02, 16.0, ramp=4.0)
    ends = []
    for nm, Q, mat, tab in (("spk_red", A, "pvc_red", tabs[0]), ("spk_black", B, "pvc_wire_black", tabs[1])):
        tail = kit.smooth_path([Q[-1], (tab[0], tab[1] + 2.8, tab[2]), (tab[0], tab[1] - 0.6, tab[2])],
                               t0=Q[-1] - Q[-4], t1=(0, -1, 0), step=0.15)
        W = np.vstack([Q[:-1], tail])
        objs += parts.wire(nm, W, SPK_WIRE, mat, strip1=2.2)
        objs.append(parts.solder_joint(nm + "_tab", np.array([(tab[0], y, tab[2]) for y in
                                                             np.linspace(tab[1] + 1.4, tab[1] - 0.8, 20)]), 0.75))
        ends.append((nm, W))
    bends = parts.report_bends("speaker_lead", {"pair_centre": (C, SPK_WIRE * 2)} |
                               {nm: (W, SPK_WIRE) for nm, W in ends})
    return objs, bends


def main():
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    objs, b1, jack = adapter(L)
    kit.save("audio_adapter", {"units": "mm", "frame": "pod frame (identity seat)",
                               "origin": __doc__.strip(), "bends": b1})
    kit.reset()
    objs, b2 = speaker_lead(L, jack)
    kit.save("speaker_lead", {"units": "mm", "frame": "pod frame (identity seat)",
                              "origin": __doc__.strip(), "bends": b2})
    kit.report("audio_adapter", bends=b1)
    kit.report("speaker_lead", bends=b2)
    if "--preview" in kit.argv():
        import bpy
        sc = [o for o in bpy.context.scene.objects if o.type == "MESH"] + kit.append_blend("audio_adapter")
        ctx = kit.load_context(["tray", "ch334f_pcb", "ch334f_chip", "ch334f_usb_c", "speaker_frame",
                                "speaker_magnet", "speaker_clamp"])
        kit.preview("audio_adapter", sc + ctx, az=-150, el=35, lens=85, target=(40, 30, 28), radius=42,
                    ground_z=kit.GROUND_Z, fstop=22)


if __name__ == "__main__":
    main()
