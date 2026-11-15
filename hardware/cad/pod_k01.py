"""Pod K-01 enclosure: parametric build123d model, checks and exports.

Run: python hardware/cad/pod_k01.py
Coordinates: X across the face (left to right seen from the front), Y into the
box (front face at y = 0), Z up (underside of the shell at z = 0).
"""

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from build123d import (
    Align, Axis, Box, Color, Compound, Cone, Cylinder, Edge, Mesher, Plane, Polygon,
    Pos, Rectangle, RectangleRounded, Rot, Circle, Sphere, Text, Vector, export_step, export_stl,
    extrude, loft, revolve,
)

HERE = Path(__file__).resolve().parent
HW = HERE.parent
OUT = HW / "out"
BUILD = HW / "build"

# parameters (mm). [E] marks an estimate to measure before printing
P = SimpleNamespace(
    # shell
    W=150.0, H=110.0, D=92.0, wall=2.4, corner_r=12.0, front_chamfer=1.5, back_fillet=1.0,
    rebate_w=1.2, rebate_d=1.2, plate_fit=0.2,
    # fasteners
    insert_pilot=4.0, insert_depth=6.7, boss_d=8.0, m3_clear=3.4, m3_csk_d=6.4,
    m2_pilot=1.6, corner_boss_inset=7.5,
    # front layout (origin bottom left of the face)
    grille_c=(40.0, 62.0), grille_field_d=36.0, grille_hole_d=1.8, grille_pitch=3.2,
    cam_c=(112.0, 86.0), finger_c=(108.0, 36.0),
    label="K-01", label_x=16.0, label_base=15.0, label_cap=7.0, label_depth=0.6,
    # finger cradle
    port_w=28.0, port_h=24.0, port_r=4.0, cradle_fit=0.2, lip_proud=1.5, lip_r=2.0,
    tunnel_in=(22.0, 19.0), tunnel_sensor=(20.0, 16.0), tunnel_len=34.0, taper_len=15.5,
    window=(6.2, 4.0), window_from_stop=11.0, floor_over_sensor=1.0, ic_below_floor=0.3,
    end_wall=2.0, cradle_boss_dx=20.0, cradle_boss_h=7.5, ear_t=3.0,
    # MAX30101 SEN-16474 [P outline, E thickness, hole pattern, IC position]
    max_board=25.4, max_t=1.6, max_hole_d=3.3, max_hole_pitch=20.32, max_ic=(5.6, 3.3, 1.55),
    qwiic=(6.0, 4.25, 2.9),
    # camera OV5647 [E lens offset, barrel]
    cam_board=(25.0, 24.0, 1.0), cam_depth=9.0, cam_holes=(21.0, 12.5), cam_hole_from_top=2.0,
    cam_lens_from_top=9.5, cam_barrel_d=12.0, cam_lens_behind_face=2.0, cam_post_d=4.5,
    bezel_aperture=17.5, bezel_od=21.5, bezel_fit=0.1, bezel_flange=(30.0, 28.0, 1.5),
    # speaker 40 mm [P diameter, depth; E rim]
    spk_d=40.0, spk_depth=20.0, spk_rim_t=2.0, spk_boss_r=26.0, spk_clamp_t=3.0,
    # top
    mic_hole_d=1.5, mic_holes=5, mic_pitch=3.0, mic_c=(60.0, 41.1), led_c=(90.0, 41.0),
    led_hole_d=5.0, led_cb_d=5.8, led_proud=2.0,
    dongle=(18.3, 22.2, 7.0), dongle_gap_top=1.0,
    # tray
    tray_t=3.0, tray_gap=9.2, rail_w=2.5, rail_t=2.0, slide_fit=0.3,
    # bought parts on the tray
    hub=(20.4, 31.6, 1.6), hub_standoff=3.0, adapter=(60.0, 25.0, 12.0),
    vision=(40.0, 20.0, 1.6), vision_standoff=4.0, xiao=(21.0, 17.8, 1.2),
    plug_overmold=(12.0, 7.0, 20.0), usb_bend=25.0, cable_d=4.0,
    ribbon_w=16.0, ribbon_len=150.0,
    # rear plate
    plate_t=3.0, spigot_t=1.0, slot_w=2.5,
    keyhole_c=(32.2, 30.0), keyhole_d=13.0,
    # underside
    foot_h=8.0, foot_w=14.0, foot_l=22.0, pad_d=10.0, pad_depth=1.0, lead_hole_d=6.0,
    lead_hole=(50.0, 84.0), lead_d=3.5,
    # air sensor capsule
    cap_d=24.0, cap_h=34.0, sht31=(12.7, 18.0, 1.6), clip_t=2.4,
    min_clear=0.3,
)

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

COL = {
    "shell": "#d8d5ce", "plate": "#d8d5ce", "tray": "#7d8186", "black": "#1c1c1e",
    "dark": "#3a3a3c", "white": "#f1f0ea", "steel": "#b9bcc0", "red": "#b8202a",
    "ada_blue": "#1d2a6b", "seeed_green": "#1d6b45", "cam_green": "#2b6e3b",
    "xiao_blue": "#1e4f8f", "chip": "#202020", "led": "#7b3fd0", "ribbon": "#e8e2cf",
    "cable": "#202022", "foam": "#2a2a2a", "gold": "#c9a227",
}


# geometry helpers
def front_plane(y):
    return Plane(origin=(0, y, 0), x_dir=(1, 0, 0), z_dir=(0, -1, 0))


def yp(sk, y0, y1):
    """prism along +Y from a sketch drawn in (x, z)."""
    return extrude(front_plane(y0) * sk, amount=y1 - y0, dir=(0, 1, 0))


def zp(sk, z0, z1):
    return extrude(Plane.XY.offset(z0) * sk, amount=z1 - z0, dir=(0, 0, 1))


def xp(sk, x0, x1):
    """prism along +X from a sketch drawn in (y, z)."""
    pl = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
    return extrude(pl * sk, amount=x1 - x0, dir=(1, 0, 0))


def box(x0, x1, y0, y1, z0, z1):
    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN,) * 3)


def ycyl(x, z, r, y0, y1):
    return Pos(x, y0, z) * Rot(-90, 0, 0) * Cylinder(r, y1 - y0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def zcyl(x, y, r, z0, z1):
    return Pos(x, y, z0) * Cylinder(r, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def ycone(x, z, r0, r1, y0, y1):
    return Pos(x, y0, z) * Rot(-90, 0, 0) * Cone(r0, r1, y1 - y0, align=(Align.CENTER, Align.CENTER, Align.MIN))


def rrect(cx, cy, w, h, r):
    return Pos(cx, cy) * RectangleRounded(w, h, r)


def poly(pts):
    return Polygon(*pts, align=None)


def teardrop(cx, cy, r, toward=(0, -1)):
    """circle plus a 45 degree point, so a horizontal boss or hole prints without support."""
    tx, ty = toward
    d = r * math.sqrt(2)
    nx, ny = -ty, tx
    tri = poly([(cx + nx * r / math.sqrt(2), cy + ny * r / math.sqrt(2)), (cx + tx * d, cy + ty * d),
                (cx - nx * r / math.sqrt(2), cy - ny * r / math.sqrt(2))])
    return Pos(cx, cy) * Circle(r) + tri


FILLET_LOG = []


def soften(shape, op, r, edges, what):
    try:
        out = shape.fillet(r, edges) if op == "fillet" else shape.chamfer(r, None, edges)
        FILLET_LOG.append({"feature": what, "op": op, "size": r, "edges": len(edges), "ok": True})
        return out
    except Exception as exc:  # noqa: BLE001
        FILLET_LOG.append({"feature": what, "op": op, "size": r, "edges": len(edges), "ok": False,
                           "error": str(exc)[:120]})
        return shape


def edges_at(shape, axis, lo, hi):
    return shape.edges().filter_by_position(axis, lo, hi)


def color(hexstr):
    h = hexstr.lstrip("#")
    return Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)


# derived positions
def derived():
    d = SimpleNamespace()
    d.floor_in = P.wall
    d.tray_z0 = P.wall + P.tray_gap
    d.tray_z1 = d.tray_z0 + P.tray_t
    d.back_in = P.D - P.rebate_d
    fx, fz = P.finger_c
    d.floor_top = fz - P.tunnel_in[1] / 2
    d.entry_y = -P.lip_proud
    d.stop_y = d.entry_y + P.tunnel_len
    d.win_y = d.stop_y - P.window_from_stop
    d.max_top = d.floor_top - P.ic_below_floor - P.max_ic[2]
    d.max_bot = d.max_top - P.max_t
    d.floor_bot_sensor = d.floor_top - P.floor_over_sensor
    cx, cz = P.cam_c
    d.cam_board_y0 = P.cam_lens_behind_face + (P.cam_depth - P.cam_board[2])
    d.cam_board_top = cz + P.cam_lens_from_top
    d.cam_board_cz = d.cam_board_top - P.cam_board[1] / 2
    hz_top = d.cam_board_top - P.cam_hole_from_top
    d.cam_posts = [(cx + sx * P.cam_holes[0] / 2, z) for sx in (-1, 1) for z in (hz_top, hz_top - P.cam_holes[1])]
    gx, gz = P.grille_c
    d.spk_bosses = [(gx + P.spk_boss_r * math.cos(math.radians(a)), gz + P.spk_boss_r * math.sin(math.radians(a)))
                    for a in (90, 210, 330)]
    d.cradle_bosses = [(fx - P.cradle_boss_dx, fz), (fx + P.cradle_boss_dx, fz)]
    i = P.corner_boss_inset
    d.corner_bosses = [(i, i), (P.W - i, i), (i, P.H - i), (P.W - i, P.H - i)]
    d.top_in = P.H - P.wall
    d.dongle_z1 = d.top_in - P.dongle_gap_top
    d.dongle_z0 = d.dongle_z1 - P.dongle[2]
    d.led_flange_z0 = P.H + P.led_proud - 8.6
    d.hub_z0 = d.tray_z1 + P.hub_standoff
    d.vis_z0 = d.tray_z1 + P.vision_standoff
    d.cable_z = d.hub_z0 + P.hub[2] + 1.6
    d.cap_axis = (114.5, 7.0)
    return d


DV = derived()


# printed parts
def shell():
    W, H, D, t = P.W, P.H, P.D, P.wall
    body = yp(rrect(W / 2, H / 2, W, H, P.corner_r), 0, D)
    body = soften(body, "chamfer", P.front_chamfer, edges_at(body, Axis.Y, -0.01, 0.01), "shell front perimeter")
    body = soften(body, "fillet", P.back_fillet, edges_at(body, Axis.Y, D - 0.01, D + 0.01), "shell back rim")
    body -= yp(rrect(W / 2, H / 2, W - 2 * t, H - 2 * t, P.corner_r - t), t, D + 1)
    o = P.rebate_w
    body -= yp(rrect(W / 2, H / 2, W - 2 * o, H - 2 * o, P.corner_r - o), DV.back_in, D + 1)

    adds = []
    for (x, z) in DV.corner_bosses:
        adds.append(ycyl(x, z, P.boss_d / 2, t - 0.5, DV.back_in))
    # tray rails, grown from the face so they print straight up
    for x0, x1 in ((t - 0.5, t + P.rail_w), (W - t - P.rail_w, W - t + 0.5)):
        adds.append(box(x0, x1, t - 0.5, DV.back_in, DV.tray_z0 - P.rail_t, DV.tray_z0))
        adds.append(box(x0, x1, t - 0.5, DV.back_in, DV.tray_z1 + P.slide_fit, DV.tray_z1 + P.slide_fit + P.rail_t))
    # face bosses
    for (x, z) in DV.cradle_bosses:
        adds.append(ycyl(x, z, P.boss_d / 2, t - 0.5, t + P.cradle_boss_h))
    spk_boss_top = t + P.spk_rim_t + 5.2
    for (x, z) in DV.spk_bosses:
        adds.append(ycyl(x, z, P.boss_d / 2, t - 0.5, spk_boss_top))
    for (x, z) in DV.cam_posts:
        adds.append(ycyl(x, z, P.cam_post_d / 2, t - 0.5, DV.cam_board_y0))
    gx, gz = P.grille_c
    seat_r0, seat_r1 = P.spk_d / 2 + 0.3, P.spk_d / 2 + 1.7
    adds.append(yp(Pos(gx, gz) * Circle(seat_r1) - Pos(gx, gz) * Circle(seat_r0), t - 0.5, t + 3.0))
    # mic pocket hanging from the top wall: rails from the face, lips under the dongle
    mx, my = P.mic_c
    dw, dl, dh = P.dongle
    gap = P.min_clear
    x_in0, x_in1 = mx - dw / 2 - gap, mx + dw / 2 + gap
    y_back = my + dl / 2
    lip_z0 = DV.dongle_z0 - 1.8
    for x0, x1 in ((x_in0 - 1.6, x_in0), (x_in1, x_in1 + 1.6)):
        adds.append(box(x0, x1, t - 0.5, y_back, lip_z0, DV.top_in + 0.5))
    adds.append(box(x_in0 - 0.1, x_in0 + 1.5, t - 0.5, y_back, lip_z0, DV.dongle_z0))
    adds.append(box(x_in1 - 1.5, x_in1 + 0.1, t - 0.5, y_back, lip_z0, DV.dongle_z0))
    y_stop = my - dl / 2 - gap
    span = DV.top_in + 0.5 - lip_z0
    adds.append(xp(poly([(y_stop - span, DV.top_in + 0.5), (y_stop, DV.top_in + 0.5), (y_stop, lip_z0)]),
                   x_in0 - 0.1, x_in1 + 0.1))
    # led boss on the top wall, teardrop toward the face so it prints face down
    lx, ly = P.led_c
    adds.append(zp(teardrop(lx, ly, 4.5, (0, -1)), DV.led_flange_z0, DV.top_in + 0.5))
    # lead grommet ring on the floor
    hx, hy = P.lead_hole
    adds.append(zp(teardrop(hx, hy, 5.5, (0, -1)), t - 0.5, t + 2.0))
    # feet: front face sloped 45 degrees so they print face down
    for fx in (22.0, P.W - 22.0):
        for fy in (8.0, 64.0):
            prof = poly([(fy, 0.5), (fy + P.foot_l, 0.5), (fy + P.foot_l, -P.foot_h), (fy + P.foot_h, -P.foot_h),
                         (fy, 0.0)])
            foot = xp(prof, fx - P.foot_w / 2, fx + P.foot_w / 2)
            bottom = edges_at(foot, Axis.Z, -P.foot_h - 0.01, -P.foot_h + 0.01)
            foot = soften(foot, "fillet", 1.0, bottom, "foot bottom edges")
            pad_y = fy + P.foot_h + (P.foot_l - P.foot_h) / 2
            foot -= zp(teardrop(fx, pad_y, P.pad_d / 2, (0, 1)), -P.foot_h - 1, -P.foot_h + P.pad_depth)
            adds.append(foot)
    for a in adds:
        body += a

    cuts = []
    for (x, z) in DV.corner_bosses:
        cuts.append(ycyl(x, z, P.insert_pilot / 2, DV.back_in - P.insert_depth, DV.back_in + 1))
    for (x, z) in DV.cradle_bosses:
        top = t + P.cradle_boss_h
        cuts.append(ycyl(x, z, P.insert_pilot / 2, top - P.insert_depth, top + 1))
    for (x, z) in DV.spk_bosses:
        cuts.append(ycyl(x, z, P.insert_pilot / 2, spk_boss_top - P.insert_depth, spk_boss_top + 1))
    for (x, z) in DV.cam_posts:
        cuts.append(ycyl(x, z, P.m2_pilot / 2, DV.cam_board_y0 - 6.0, DV.cam_board_y0 + 1))
    # speaker grille
    holes = None
    rows = int(P.grille_field_d / (P.grille_pitch * math.sin(math.radians(60)))) + 2
    for j in range(-rows, rows + 1):
        zz = j * P.grille_pitch * math.sin(math.radians(60))
        off = (P.grille_pitch / 2) if j % 2 else 0.0
        for i in range(-rows, rows + 1):
            xx = i * P.grille_pitch + off
            if math.hypot(xx, zz) <= (P.grille_field_d - P.grille_hole_d) / 2:
                c = Pos(gx + xx, gz + zz) * Circle(P.grille_hole_d / 2)
                holes = c if holes is None else holes + c
    cuts.append(yp(holes, -1, t + 0.5))
    # camera bezel hole, finger port
    cx, cz = P.cam_c
    cuts.append(ycyl(cx, cz, P.bezel_od / 2 + P.bezel_fit, -1, t + 0.01))
    fx, fz = P.finger_c
    cuts.append(yp(rrect(fx, fz, P.port_w, P.port_h, P.port_r), -1, t + 0.5))
    # debossed id, drawn on the front plane so it reads from the front
    cuts.append(label_solid())
    # mic holes and led hole through the top wall
    for k in range(P.mic_holes):
        x = mx + (k - (P.mic_holes - 1) / 2) * P.mic_pitch
        cuts.append(zcyl(x, my, P.mic_hole_d / 2, DV.top_in - 1, P.H + 1))
    cuts.append(zcyl(lx, ly, P.led_hole_d / 2, DV.led_flange_z0, P.H + 1))
    cuts.append(zcyl(lx, ly, P.led_cb_d / 2, DV.led_flange_z0 - 1, DV.led_flange_z0 + 1.0))
    # lead hole with chamfered lip
    cuts.append(zcyl(hx, hy, P.lead_hole_d / 2, -1, t + 3))
    cuts.append(Pos(hx, hy, -0.01) * Cone(P.lead_hole_d / 2 + 0.8, P.lead_hole_d / 2, 0.8,
                                         align=(Align.CENTER, Align.CENTER, Align.MIN)))
    for c in cuts:
        body -= c
    return body


def label_solid():
    probe = Text("K", 10, font_path=FONT, align=(Align.MIN, Align.MIN))
    cap10 = probe.bounding_box().size.Y
    size = 10 * P.label_cap / cap10
    txt = Text(P.label, size, font_path=FONT, align=(Align.MIN, Align.MIN))
    return yp(Pos(P.label_x, P.label_base) * txt, -1, P.label_depth)


def rear_plate():
    W, H, D = P.W, P.H, P.D
    y0 = D
    y1 = D + P.plate_t - P.spigot_t
    plate = yp(rrect(W / 2, H / 2, W, H, P.corner_r), y0, y1)
    plate = soften(plate, "fillet", 1.0, edges_at(plate, Axis.Y, y1 - 0.01, y1 + 0.01), "rear plate outer edge")
    plate = soften(plate, "fillet", 0.5, edges_at(plate, Axis.Y, y0 - 0.01, y0 + 0.01), "rear plate parting edge")
    o = P.rebate_w + P.plate_fit
    plate += yp(rrect(W / 2, H / 2, W - 2 * o, H - 2 * o, P.corner_r - o), y0 - P.spigot_t, y0 + 0.5)
    kx, kz = P.keyhole_c
    bz = kz
    clamp_holes = [(kx - 11.0, bz), (kx + 11.0, bz)]
    for (x, z) in clamp_holes:
        plate += ycyl(x, z, P.boss_d / 2, y0 - P.spigot_t - 7.2, y0 - P.spigot_t + 0.5)
    cuts = []
    for (x, z) in DV.corner_bosses:
        cuts.append(ycyl(x, z, P.m3_clear / 2, y0 - 2, y1 + 1))
        cuts.append(ycone(x, z, P.m3_clear / 2, P.m3_csk_d / 2, y1 - (P.m3_csk_d - P.m3_clear) / 2, y1 + 0.01))
    for (x, z) in clamp_holes:
        cuts.append(ycyl(x, z, P.insert_pilot / 2, y1 - P.insert_depth, y1 + 1))
    # keyhole cable exit: round part passes the plug, the cable sits in the slot end
    cuts.append(ycyl(kx, kz, P.keyhole_d / 2, y0 - 2, y1 + 1))
    sw = P.cable_d + 0.4
    cuts.append(yp(Pos(kx, (kz + DV.cable_z) / 2) * Rectangle(sw, kz - DV.cable_z), y0 - 2, y1 + 1))
    cuts.append(ycyl(kx, DV.cable_z, sw / 2, y0 - 2, y1 + 1))
    # intake low, exhaust high
    for i in range(8):
        x = 100 + i * 6
        cuts.append(yp(Pos(x, 32) * RectangleRounded(P.slot_w, 20, P.slot_w / 2 - 0.01), y0 - 2, y1 + 1))
    for i in range(11):
        x = 45 + i * 6
        cuts.append(yp(Pos(x, 87) * RectangleRounded(P.slot_w, 22, P.slot_w / 2 - 0.01), y0 - 2, y1 + 1))
    # hangers: head hole and a slot upward
    for x in (22.0, P.W - 22.0):
        cuts.append(ycyl(x, 88, 4.5, y0 - 2, y1 + 1))
        cuts.append(yp(Pos(x, 92) * Rectangle(4.4, 8), y0 - 2, y1 + 1))
        cuts.append(ycyl(x, 96, 2.2, y0 - 2, y1 + 1))
    # capsule clip screws from inside, countersunk on the spigot face
    for (x, z) in clip_screws():
        cuts.append(ycyl(x, z, P.m3_clear / 2, y0 - 2, y1 + 1))
        cuts.append(ycone(x, z, P.m3_csk_d / 2, P.m3_clear / 2, y0 - P.spigot_t - 0.01,
                          y0 - P.spigot_t + (P.m3_csk_d - P.m3_clear) / 2))
    for c in cuts:
        plate -= c
    return plate


def clip_screws():
    return [(65.0, 13.0), (85.0, 13.0)]


def tray():
    t = P.wall
    x0, x1 = t + P.slide_fit, P.W - t - P.slide_fit
    y0, y1 = 5.0, DV.back_in
    z0, z1 = DV.tray_z0, DV.tray_z1
    tr = box(x0, x1, y0, y1, z0, z1)
    tr = soften(tr, "fillet", 2.0, tr.edges().filter_by(Axis.Z), "tray corners")
    adds = []
    for (x, y) in hub_holes():
        adds.append(zcyl(x, y, 2.5, z1 - 0.5, z1 + P.hub_standoff))
    for (x, y) in vision_holes():
        adds.append(zcyl(x, y, 2.5, z1 - 0.5, z1 + P.vision_standoff))
    ax0, ax1, ay0, ay1 = adapter_box()
    for gx0 in (ax0 - 3.3, ax1 + 0.3):
        adds.append(box(gx0, gx0 + 3.0, ay0 + 3, ay1 - 3, z1 - 0.5, z1 + 4.0))
    # cable tie anchor under the cable, behind the hub plug
    kx = P.keyhole_c[0]
    anchor = box(kx - 5, kx + 5, 86.5, 89.5, z1 - 0.5, DV.cable_z - P.cable_d / 2 - 0.2)
    anchor -= box(kx - 6, kx + 6, 87.0, 89.0, z1 + 1.0, z1 + 3.0)
    adds.append(anchor)
    for a in adds:
        tr += a
    for (x, y) in hub_holes() + vision_holes():
        tr -= zcyl(x, y, P.m2_pilot / 2, z1 - 1, z1 + 6)
    hx, hy = P.lead_hole
    tr -= zcyl(hx, hy, 4.0, z0 - 1, z1 + 1)
    return tr


def cradle():
    fx, fz = P.finger_c
    bw, bh = P.port_w - 2 * P.cradle_fit, P.port_h - 2 * P.cradle_fit
    y_front, y_back = DV.entry_y, DV.stop_y + P.end_wall
    body = yp(rrect(fx, fz, bw, bh, P.port_r - P.cradle_fit), y_front, y_back)
    body = soften(body, "fillet", P.lip_r, edges_at(body, Axis.Y, y_front - 0.01, y_front + 0.01), "cradle lip")
    # ears on the face bosses, with 45 degree gussets for printing
    ear_y0 = P.wall + P.cradle_boss_h
    ear_y1 = ear_y0 + P.ear_t
    half = bw / 2
    reach = P.cradle_boss_dx + 6.0
    for s in (-1, 1):
        a, b = fx + s * (half - 0.2), fx + s * reach
        pts = [(a, ear_y0), (b, ear_y0), (b, ear_y1), (a, ear_y1 + abs(b - a))]
        ear = zp(poly(pts if s > 0 else pts[::-1]), fz - 5, fz + 5)
        body += ear
    # tunnel: tapered entry, straight over the sensor, closed end stop
    w0, h0 = P.tunnel_in
    w1, h1 = P.tunnel_sensor
    ft = DV.floor_top
    y_t = DV.entry_y + P.taper_len
    s0 = front_plane(y_front - 0.1) * rrect(fx, ft + h0 / 2, w0, h0, 2.0)
    s1 = front_plane(y_t) * rrect(fx, ft + h1 / 2, w1, h1, 2.0)
    body -= loft([s0, s1])
    body -= yp(rrect(fx, ft + h1 / 2, w1, h1, 2.0), y_t - 0.01, DV.stop_y)
    # foam ring groove inside the entry, its upper face sloped for printing
    g0, g1, g2 = y_front + 2.0, y_front + 3.0, y_front + 4.0

    def tunnel_rect(y, grow):
        k = (y - y_front) / P.taper_len
        w, h = w0 + (w1 - w0) * k, h0 + (h1 - h0) * k
        return front_plane(y) * rrect(fx, ft + h / 2, w + 2 * grow, h + 2 * grow, 2.0 + grow)

    body -= loft([tunnel_rect(g0 - 0.2, -0.2), tunnel_rect(g1, 1.0)])
    body -= loft([tunnel_rect(g1 - 0.01, 1.0), tunnel_rect(g2, 1.0)])
    # sensor pocket below the floor, front edge sloped 45 degrees
    fb = DV.floor_bot_sensor
    pk = poly([(8.4 - 10, fb - 10), (8.4, fb), (y_back + 1, fb), (y_back + 1, fb - 10)])
    body -= xp(pk, fx - P.max_board / 2 - 0.4, fx + P.max_board / 2 + 0.4)
    ww, wl = P.window
    body -= box(fx - ww / 2, fx + ww / 2, DV.win_y - wl / 2, DV.win_y + wl / 2, fb - 0.5, ft + 0.5)
    # standoffs and pins for the board, pilots stop 0.3 under the floor top
    for (x, y) in max_holes():
        body += zcyl(x, y, 2.5, DV.max_top, fb + 0.3)
        body += zcyl(x, y, 1.5, DV.max_bot + 0.2, DV.max_top + 0.1)
        body -= zcyl(x, y, P.m2_pilot / 2, DV.max_bot, ft - 0.3)
    # screw holes in the ears, countersunk from behind
    for (x, z) in DV.cradle_bosses:
        body -= ycyl(x, z, P.m3_clear / 2, ear_y0 - 1, y_back + 10)
        body -= ycone(x, z, P.m3_clear / 2, P.m3_csk_d / 2, ear_y1 - 0.4, ear_y1 - 0.4 + (P.m3_csk_d - P.m3_clear) / 2)
        body -= ycyl(x, z, P.m3_csk_d / 2, ear_y1 - 0.4 + (P.m3_csk_d - P.m3_clear) / 2 - 0.01, y_back + 10)
    return body


def max_holes():
    fx = P.finger_c[0]
    p = P.max_hole_pitch / 2
    return [(fx + sx * p, DV.win_y + sy * p) for sx in (-1, 1) for sy in (-1, 1)]


def bezel():
    cx, cz = P.cam_c
    fw, fh, ft = P.bezel_flange
    t = P.wall
    b = ycyl(cx, cz, P.bezel_od / 2, 0, t + 0.01)
    flange = yp(rrect(cx, cz, fw, fh, 4.0), t, t + ft)
    flange = soften(flange, "fillet", 0.6, edges_at(flange, Axis.Y, t + ft - 0.01, t + ft + 0.01), "bezel flange")
    b += flange
    b -= ycyl(cx, cz, P.bezel_aperture / 2, -1, t + ft + 1)
    b -= ycone(cx, cz, P.bezel_aperture / 2 + 1.0 + 0.01, P.bezel_aperture / 2 - 0.01, -0.01, 1.02)
    for (x, z) in DV.cam_posts:
        b -= ycyl(x, z, P.cam_post_d / 2 + P.min_clear, t - 0.01, t + ft + 1)
    return b


def speaker_clamp():
    gx, gz = P.grille_c
    t = P.wall
    y_rim = t + P.spk_rim_t
    y_fl = t + P.spk_rim_t + 5.2
    lip = yp(Pos(gx, gz) * Circle(P.spk_d / 2 + 0.1) - Pos(gx, gz) * Circle(P.spk_d / 2 - 1.0), y_rim, y_fl + 0.1)
    fl = yp(Pos(gx, gz) * Circle(P.spk_boss_r + 4.0) - Pos(gx, gz) * Circle(P.spk_d / 2 - 1.0), y_fl, y_fl + P.spk_clamp_t)
    fl = soften(fl, "fillet", 0.8, edges_at(fl, Axis.Y, y_fl + P.spk_clamp_t - 0.01, y_fl + P.spk_clamp_t + 0.01),
                "speaker clamp back edges")
    c = lip + fl
    for (x, z) in DV.spk_bosses:
        c -= ycyl(x, z, P.m3_clear / 2, y_fl - 1, y_fl + P.spk_clamp_t + 1)
    return c


def cable_clamp():
    kx = P.keyhole_c[0]
    y0 = P.D + P.plate_t - P.spigot_t
    y1 = y0 + 3.0
    z0, z1 = DV.cable_z - 5.0, P.keyhole_c[1] + 12.0
    c = yp(rrect(kx, (z0 + z1) / 2, 30.0, z1 - z0, 3.0), y0, y1)
    c = soften(c, "fillet", 1.0, edges_at(c, Axis.Y, y1 - 0.01, y1 + 0.01), "cable clamp outer edge")
    c -= yp(Pos(kx, (z0 - 1 + DV.cable_z) / 2) * Rectangle(P.cable_d, DV.cable_z - z0 + 1), y0 - 1, y1 + 1)
    c -= ycyl(kx, DV.cable_z, P.cable_d / 2, y0 - 1, y1 + 1)
    for (x, z) in ((kx - 11.0, P.keyhole_c[1]), (kx + 11.0, P.keyhole_c[1])):
        c -= ycyl(x, z, P.m3_clear / 2, y0 - 1, y1 + 1)
        c -= ycone(x, z, P.m3_clear / 2, P.m3_csk_d / 2, y1 - (P.m3_csk_d - P.m3_clear) / 2, y1 + 0.01)
    return c


def capsule_local():
    """air sensor capsule in its own frame: axis +Z, open bottom at z = 0, cap on top."""
    R = P.cap_d / 2
    H = P.cap_h
    tube_r0, tube_r1 = 7.0, 8.2
    cap_z0 = H - 5.0
    tube = Cylinder(tube_r1, cap_z0, align=(Align.CENTER, Align.CENTER, Align.MIN)) - \
        Pos(0, 0, -1) * Cylinder(tube_r0, cap_z0 + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap = Pos(0, 0, cap_z0) * Cylinder(R, 5.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap = soften(cap, "chamfer", 1.0, edges_at(cap, Axis.Z, H - 0.01, H + 0.01), "capsule cap edge")
    body = tube + cap
    for zt in (cap_z0 - 2.0, cap_z0 - 11.0, cap_z0 - 20.0):
        prof = poly([(tube_r1 - 0.3, zt), (R, zt - (R - tube_r1 + 0.3)), (R, zt - (R - tube_r1 + 0.3) - 1.5),
                     (R - 1.2, zt - (R - tube_r1 + 0.3) - 1.5), (R - 1.2, zt - (R - tube_r1 + 0.3) - 0.2),
                     (tube_r1 - 0.3, zt - 1.7 - 0.3)])
        body += revolve(Plane.XZ * prof, Axis.Z)
        for k in range(6):
            a = math.radians(30 + 60 * k)
            wz = zt - 6.0
            body -= Pos(tube_r1 * math.cos(a), tube_r1 * math.sin(a), wz) * \
                Rot(0, 90, math.degrees(a)) * Cylinder(2.0, 4.0)
    # board slot ribs, the lead hole and a knot pocket in the cap
    bw = P.sht31[0]
    for sx in (-1, 1):
        for sy in (-1, 1):
            body += Pos(sx * (bw / 2 - 0.6), sy * 1.3, 6.0) * Box(2.4, 1.0, cap_z0 - 6.0 + 0.1,
                                                                align=(Align.CENTER, Align.CENTER, Align.MIN))
    body -= Pos(0, 0, cap_z0 - 0.1) * Cylinder(4.0, 3.1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body -= Pos(0, 0, cap_z0) * Cylinder(P.lead_d / 2 + 0.15, 10, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return body


def capsule_place(shape):
    cy, cz = DV.cap_axis
    return Pos(92.0, cy, cz) * Rot(0, -90, 0) * shape


def capsule_clip():
    cy, cz = DV.cap_axis
    y0 = P.D + P.plate_t - P.spigot_t
    base = poly([(y0, 0.0), (y0 + 8.0, 0.0), (y0 + 8.0, 24.0), (y0, 24.0)])
    r0, r1 = P.cap_d / 2 + 0.1, P.cap_d / 2 + 0.1 + P.clip_t
    ring = Pos(cy, cz) * Circle(r1) - Pos(cy, cz) * Circle(r0)
    gapd = 60.0
    wedge = poly([(cy, cz), (cy + 40 * math.cos(math.radians(gapd)), cz + 40 * math.sin(math.radians(gapd))),
                  (cy + 40, cz), (cy + 40 * math.cos(math.radians(-gapd)), cz + 40 * math.sin(math.radians(-gapd)))])
    prof = base + ring - wedge - Pos(cy, cz) * Circle(r0)
    clip = xp(prof, 59.0, 91.0)
    clip = soften(clip, "fillet", 0.8, edges_at(clip, Axis.X, 58.99, 59.01) + edges_at(clip, Axis.X, 90.99, 91.01),
                  "capsule clip ends")
    for (x, z) in clip_screws():
        clip -= ycyl(x, z, P.insert_pilot / 2, y0 - 1, y0 + P.insert_depth)
    return clip


# bought parts (simple solids, right outline, height, holes, connectors)
def part(children):
    """children: list of (name, shape, colour)."""
    kids = []
    for name, shp, col in children:
        s = Compound(children=[shp]) if not isinstance(shp, Compound) else shp
        s.label, s.color = name, color(col)
        kids.append(s)
    return kids


def max30101():
    fx = P.finger_c[0]
    y = DV.win_y
    b = P.max_board / 2
    pcb = box(fx - b, fx + b, y - b, y + b, DV.max_bot, DV.max_top)
    for (x, yy) in max_holes():
        pcb -= zcyl(x, yy, P.max_hole_d / 2, DV.max_bot - 1, DV.max_top + 1)
    icw, icl, ich = P.max_ic
    ic = box(fx - icw / 2, fx + icw / 2, y - icl / 2, y + icl / 2, DV.max_top, DV.max_top + ich)
    qw, ql, qh = P.qwiic
    qs = [box(fx + s * b - (ql if s > 0 else 0), fx + s * b + (0 if s > 0 else ql), y - qw / 2, y + qw / 2,
              DV.max_bot - qh, DV.max_bot) for s in (-1, 1)]
    return part([("max30101_pcb", pcb, COL["red"]), ("max30101_ic", ic, COL["chip"]),
                 ("qwiic_a", qs[0], COL["black"]), ("qwiic_b", qs[1], COL["black"])])


def camera():
    cx, cz = P.cam_c
    bw, bh, bt = P.cam_board
    y0 = DV.cam_board_y0
    pcb = box(cx - bw / 2, cx + bw / 2, y0, y0 + bt, DV.cam_board_cz - bh / 2, DV.cam_board_cz + bh / 2)
    for (x, z) in DV.cam_posts:
        pcb -= ycyl(x, z, 1.1, y0 - 1, y0 + bt + 1)
    holder = box(cx - 7, cx + 7, P.cam_lens_behind_face + 3.0, y0, cz - 7, cz + 7)
    barrel = ycyl(cx, cz, P.cam_barrel_d / 2, P.cam_lens_behind_face, P.cam_lens_behind_face + 3.01)
    zb = DV.cam_board_cz - bh / 2
    conn = box(cx - 11, cx + 11, y0 + bt, y0 + bt + 2.5, zb + 0.5, zb + 6.0)
    return part([("ov5647_pcb", pcb, COL["cam_green"]), ("ov5647_holder", holder + barrel, COL["black"]),
                 ("ov5647_fpc_socket", conn, COL["black"])])


def ribbon():
    cx = P.cam_c[0]
    x0, x1 = cx - P.ribbon_w / 2, cx + P.ribbon_w / 2
    yb = DV.cam_board_y0 + P.cam_board[2] + 1.0
    zc = DV.cam_board_cz - P.cam_board[1] / 2 + 0.5
    zr = 66.0
    yv = vision_box()[2] - 3.0
    zcsi = DV.vis_z0 + P.vision[2] + 1.2
    segs = [box(x0, x1, yb, yb + 0.3, zr, zc), box(x0, x1, yb, yv + 0.3, zr, zr + 0.3),
            box(x0, x1, yv, yv + 0.3, zcsi, zr + 0.3), box(x0, x1, yv, yv + 3.0, zcsi, zcsi + 0.3)]
    r = segs[0]
    for s in segs[1:]:
        r += s
    length = (zc - zr) + (yv - yb) + (zr - zcsi) + 3.0
    return part([("csi_ribbon", r, COL["ribbon"])]), length


def vision_box():
    return (92.0, 132.0, 50.0, 70.0)


def vision_holes():
    x0, x1, y0, y1 = vision_box()
    return [(x0 + 2.5, y0 + 2.5), (x1 - 2.5, y0 + 2.5), (x0 + 2.5, y1 - 2.5), (x1 - 2.5, y1 - 2.5)]


def vision_stack():
    x0, x1, y0, y1 = vision_box()
    z0 = DV.vis_z0
    z1 = z0 + P.vision[2]
    pcb = box(x0, x1, y0, y1, z0, z1)
    for (x, y) in vision_holes():
        pcb -= zcyl(x, y, 1.1, z0 - 1, z1 + 1)
    under = box(100, 124, 54, 66, z0 - 1.5, z0)
    csi = box(103, 121, y0, y0 + 5, z1, z1 + 2.5)
    usb = box(x0 - 1.0, x0 + 6.3, 55.5, 64.5, z1, z1 + 3.2)
    xs0, xs1 = 102.0, 123.0
    sock = [box(xs0, xs1, 51.1, 53.6, z1, z1 + 8.5), box(xs0, xs1, 66.4, 68.9, z1, z1 + 8.5)]
    xz0 = z1 + 8.5
    xiao = box(xs0, xs1, 51.1, 68.9, xz0, xz0 + P.xiao[2])
    shield = box(109.0, 121.0, 53.0, 67.0, xz0 + P.xiao[2], xz0 + P.xiao[2] + 2.5)
    xusb = box(xs0 - 1.3, xs0 + 6.0, 55.5, 64.5, xz0 + P.xiao[2], xz0 + P.xiao[2] + 3.2)
    return part([("vision_ai_v2_pcb", pcb, COL["seeed_green"]), ("vision_ai_v2_parts", under + csi, COL["black"]),
                 ("vision_ai_v2_usb_c", usb, COL["steel"]), ("xiao_sockets", sock[0] + sock[1], COL["black"]),
                 ("xiao_nrf52840_pcb", xiao, COL["xiao_blue"]), ("xiao_shield", shield, COL["steel"]),
                 ("xiao_usb_c", xusb, COL["steel"])])


def usb_c_plug(x_face, y_c, z_c, direction):
    """overmoulded usb-c plug leaving a receptacle face; direction -1 = toward -X, +1 = toward +Y."""
    ow, oh, ol = P.plug_overmold
    if direction == -1:
        shp = box(x_face - ol, x_face, y_c - ow / 2, y_c + ow / 2, z_c - oh / 2, z_c + oh / 2)
    else:
        shp = box(x_face - ow / 2, x_face + ow / 2, y_c, y_c + ol, z_c - oh / 2, z_c + oh / 2)
    shp = soften(shp, "fillet", 1.5, shp.edges().filter_by(Axis.X if direction == -1 else Axis.Y), "usb plug body")
    return shp


def hub_box():
    return (22.0, 42.4, 33.0, 64.6)


def hub_holes():
    x0, x1, y0, y1 = hub_box()
    return [(x0 + 2.5, y0 + 2.5), (x1 - 2.5, y0 + 2.5), (x0 + 2.5, y1 - 2.5), (x1 - 2.5, y1 - 2.5)]


def hub():
    x0, x1, y0, y1 = hub_box()
    z0 = DV.hub_z0
    z1 = z0 + P.hub[2]
    pcb = box(x0, x1, y0, y1, z0, z1)
    for (x, y) in hub_holes():
        pcb -= zcyl(x, y, 1.25, z0 - 1, z1 + 1)
    chip = box(29.0, 35.0, 40.0, 46.0, z1, z1 + 1.0)
    kx = P.keyhole_c[0]
    usb = box(kx - 4.5, kx + 4.5, y1 - 6.6, y1 + 0.8, z1, z1 + 3.2)
    return part([("ch334f_pcb", pcb, COL["ada_blue"]), ("ch334f_chip", chip, COL["chip"]),
                 ("ch334f_usb_c", usb, COL["steel"])])


def adapter_box():
    return (10.0, 70.0, 6.0, 31.0)


def audio_adapter():
    x0, x1, y0, y1 = adapter_box()
    b = box(x0, x1, y0, y1, DV.tray_z1, DV.tray_z1 + P.adapter[2])
    b = soften(b, "fillet", 2.0, b.edges().filter_by(Axis.X), "adapter body")
    return part([("usb_audio_adapter", b, COL["black"])])


def speaker():
    gx, gz = P.grille_c
    t = P.wall
    r = P.spk_d / 2
    rim = ycyl(gx, gz, r, t, t + P.spk_rim_t) - ycone(gx, gz, r - 3.0, 7.0, t - 0.01, t + 1.6)
    basket = ycone(gx, gz, r - 2.0, 13.0, t + P.spk_rim_t, t + 8.6)
    magnet = ycyl(gx, gz, 13.0, t + 8.6, t + P.spk_depth)
    return part([("speaker_frame", rim + basket, COL["black"]), ("speaker_magnet", magnet, COL["steel"])])


def mic_dongle():
    mx, my = P.mic_c
    dw, dl, dh = P.dongle
    z0, z1 = DV.dongle_z0, DV.dongle_z1
    body = box(mx - dw / 2, mx + dw / 2, my - dl / 2, my + dl / 2, z0, z1)
    body = soften(body, "fillet", 1.5, body.edges().filter_by(Axis.Z), "dongle body")
    for k in range(5):
        body -= zcyl(mx - 4 + 2 * k, my, 0.4, z1 - 0.3, z1 + 1)
    zc = (z0 + z1) / 2
    plug = box(mx - 6, mx + 6, my + dl / 2, my + dl / 2 + 12, zc - 2.25, zc + 2.25)
    return part([("usb_mic_dongle", body, COL["black"]), ("usb_mic_plug", plug, COL["steel"])])


def mic_pigtail():
    mx, my = P.mic_c
    y0 = my + P.dongle[1] / 2 + 12
    b = box(mx - 7.25, mx + 7.25, y0, y0 + 18, DV.dongle_z0, DV.dongle_z1)
    return part([("usb_a_pigtail_socket", b, COL["black"])])


def uv_led():
    lx, ly = P.led_c
    z0 = DV.led_flange_z0
    dome = Pos(lx, ly, z0 + 6.1) * Sphere(2.5) - box(lx - 3, lx + 3, ly - 3, ly + 3, z0, z0 + 6.1)
    body = zcyl(lx, ly, P.led_cb_d / 2, z0, z0 + 1.0) + zcyl(lx, ly, 2.5, z0 + 1.0, z0 + 6.1) + dome
    legs = box(lx - 1.52, lx - 1.02, ly - 0.25, ly + 0.25, z0 - 25, z0) + box(lx + 1.02, lx + 1.52, ly - 0.25,
                                                                               ly + 0.25, z0 - 25, z0)
    return part([("uv_led_365nm", body, COL["led"]), ("uv_led_leads", legs, COL["steel"])])


def sht31_local():
    w, h, t = P.sht31
    pcb = Pos(0, 0, 25.0 - h / 2) * Box(w, t, h) - Pos(0, 0, 25.0 - h + 2.5) * Rot(90, 0, 0) * Cylinder(1.25, 3)
    chip = Pos(0, t / 2 + 0.45, 25.0 - h / 2 - 3) * Box(2.5, 0.9, 2.5)
    return pcb, chip


def sht31():
    pcb, chip = sht31_local()
    return part([("sht31d_pcb", capsule_place(pcb), COL["ada_blue"]), ("sht31d_sensor", capsule_place(chip), COL["chip"])])


def sweep_path(pts, r, radius):
    from build123d import FilletPolyline, sweep
    path = FilletPolyline(*pts, radius=radius)
    start = Vector(*pts[0])
    tangent = (Vector(*pts[1]) - start).normalized()
    prof = Plane(origin=start, z_dir=tangent) * Circle(r)
    return sweep(prof, path=path), path.length


def usb_cable():
    kx = P.keyhole_c[0]
    y0 = hub_box()[3] + 0.8 + P.plug_overmold[2]
    plug = usb_c_plug(kx, hub_box()[3] + 0.8, DV.cable_z, +1)
    pts = [(kx, y0, DV.cable_z), (kx, 135.0, DV.cable_z), (kx, 135.0, -P.foot_h + P.cable_d / 2)]
    c, _ = sweep_path(pts, P.cable_d / 2, 12.0)
    return part([("usb_c_plug_hub", plug, COL["black"])]), part([("usb_c_cable", c, COL["cable"])])


def sensor_lead():
    cy, cz = DV.cap_axis
    hx, hy = P.lead_hole
    x_board = 92.0 - 25.0
    pts = [(x_board, cy, cz), (hx, cy, cz), (hx, cy, -4.0), (hx, hy, -4.0), (hx, hy, DV.tray_z1 + 4.0)]
    c, length = sweep_path(pts, P.lead_d / 2, 4.0)
    return part([("sht31_lead", c, COL["cable"])]), length


# assembly
@dataclass
class Item:
    name: str
    shape: object
    kind: str  # printed | bought
    colour: str = "#888888"
    flexible: bool = False
    print_rot: tuple = (0, 0, 0)
    material: str = "PETG"
    note: str = ""
    children: list = field(default_factory=list)


CONTACTS = {
    ("speaker", "shell"), ("speaker", "speaker_clamp"), ("camera_ov5647", "shell"), ("camera_bezel", "shell"),
    ("max30101", "finger_cradle"), ("finger_cradle", "shell"), ("hub_ch334f", "tray"), ("vision_stack", "tray"),
    ("audio_adapter", "tray"), ("usb_plug_hub", "hub_ch334f"), ("usb_plug_vision", "vision_stack"),
    ("usb_plug_xiao", "vision_stack"), ("usb_cable", "usb_plug_hub"), ("usb_cable", "rear_plate"),
    ("usb_cable", "cable_clamp"), ("usb_cable", "tray"), ("csi_ribbon", "camera_ov5647"),
    ("csi_ribbon", "vision_stack"), ("mic_dongle", "shell"), ("mic_pigtail", "mic_dongle"), ("uv_led", "shell"),
    ("rear_plate", "shell"), ("cable_clamp", "rear_plate"), ("capsule_clip", "rear_plate"),
    ("sensor_capsule", "capsule_clip"), ("sht31", "sensor_capsule"), ("sensor_lead", "sensor_capsule"),
    ("sensor_lead", "sht31"), ("tray", "shell"), ("speaker_clamp", "shell"),
}


def assemble():
    items = []

    def printed(name, shp, col, rot, material="PETG", note=""):
        shp.label, shp.color = name, color(col)
        items.append(Item(name, shp, "printed", col, print_rot=rot, material=material, note=note))

    def bought(name, kids, flexible=False, note=""):
        comp = Compound(children=kids)
        comp.label = name
        items.append(Item(name, comp, "bought", flexible=flexible, note=note, children=kids))

    printed("shell", shell(), COL["shell"], (90, 0, 0), note="front face down")
    printed("rear_plate", rear_plate(), COL["plate"], (-90, 0, 0), note="outer face down")
    printed("tray", tray(), COL["tray"], (0, 0, 0), note="flat, standoffs up")
    printed("finger_cradle", cradle(), COL["black"], (-90, 0, 0), material="PETG black",
            note="end stop down, tunnel axis vertical")
    printed("camera_bezel", bezel(), COL["black"], (-90, 0, 0), material="PETG black", note="flange down")
    printed("speaker_clamp", speaker_clamp(), COL["dark"], (-90, 0, 0), note="flange down")
    printed("cable_clamp", cable_clamp(), COL["dark"], (-90, 0, 0), note="outer face down")
    printed("sensor_capsule", capsule_place(capsule_local()), COL["white"], None, material="ASA white",
            note="cap down, open end up")
    printed("capsule_clip", capsule_clip(), COL["white"], (0, -90, 0), material="ASA white", note="on one end face")

    bought("max30101", max30101())
    bought("camera_ov5647", camera())
    rib, rib_len = ribbon()
    bought("csi_ribbon", rib, flexible=True, note=f"{rib_len:.0f} mm path of a {P.ribbon_len:.0f} mm ribbon")
    bought("vision_stack", vision_stack())
    x0 = vision_box()[0]
    zv = DV.vis_z0 + P.vision[2] + 1.6
    zx = DV.vis_z0 + P.vision[2] + 8.5 + P.xiao[2] + 1.6
    bought("usb_plug_vision", part([("usb_c_plug_vision", usb_c_plug(x0 - 1.0, 60.0, zv, -1), COL["black"])]))
    bought("usb_plug_xiao", part([("usb_c_plug_xiao", usb_c_plug(102.0 - 1.3, 60.0, zx, -1), COL["black"])]))
    bought("hub_ch334f", hub())
    plug, cab = usb_cable()
    bought("usb_plug_hub", plug)
    bought("usb_cable", cab, flexible=True)
    bought("audio_adapter", audio_adapter())
    bought("speaker", speaker())
    bought("mic_dongle", mic_dongle())
    bought("mic_pigtail", mic_pigtail())
    bought("uv_led", uv_led())
    bought("sht31", sht31())
    lead, lead_len = sensor_lead()
    bought("sensor_lead", lead, flexible=True, note=f"{lead_len:.0f} mm modelled of a 120 mm lead")
    return items, {"ribbon_path_mm": round(rib_len, 1), "sensor_lead_path_mm": round(lead_len, 1)}


# checks
def tess(shape, tol=0.05):
    v, f = shape.tessellate(tol, 0.3)
    return np.array([[p.X, p.Y, p.Z] for p in v]), np.array(f, dtype=int)


def print_shape(it):
    if it.name == "sensor_capsule":
        return Rot(180, 0, 0) * capsule_local()
    return Rot(*it.print_rot) * it.shape


def overhang_area(shape):
    v, f = tess(shape, 0.1)
    v[:, 2] -= v[:, 2].min()
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    zmin = np.minimum(np.minimum(a[:, 2], b[:, 2]), c[:, 2])
    mask = (nz < -0.75) & (zmin > 0.2)
    return float(area[mask].sum())


def print_estimate(shape, material):
    V = shape.volume
    A = shape.area
    skin = min(V, A * 0.8)
    extruded = skin + 0.15 * (V - skin)
    density = 1.07 if "ASA" in material else 1.27
    hours = extruded / 7.0 * 1.3 / 3600 + 0.1
    return {"volume_cm3": round(V / 1000, 2), "extruded_cm3": round(extruded / 1000, 2),
            "filament_g": round(extruded / 1000 * density, 1), "filament_m": round(extruded / 2.405 / 1000, 2),
            "print_h": round(hours, 2), "material": material}


def bb(shape):
    b = shape.bounding_box()
    return [round(b.min.X, 2), round(b.min.Y, 2), round(b.min.Z, 2)], [round(b.max.X, 2), round(b.max.Y, 2),
                                                                         round(b.max.Z, 2)]


def bbox_near(a, b, pad):
    (a0, a1), (b0, b1) = a, b
    return all(a0[i] - pad <= b1[i] and b0[i] - pad <= a1[i] for i in range(3))


def chord(shape, p, d, at):
    """length of the solid section along a line through p in direction d that contains point `at`."""
    p, d = Vector(*p), Vector(*d).normalized()
    e = Edge.make_line(p - d * 200, p + d * 200)
    hit = shape.intersect(e)
    if hit is None:
        return None
    best = None
    for seg in hit.edges():
        s0, s1 = seg.position_at(0), seg.position_at(1)
        lo, hi = sorted(((s0 - p).dot(d), (s1 - p).dot(d)))
        t_at = (Vector(*at) - p).dot(d)
        if lo - 1e-3 <= t_at <= hi + 1e-3:
            best = hi - lo
    return best


def run_checks(items, extra):
    res = {"date": date.today().isoformat(), "units": "mm", "min_clearance_required": P.min_clear}
    byname = {it.name: it for it in items}
    boxes = {it.name: bb(it.shape) for it in items}
    failures = []

    pod = [it for it in items if it.name not in ("usb_cable", "sensor_lead")]
    lo = np.min([boxes[it.name][0] for it in pod], axis=0)
    hi = np.max([boxes[it.name][1] for it in pod], axis=0)
    enc = [byname[n] for n in ("shell", "rear_plate", "finger_cradle", "uv_led", "cable_clamp")]
    elo = np.min([boxes[it.name][0] for it in enc], axis=0)
    ehi = np.max([boxes[it.name][1] for it in enc], axis=0)
    res["envelope"] = {
        "enclosure_mm": [round(float(x), 1) for x in ehi - elo],
        "enclosure_note": "shell + rear plate + feet + finger lip + LED tip + cable clamp, X x Y(depth) x Z",
        "with_stowed_capsule_mm": [round(float(x), 1) for x in hi - lo],
        "shell_mm": [P.W, P.D, P.H],
    }
    res["part_count"] = {"printed": sum(it.kind == "printed" for it in items),
                         "bought_models": sum(it.kind == "bought" for it in items), "total": len(items)}

    parts = {}
    for it in items:
        entry = {"kind": it.kind, "bbox_min": boxes[it.name][0], "bbox_max": boxes[it.name][1],
                 "volume_mm3": round(it.shape.volume, 1)}
        if it.kind == "printed":
            ps = print_shape(it)
            pb = ps.bounding_box().size
            entry["print_bbox_mm"] = [round(pb.X, 1), round(pb.Y, 1), round(pb.Z, 1)]
            entry["fits_220_bed"] = bool(pb.X <= 220 and pb.Y <= 220 and pb.Z <= 250)
            entry["print_orientation"] = it.note
            entry["solids"] = len(it.shape.solids())
            if entry["solids"] != 1:
                failures.append(f"{it.name} is {entry['solids']} solids, not one")
            entry["estimate"] = print_estimate(it.shape, it.material)
            entry["overhang_area_mm2_steeper_than_45deg"] = round(overhang_area(ps), 1)
            if not entry["fits_220_bed"]:
                failures.append(f"{it.name} does not fit the bed")
        parts[it.name] = entry
    res["parts"] = parts
    res["print_totals"] = {
        "filament_g": round(sum(p["estimate"]["filament_g"] for p in parts.values() if "estimate" in p), 1),
        "print_h": round(sum(p["estimate"]["print_h"] for p in parts.values() if "estimate" in p), 1),
        "method": "extruded = min(V, 0.8 mm skin x area) + 15% infill of the rest; 7 mm3/s x 1.3 overhead + 6 min",
    }

    pairs = []
    adjacency = {it.name: set() for it in items}
    contact_dist = {}
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if not bbox_near(boxes[a.name], boxes[b.name], 0.5):
                continue
            inter = a.shape.intersect(b.shape)
            iv = inter.volume if inter is not None else 0.0
            dist = a.shape.distance_to(b.shape)
            key = (a.name, b.name) if (a.name, b.name) in CONTACTS else (b.name, a.name)
            declared = key in CONTACTS
            need_clear = (not declared and not a.flexible and not b.flexible
                          and "bought" in (a.kind, b.kind))
            ok = iv < 0.01 and (dist >= P.min_clear - 1e-6 if need_clear else True)
            pairs.append({"a": a.name, "b": b.name, "distance": round(dist, 3), "intersection_mm3": round(iv, 4),
                          "declared_contact": declared, "clearance_checked": need_clear, "ok": ok})
            if not ok:
                failures.append(f"{a.name} / {b.name}: distance {dist:.3f}, intersection {iv:.4f}")
            if dist <= 0.25:
                adjacency[a.name].add(b.name)
                adjacency[b.name].add(a.name)
            if declared:
                contact_dist[key] = dist
    res["pairs_checked"] = len(pairs)
    res["pairs"] = pairs
    bought_pairs = [p for p in pairs if p["clearance_checked"]]
    res["min_clearance_found"] = min((p["distance"] for p in bought_pairs), default=None)

    missing = [f"{a}/{b}" for (a, b) in CONTACTS if contact_dist.get((a, b), 99) > 0.25]
    seen, stack = {"shell"}, ["shell"]
    while stack:
        n = stack.pop()
        for m in adjacency[n] - seen:
            seen.add(m)
            stack.append(m)
    floating = sorted(set(byname) - seen)
    res["mounting"] = {"declared_contacts": len(CONTACTS), "contacts_not_touching": missing,
                       "floating_parts": floating}
    failures += [f"contact not touching: {m}" for m in missing] + [f"floating: {f}" for f in floating]

    # wall thickness at the thinnest designed features, measured on the solids
    sh, cr, bz, cap = byname["shell"].shape, byname["finger_cradle"].shape, byname["camera_bezel"].shape, \
        byname["sensor_capsule"].shape
    fx = P.finger_c[0]
    mx, my = P.mic_c
    cy, cz = DV.cap_axis
    walls = {
        "shell side wall": chord(sh, (0, 50, 55), (1, 0, 0), (1.2, 50, 55)),
        "rebate lip": chord(sh, (0, 91.5, 55), (1, 0, 0), (0.6, 91.5, 55)),
        "cradle floor over sensor": chord(cr, (fx, DV.win_y + 3.0, 0), (0, 0, 1), (fx, DV.win_y + 3.0,
                                                                                    DV.floor_top - 0.5)),
        "cradle floor at foam groove": chord(cr, (fx, DV.entry_y + 3.5, 0), (0, 0, 1), (fx, DV.entry_y + 3.5,
                                                                                       DV.floor_top - 1.6)),
        "bezel tube wall": chord(bz, (0, 1.6, P.cam_c[1]), (1, 0, 0), (P.cam_c[0] + 9.5, 1.6, P.cam_c[1])),
        "mic pocket rail": chord(sh, (0, 40, 104), (1, 0, 0), (mx - P.dongle[0] / 2 - 1.0, 40, 104)),
        "capsule tube wall": chord(cap, (76, 0, cz), (0, 1, 0), (76, cy + 7.6, cz)),
        "capsule louvre (normal to cone)": chord(cap, (92 - 23.9, cy + 10.0, cz), (-math.sqrt(0.5), math.sqrt(0.5), 0),
                                                 (92 - 23.9, cy + 10.0, cz)),
    }
    walls = {k: (round(v, 2) if v else None) for k, v in walls.items()}
    res["wall_thickness_mm"] = walls
    measured = [v for v in walls.values() if v]
    res["min_wall_mm"] = min(measured) if measured else None
    for k, v in walls.items():
        if v is None or v < 0.8:
            failures.append(f"wall {k}: {v}")

    # zones that must stay empty for usb plug bends
    zones = {"vision_plug_bend": box(71.0 - P.usb_bend, 71.0, 54, 66, 18.3, 25.3),
             "xiao_plug_bend": box(80.7 - P.usb_bend, 80.7, 54, 66, 28.0, 35.0)}
    zres = {}
    for zn, zs in zones.items():
        hits = [it.name for it in items if not it.flexible and (lambda r: r is not None and r.volume > 0.01)(
            it.shape.intersect(zs))]
        zres[zn] = hits
        if hits:
            failures.append(f"{zn} blocked by {hits}")
    res["usb_bend_zones_blocked_by"] = zres
    res["cables"] = extra
    if extra["ribbon_path_mm"] > P.ribbon_len:
        failures.append("ribbon too short")
    res["fillets"] = FILLET_LOG
    failures += [f"fillet failed: {f['feature']}" for f in FILLET_LOG if not f["ok"]]
    res["failures"] = failures
    res["passed"] = not failures
    return res


# exports
def export_all(items):
    for d in ("step", "print", "drawings"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    asm = Compound(children=[it.shape for it in items])
    asm.label = "pod_k01"
    export_step(asm, str(OUT / "step" / "pod_k01_assembly.step"))
    for it in items:
        if it.kind != "printed":
            continue
        one = Compound(children=[it.shape])
        one.label = it.name
        export_step(one, str(OUT / "step" / f"{it.name}.step"))
        m = Mesher()
        ps = print_shape(it)
        b = ps.bounding_box()
        ps = Pos(-b.center().X, -b.center().Y, -b.min.Z) * ps
        m.add_shape(ps, linear_deflection=0.03, angular_deflection=0.25)
        m.write(str(OUT / "print" / f"{it.name}.3mf"))


def rgb_of(shape):
    c = shape.color
    if c is None:
        return [0.5, 0.5, 0.5]
    try:
        return [float(v) for v in list(c)[:3]]
    except TypeError:
        rgba = c.wrapped.GetRGB()
        return [rgba.Red(), rgba.Green(), rgba.Blue()]


def export_render_meshes(items):
    rd = BUILD / "render"
    rd.mkdir(parents=True, exist_ok=True)
    manifest = []
    secx = (P.finger_c[0] + P.cam_c[0]) / 2
    cutter = box(secx, 400, -200, 300, -200, 300)
    for it in items:
        subs = it.children if it.kind == "bought" else [it.shape]
        for k, s in enumerate(subs):
            fn = f"{it.name}_{k}.stl"
            export_stl(s, str(rd / fn), tolerance=0.05, angular_tolerance=0.3)
            sec = None
            try:
                cut = s - cutter
                if cut.volume > 1e-3:
                    sec = f"sec_{it.name}_{k}.stl"
                    export_stl(cut, str(rd / sec), tolerance=0.05, angular_tolerance=0.3)
            except Exception:  # noqa: BLE001
                pass
            rgb = rgb_of(s)
            manifest.append({"item": it.name, "kind": it.kind, "file": fn, "section": sec, "rgb": rgb})
        if it.kind == "printed":
            fn = f"print_{it.name}.stl"
            ps = print_shape(it)
            b = ps.bounding_box()
            export_stl(Pos(-b.center().X, -b.center().Y, -b.min.Z) * ps, str(rd / fn), tolerance=0.05,
                       angular_tolerance=0.3)
            manifest.append({"item": it.name, "kind": "print", "file": fn, "rgb": rgb_of(it.shape),
                             "size": [b.size.X, b.size.Y, b.size.Z]})
    (rd / "manifest.json").write_text(json.dumps(manifest, indent=1))


def step_readback(path):
    from build123d import import_step
    shp = import_step(str(path))
    leaves = []

    def walk(node):
        kids = list(getattr(node, "children", []) or [])
        if not kids:
            leaves.append(node)
        for k in kids:
            walk(k)

    for c in shp.children:
        walk(c)
    return {"top_level_children": len(shp.children), "named": sum(bool(c.label) for c in shp.children),
            "leaf_shapes": len(leaves), "leaf_coloured": sum(lf.color is not None for lf in leaves)}


def file_report(res):
    files, failures = [], []
    for f in sorted(OUT.rglob("*")):
        if f.is_file() and f.name != "checks.json":
            kb = round(f.stat().st_size / 1024, 1)
            files.append({"path": str(f.relative_to(HW)), "kb": kb})
            if kb > 6 * 1024:
                failures.append(f"{f.name} is over 6 MB")
    res["files"] = files
    return failures


def main():
    args = set(sys.argv[1:])
    items, extra = assemble()
    print(f"built {len(items)} items")
    res = run_checks(items, extra)
    if "--no-export" not in args:
        export_all(items)
        from sheets import drawing_sheet, foam_template
        drawing_sheet(items, P, DV, OUT / "drawings" / "pod_k01_drawing.pdf")
        foam_template(P, DV, OUT / "drawings" / "foam_board_template.pdf")
        rb = step_readback(OUT / "step" / "pod_k01_assembly.step")
        res["step_readback"] = rb
        if rb["named"] < len(items) or rb["leaf_coloured"] < rb["leaf_shapes"]:
            res["failures"].append(f"assembly STEP lost names or colours: {rb}")
        res["failures"] += file_report(res)
        res["passed"] = not res["failures"]
        print("exports written")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "checks.json").write_text(json.dumps(res, indent=1))
    from readme import write_readme
    write_readme(res, P, HERE / "README.md")
    print("checks:", "PASS" if res["passed"] else "FAIL")
    for f in res["failures"]:
        print("  FAIL", f)
    if "--render-meshes" in args:
        export_render_meshes(items)
        print("render meshes written")
    if not res["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
