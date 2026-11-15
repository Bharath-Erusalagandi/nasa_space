"""usb connectors and pigtail ends in mm.

plug frames: origin on the axis at the front tip of the metal shell, +Z points back toward the cable,
the long side of the shell along X.
"""

import math

import numpy as np

import kit
import parts

TAU = 2 * math.pi
USB_COLOURS = {"gnd": "pvc_wire_black", "dm": "pvc_white", "dp": "pvc_green", "vbus": "pvc_red"}
PAD_ORDER = ["gnd", "dm", "dp", "vbus"]  # ch334f port pads in order of increasing y


def rr(w, h, rc, segs):
    th = np.arange(segs) * TAU / segs
    return kit.rounded_rect_r(w, h, rc, th)


def usb_c_plug(name, overmold=(12.0, 6.4), length=15.0, boot_len=8.5, cable_d=3.0):
    """usb type-c plug: drawn steel shell with a moulded insulator and 2 x 12 contacts, tpe overmould, ribbed boot.
    returns (objects, z where the cable leaves the boot)."""
    segs = 96
    out = []
    so, si = rr(8.25, 2.4, 1.2, segs), rr(7.75, 1.9, 0.95, segs)
    shell_len = 6.65 + 1.5
    v, f = kit.rev_rows([(si, 0.14), ((so + si) / 2, 0.0), (so, 0.14), (so, shell_len), (si, shell_len)], segs,
                        closed=True)
    out.append(kit.auto_smooth(kit.mesh_obj(name + "_shell", v, f, kit.M("nickel")), 50))
    ins, slot = rr(7.72, 1.86, 0.93, segs), rr(6.75, 0.78, 0.39, segs)
    v, f = kit.rev_rows([(ins, shell_len), (ins, 0.9), (slot * 1.04, 0.86), (slot, 1.0), (slot, 5.9)], segs,
                        pole_start=shell_len, pole_end=5.9)
    out.append(kit.auto_smooth(kit.mesh_obj(name + "_insulator", v, f, kit.M("pbt_black")), 50))
    for side in (-1, 1):
        for k in range(12):
            x = -2.75 + k * 0.5
            out.append(kit.cube(f"{name}_pin{side}_{k}", (0.24, 0.09, 1.7), (x, side * 0.35, 2.3), kit.M("gold"),
                                bevel=0.03))
    # overmould: rounded block with a front chamfer, slight taper, then a ribbed round boot
    a0, b0 = overmold[0] / 2, overmold[1] / 2
    z0 = 6.65
    th = np.arange(segs) * TAU / segs
    rows = []
    for z, ka, kb in ((z0, -0.7, -0.7), (z0 + 0.25, -0.25, -0.25), (z0 + 0.7, 0, 0), (z0 + length * 0.5, -0.05, -0.03),
                      (z0 + length - 1.2, -0.3, -0.15), (z0 + length - 0.3, -0.75, -0.5)):
        rows.append((kit.superellipse(a0 + ka, b0 + kb, 4.0, th), z))
    zb = z0 + length
    rb0 = min(b0, 3.0)
    for u in np.linspace(0, 1, 40):
        z = zb + u * boot_len
        r = rb0 + (cable_d / 2 + 0.35 - rb0) * u ** 0.8
        r -= 0.18 * max(0.0, math.sin(u * 5 * math.pi)) ** 4 if 0.15 < u < 0.92 else 0.0
        rows.append((r, z))
    rows.append((cable_d / 2 + 0.05, zb + boot_len + 0.15))
    v, f = kit.rev_rows(rows, segs, pole_start=z0, pole_end=zb + boot_len + 0.15)
    out.append(kit.auto_smooth(kit.mesh_obj(name + "_overmould", v, f, kit.M("tpe_black")), 40))
    return out, zb + boot_len - 1.0


def usb_a_plug(name):
    """usb type-a plug: 12.0 x 4.5 steel shell with latch windows, insulator on -Y with four contacts."""
    segs = 96
    so, si = rr(12.0, 4.5, 0.45, segs), rr(11.5, 4.0, 0.25, segs)
    L = 12.0
    v, f = kit.rev_rows([(si, 0.15), ((so + si) / 2, 0.0), (so, 0.15), (so, L), (si, L)], segs, closed=True)
    shell = kit.mesh_obj(name + "_shell", v, f, kit.M("nickel"))
    for x in (-3.6, 3.6):
        for y in (-2.3, 2.3):
            kit.boolean(shell, kit.cube("win", (2.0, 1.2, 1.7), (x, y, 3.6), None))
    kit.auto_smooth(shell, 40)
    ins = kit.cube(name + "_insulator", (11.4, 1.95, L - 1.0), (0, -2.0 + 0.975, L / 2 + 0.5), kit.M("pbt_white"),
                   bevel=0.08)
    pins = []
    for x, w in ((-3.5, 1.0), (-1.0, 1.0), (1.0, 1.0), (3.5, 1.0)):
        pins.append(kit.cube(f"{name}_pin{x}", (w, 0.12, 7.5 if abs(x) > 2 else 7.0),
                             (x, -2.0 + 1.95 + 0.06, 1.0 + (3.75 if abs(x) > 2 else 4.0)), kit.M("gold"), bevel=0.03))
    return [shell, ins] + pins


def usb_a_receptacle_overmould(name, length=17.0, boot_len=6.5, cable_d=3.0):
    """inline usb-a female socket: steel receptacle shell with its tongue, inside a moulded tpe body.
    frame: origin at the socket mouth, +Z toward the cable."""
    segs = 96
    out = []
    so, si = rr(13.1, 5.7, 0.4, segs), rr(12.55, 5.15, 0.25, segs)
    v, f = kit.rev_rows([(si, 0.25), ((so + si) / 2, 0.0), (so * 1.03, 0.2), (so, 0.6), (so, 10.5), (si, 10.5)],
                        segs, closed=True)
    out.append(kit.auto_smooth(kit.mesh_obj(name + "_shell", v, f, kit.M("nickel")), 40))
    out.append(kit.cube(name + "_tongue", (11.1, 1.84, 8.8), (0, 2.575 - 0.62 - 0.92, 10.5 - 4.4), kit.M("pbt_black"),
                        bevel=0.1))
    th = np.arange(segs) * TAU / segs
    rows = []
    for z, k in ((0.3, -0.6), (0.6, 0.0), (length - 1.5, -0.1), (length - 0.4, -0.7)):
        rows.append((kit.superellipse(15.6 / 2 + k, 8.0 / 2 + k, 4.5, th), z))
    for u in np.linspace(0, 1, 30):
        r = 3.6 + (cable_d / 2 + 0.3 - 3.6) * u ** 0.8
        r -= 0.15 * max(0.0, math.sin(u * 4 * math.pi)) ** 4 if 0.15 < u < 0.9 else 0.0
        rows.append((r, length + u * boot_len))
    v, f = kit.rev_rows(rows, segs, pole_start=0.3, pole_end=length + boot_len)
    body = kit.mesh_obj(name + "_overmould", v, f, kit.M("tpe_black"))
    kit.boolean(body, kit.cube("mouth", (13.0, 5.6, 11.0), (0, 0, 5.0), None))
    out.append(kit.auto_smooth(body, 40))
    return out, length + boot_len - 1.0


def seat(objs, origin, back_dir, x_dir):
    """place a plug built in its own frame: +Z of the plug along back_dir, X along x_dir."""
    M = kit.frame_matrix(origin, back_dir, x_dir)
    kit.place(objs, M)
    return M


def fan_to_pads(name, jacket_pt, jacket_dir, pads, board_top, wire_od=0.85, board_t=1.6):
    """individual wires leaving a jacket end, each dropping into a plated hole with a solder fillet.
    pads: list of (colour key, (x, y)). returns objects."""
    jacket_dir = np.array(jacket_dir, float)
    jacket_dir /= np.linalg.norm(jacket_dir)
    side = np.cross(jacket_dir, (0, 0, 1.0))
    side /= np.linalg.norm(side)
    up = np.cross(side, jacket_dir)
    offs = [(-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)]
    objs = []
    paths = {}
    order = sorted(range(len(pads)), key=lambda i: float(np.dot(np.r_[pads[i][1], 0] - jacket_pt, side)))
    for slot, i in enumerate(order):
        key, (px, py) = pads[i]
        o = offs[slot]
        start = np.array(jacket_pt) - jacket_dir * 2.5 + side * o[0] + up * o[1]
        exitp = np.array(jacket_pt) + jacket_dir * 1.5 + side * o[0] * 1.2 + up * o[1]
        top = np.array((px, py, board_top + 2.6))
        P = kit.catmull([start, exitp, top + (0, 0, 1.2), (px, py, board_top + 0.4), (px, py, board_top - board_t - 0.6)],
                        t0=jacket_dir, t1=(0, 0, -1), step=0.12)
        objs += parts.wire(f"{name}_{key}", P, wire_od, USB_COLOURS[key], strip1=board_t + 2.1)
        paths[f"{name}_{key}"] = (P, wire_od)
        fillet = [(0.92, board_top), (0.86, board_top + 0.06), (0.66, board_top + 0.22), (0.46, board_top + 0.46),
                  (0.33, board_top + 0.72), (0.27, board_top + 0.84)]
        f = kit.lathe(f"{name}_{key}_fillet", fillet, 32, kit.M("solder"), pole_start=board_top, pole_end=board_top + 0.86)
        f.data.transform(kit.Matrix.Translation((px, py, 0)))
        objs.append(kit.auto_smooth(f, 60))
        under = kit.lathe(f"{name}_{key}_under", [(0.85, board_top - board_t), (0.5, board_top - board_t - 0.35),
                                                  (0.28, board_top - board_t - 0.5)], 24, kit.M("solder"),
                          pole_start=board_top - board_t, pole_end=board_top - board_t - 0.55)
        under.data.transform(kit.Matrix.Translation((px, py, 0)))
        objs.append(under)
    return objs, paths
