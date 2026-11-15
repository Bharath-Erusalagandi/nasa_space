"""usb-c pigtails from the ch334f hub to the vision ai v2 and the xiao.

the ch334f breakout has no downstream sockets, only 0.1 in through holes per port (gnd, d-, d+, 5v), so each
pigtail is a short 3.0 mm usb cable with a moulded usb-c plug at one end and its four wires soldered into a
port's holes at the other. pod frame (identity seat). hole positions come from adafruit's ch334f board file
as seated by the vendor manifest (board 20.32 x 30.48 centred on the hub pose): rows 7.62 either side of the
centre line, four pins on a 2.54 pitch per port. receptacle positions are the real ones from the vendor
vision stack (both usb-c mouths at x 90.3 to 90.5; the board's own usb-c is on its underside).
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import parts  # noqa: E402
import usb  # noqa: E402

OD = 3.0
HUB_C = (32.2, 48.8)  # vendor seat of the ch334f board centre
HUB_TOP = 17.6 + 1.51
HOLES_X = (-7.62, 7.62)
HOLES_Y = {"low": (-8.89, -6.35, -3.81, -1.27), "high": (1.27, 3.81, 6.35, 8.89)}
VISION_USB = (90.34, 60.06, 18.6 - 1.63)
XIAO_USB = (90.5, 60.0, 29.01)


def port_pads(L, side, half):
    return [(k, (HUB_C[0] + HOLES_X[side], HUB_C[1] + y)) for k, y in zip(usb.PAD_ORDER, HOLES_Y[half])]


def pigtail(name, plug_face, plug_dir, x_dir, route, jacket_end, jacket_dir, pads, board_top, floor, plug_len=12.0,
            overmold=(12.0, 6.4)):
    """plug_face: receptacle mouth centre; plug_dir: direction the plug body extends away from it."""
    objs, exit_z = usb.usb_c_plug(name + "_plug", overmold=overmold, length=plug_len, boot_len=6.0, cable_d=OD)
    plug_dir = np.array(plug_dir, float)
    tip = np.array(plug_face) - plug_dir * (6.65 - 0.3)
    usb.seat(objs, tip, plug_dir, x_dir)
    start = tip + plug_dir * exit_z
    C = kit.smooth_path([start] + route + [jacket_end], t0=plug_dir, t1=jacket_dir, step=0.2, floor=floor)
    C = kit.relax(C, 4.2 * OD, floor=floor)
    objs.append(kit.tube(name + "_jacket", C, OD / 2, kit.M("pvc_black"), segs=32))
    hs = C[-int(7.0 / 0.2):]
    objs.append(parts.heatshrink(name + "_shrink", np.vstack([hs, hs[-1] + np.array(jacket_dir) * 0.6]),
                                 OD / 2 + 0.28, OD / 2 + 0.12))
    jd = C[-1] - C[-6]
    fan, paths = usb.fan_to_pads(name, C[-1], jd, pads, board_top)
    paths[name + "_jacket"] = (C, OD)
    return objs + fan, paths


def build(L):
    P, DV = L["P"], L["DV"]
    board_top = HUB_TOP
    tray = DV["tray_z1"] + OD / 2
    objs, paths = [], {}
    o, p = pigtail("pigtail_vision", VISION_USB, (-1, 0, 0), (0, 1, 0),
                   [(63.0, 57.4, tray + 0.3), (54.5, 48.8, tray)],
                   (48.0, 44.0, tray + 0.3), (-1, -0.75, 0.02), port_pads(L, 1, "low"), board_top, tray,
                   overmold=(11.0, 5.0))
    objs += o
    paths.update(p)
    o, p = pigtail("pigtail_xiao", XIAO_USB, (-1, 0, 0), (0, 1, 0),
                   [(65.0, 62.6, tray + 4.5)],
                   (48.2, 53.6, tray + 0.3), (-1, -0.75, 0.02), port_pads(L, 1, "high"), board_top, tray)
    objs += o
    paths.update(p)
    bends = parts.report_bends("usb_pigtails", {k: v for k, v in paths.items() if k.endswith("_jacket")})
    return objs, bends


def main():
    L = json.loads((kit.OUT / "layout.json").read_text())
    kit.reset()
    objs, bends = build(L)
    meta = {"units": "mm", "frame": "pod frame (identity seat)",
            "origin": __doc__.strip(), "bends": bends,
            "port_use": {"x 18.28 low (adafruit PORT4 side)": "vision ai v2", "x 18.28 high": "xiao"}}
    kit.save("usb_pigtails", meta)
    kit.report("usb_pigtails", bends=bends)
    if "--preview" in kit.argv():
        import bpy
        sc = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        ctx = kit.load_context(["tray", "ch334f_pcb", "ch334f_chip", "ch334f_usb_c", "vision_ai_v2_pcb",
                                "vision_ai_v2_usb_c", "vision_ai_v2_parts", "xiao_sockets", "xiao_nrf52840_pcb",
                                "xiao_shield", "xiao_usb_c"])
        kit.preview("usb_pigtails", sc + ctx, az=-30, el=42, lens=85, target=(66, 52, 20), radius=38,
                    ground_z=kit.GROUND_Z, fstop=22)
        kit.preview("usb_pigtails", sc + ctx, az=-120, el=40, lens=100, target=(42, 49, 19), radius=11,
                    ground_z=kit.GROUND_Z, fstop=22, name="usb_pigtails_pads")


if __name__ == "__main__":
    main()
