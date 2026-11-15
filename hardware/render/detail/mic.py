"""usb microphone dongle (adafruit 3367 class) and the usb-a socket pigtail that connects it to the hub.

pod frame (identity seat). the dongle sits in the pocket under the top wall, sound holes up under the
mic port row; the socket pigtail drops behind it to the tray, crosses over the hub's upstream plug and
ends in four wires soldered into the hub port at x 3.04, y 16.51 to 24.13 of the ch334f step.
note: adafruit lists 22.2 x 18.3 x 7.0 mm and that length may include the plug; the CAD pocket and this model
take 22.2 as the body length. measure the real dongle.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import parts  # noqa: E402
import usb  # noqa: E402
import usb_pigtails  # noqa: E402

OD = 3.0


def dongle(L):
    P, DV = L["P"], L["DV"]
    mx, my = P["mic_c"]
    dw, dl, dh = P["dongle"]
    z0 = DV["dongle_z0"]
    body = kit.plan_block("mic_dongle_body", dw, dl, dh, 3.0, 1.4, kit.M("abs_black_gloss"), n=5.0,
                          groove=(dh * 0.42, 0.12, 0.2))
    body.data.transform(kit.Matrix.Translation((mx, my, z0)))
    for k in range(5):
        hole = kit.lathe("hole", [(0.42, -0.2), (0.42, 1.4)], 24, None, pole_start=-0.2, pole_end=1.4)
        hole.data.transform(kit.Matrix.Translation((mx - 4 + 2 * k, my, z0 + dh - 1.2)))
        kit.boolean(body, hole)
    # acoustic felt at the bottom of the holes
    felt = kit.cube("mic_dongle_felt", (9.2, 1.2, 0.05), (mx, my, z0 + dh - 1.15), kit.M("foam_black"))
    kit.auto_smooth(body, 35)
    plug = usb.usb_a_plug("mic_dongle_plug")
    zc = z0 + dh / 2
    usb.seat(plug, (mx, my + dl / 2 + 12.0, zc), (0, -1, 0), (1, 0, 0))
    return [body, felt] + plug


def pigtail(L):
    P, DV = L["P"], L["DV"]
    mx, my = P["mic_c"]
    dl = P["dongle"][1]
    zc = (DV["dongle_z0"] + DV["dongle_z1"]) / 2
    mouth = np.array((mx, my + dl / 2 + 2.0, zc))
    objs, exit_z = usb.usb_a_receptacle_overmould("mic_socket", length=15.5, boot_len=6.0, cable_d=OD)
    usb.seat(objs, mouth, (0, 1, 0), (-1, 0, 0))
    start = mouth + np.array((0, exit_z, 0))
    tray = DV["tray_z1"] + OD / 2
    hub_plug_top = DV["cable_z"] + 3.2
    pads = usb_pigtails.port_pads(L, 0, "high")
    route = [(mx, start[1] + 9.0, zc - 9.0), (mx - 0.5, start[1] + 11.6, 60.0), (mx - 2.0, start[1] + 10.8, 42.0),
             (mx - 14.0, 85.4, hub_plug_top + 4.0), (32.0, 84.8, hub_plug_top + OD / 2 + 0.6),
             (24.5, 83.2, tray + 3.6), (12.8, 74.0, tray + 0.6), (13.8, 64.0, tray + 0.2)]
    jacket_end = (16.6, 57.0, tray + 0.3)
    C = kit.smooth_path([start] + route + [jacket_end], t0=(0, 1, 0), t1=(0.35, -1, 0.02), step=0.2, floor=tray)
    C = kit.relax(C, 4.2 * OD, keep=0.6, floor=tray)
    objs.append(kit.tube("mic_pigtail_jacket", C, OD / 2, kit.M("pvc_black"), segs=32))
    hs = C[-35:]
    objs.append(parts.heatshrink("mic_pigtail_shrink", hs, OD / 2 + 0.28, OD / 2 + 0.12))
    fan, paths = usb.fan_to_pads("mic_pigtail", C[-1], C[-1] - C[-6], pads, usb_pigtails.HUB_TOP)
    bends = parts.report_bends("mic_pigtail", {"mic_pigtail_jacket": (C, OD)})
    return objs + fan, bends


def main():
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    d = dongle(L)
    kit.save("mic_dongle", {"units": "mm", "frame": "pod frame (identity seat)",
                            "origin": __doc__.strip()})
    kit.reset()
    objs, bends = pigtail(L)
    kit.save("mic_pigtail", {"units": "mm", "frame": "pod frame (identity seat)",
                             "origin": __doc__.strip(), "bends": bends})
    kit.report("mic_pigtail", bends=bends)
    if "--preview" in kit.argv():
        import bpy
        sc = [o for o in bpy.context.scene.objects if o.type == "MESH"] + kit.append_blend("mic_dongle")
        ctx = kit.load_context(["tray", "ch334f_pcb", "ch334f_chip", "ch334f_usb_c"]) + kit.append_blend("usb_cable")
        kit.preview("mic_dongle", sc, az=-35, el=35, lens=100, target=(60, 52, 103), radius=22, fstop=22)
        kit.preview("mic_pigtail", sc + ctx, az=-125, el=24, lens=70, target=(45, 70, 58), radius=62,
                    ground_z=kit.GROUND_Z)


if __name__ == "__main__":
    main()
