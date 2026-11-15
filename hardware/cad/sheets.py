"""Drawing sheet and foam board template for pod K-01 (matplotlib, PDF)."""

import math
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Circle as MCircle, FancyBboxPatch, Rectangle as MRect  # noqa: E402

from build123d import Compound, GeomType  # noqa: E402

LW_EDGE, LW_THIN = 0.35, 0.2
INK = "black"


def _paper(w_mm, h_mm):
    fig = plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w_mm)
    ax.set_ylim(0, h_mm)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def _edge_points(e):
    if e.geom_type == GeomType.LINE:
        ts = (0.0, 1.0)
    else:
        n = max(8, min(64, int(e.length / 0.6)))
        ts = [i / n for i in range(n + 1)]
    return [e.position_at(t) for t in ts]


def _view(ax, shape, origin, up, look, place, s):
    vis, _ = shape.project_to_viewport(origin, up, look)
    px, py = place
    for e in vis:
        pts = _edge_points(e)
        ax.plot([px + s * p.X for p in pts], [py + s * p.Y for p in pts], color=INK, lw=LW_EDGE,
                solid_capstyle="round")


def _arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="<|-|>", lw=LW_THIN, color=INK,
                                                    shrinkA=0, shrinkB=0, mutation_scale=5))


def dim_h(ax, x0, x1, y_feat0, y_feat1, y_line, text):
    for x, yf in ((x0, y_feat0), (x1, y_feat1)):
        ax.plot([x, x], [yf + (1 if y_line > yf else -1), y_line + (1.5 if y_line > yf else -1.5)], color=INK,
                lw=LW_THIN)
    _arrow(ax, (x0, y_line), (x1, y_line))
    ax.text((x0 + x1) / 2, y_line + 0.8, text, ha="center", va="bottom", fontsize=6)


def dim_v(ax, y0, y1, x_feat0, x_feat1, x_line, text):
    for y, xf in ((y0, x_feat0), (y1, x_feat1)):
        ax.plot([xf + (1 if x_line > xf else -1), x_line + (1.5 if x_line > xf else -1.5)], [y, y], color=INK,
                lw=LW_THIN)
    _arrow(ax, (x_line, y0), (x_line, y1))
    ax.text(x_line - 0.8, (y0 + y1) / 2, text, ha="right", va="center", fontsize=6, rotation=90)


def leader(ax, at, to, text, ha="left"):
    ax.annotate(text, xy=at, xytext=to, fontsize=5.5, ha=ha, va="center",
                arrowprops=dict(arrowstyle="-|>", lw=LW_THIN, color=INK, mutation_scale=4, shrinkA=0, shrinkB=0))


def centre_mark(ax, p, r=2.0):
    ax.plot([p[0] - r, p[0] + r], [p[1], p[1]], color=INK, lw=LW_THIN)
    ax.plot([p[0], p[0]], [p[1] - r, p[1] + r], color=INK, lw=LW_THIN)


def third_angle_symbol(ax, x, y):
    ax.add_patch(MCircle((x + 12, y), 2.2, fill=False, lw=LW_THIN))
    ax.add_patch(MCircle((x + 12, y), 3.6, fill=False, lw=LW_THIN))
    ax.plot([x, x + 6, x + 6, x, x], [y - 2.2, y - 3.6, y + 3.6, y + 2.2, y - 2.2], color=INK, lw=LW_THIN)


def drawing_sheet(items, P, DV, path):
    names = ("shell", "rear_plate", "finger_cradle", "camera_bezel", "cable_clamp", "uv_led")
    shape = Compound(children=[it.shape for it in items if it.name in names])
    s = 0.5
    W, H, D = P.W, P.H, P.D
    look = (W / 2, D / 2, H / 2)
    fig, ax = _paper(420, 297)
    ax.add_patch(MRect((10, 10), 400, 277, fill=False, lw=0.5))
    cf, ct, cr, cb = (130, 100), (130, 222), (255, 100), (365, 100)
    _view(ax, shape, (look[0], -1000, look[2]), (0, 0, 1), look, cf, s)
    _view(ax, shape, (look[0], look[1], 1000), (0, 1, 0), look, ct, s)
    _view(ax, shape, (1000, look[1], look[2]), (0, 0, 1), look, cr, s)
    _view(ax, shape, (look[0], 1000, look[2]), (0, 0, 1), look, cb, s)

    def F(x, z):
        return cf[0] + s * (x - look[0]), cf[1] + s * (z - look[2])

    def T(x, y):
        return ct[0] + s * (x - look[0]), ct[1] + s * (y - look[1])

    def R(y, z):
        return cr[0] + s * (y - look[1]), cr[1] + s * (z - look[2])

    def B(x, z):
        return cb[0] - s * (x - look[0]), cb[1] + s * (z - look[2])

    for lab, c, dy in (("FRONT", cf, -48), ("TOP", ct, -36), ("RIGHT", cr, -48), ("BACK", cb, -48)):
        ax.text(c[0], c[1] + dy, lab, ha="center", fontsize=7, weight="bold")

    # front view
    x0, z0 = F(0, 0)
    x1, z1 = F(W, H)
    dim_h(ax, x0, x1, z0 - 4, z0 - 4, z0 - 12, f"{W:.0f}")
    dim_v(ax, z0, z1, x0, x0, x0 - 8, f"{H:.0f}")
    _, zf = F(0, -P.foot_h)
    dim_v(ax, zf, z0, x0 + 8, x0 + 8, x0 - 16, f"{P.foot_h:.0f}")
    gx, gz = P.grille_c
    cx, cz = P.cam_c
    fx, fz = P.finger_c
    for p in (F(gx, gz), F(cx, cz), F(fx, fz)):
        centre_mark(ax, p)
    dim_h(ax, x0, F(gx, 0)[0], z1, z1, z1 + 6, f"{gx:.0f}")
    dim_h(ax, x0, F(fx, 0)[0], z1, z1, z1 + 12, f"{fx:.0f}")
    dim_h(ax, x0, F(cx, 0)[0], z1, z1, z1 + 18, f"{cx:.0f}")
    xr = x1
    dim_v(ax, z0, F(0, fz)[1], xr, F(fx, fz)[0] + 7, xr + 6, f"{fz:.0f}")
    dim_v(ax, z0, F(0, gz)[1], xr, F(gx, gz)[0], xr + 12, f"{gz:.0f}")
    dim_v(ax, z0, F(0, cz)[1], xr, F(cx, cz)[0], xr + 18, f"{cz:.0f}")
    w0, h0 = P.tunnel_in
    xl = x0 - 24
    leader(ax, F(gx - 14, gz + 8), (xl, F(0, gz + 22)[1]),
           f"speaker grille: {P.grille_hole_d} holes,\nhex pitch {P.grille_pitch}, field {P.grille_field_d:.0f} dia",
           ha="right")
    leader(ax, F(P.label_x + 2, P.label_base + 3), (xl, F(0, P.label_base + 4)[1]),
           f"{P.label} debossed {P.label_depth},\ncap height {P.label_cap:.0f}", ha="right")
    ya = z1 + 28
    leader(ax, F(cx + 6, cz + 6), (F(cx, 0)[0] + 8, ya + 6),
           f"camera aperture {P.bezel_aperture} dia, 45 deg chamfer")
    leader(ax, F(fx + 10, fz + 9), (F(cx, 0)[0] + 8, ya),
           f"finger port {P.port_w:.0f} x {P.port_h:.0f}, tunnel {w0:.0f} x {h0:.0f} at entry")

    # top view
    tx0, ty0 = T(0, 0)
    tx1, ty1 = T(W, D)
    dim_v(ax, ty0, ty1, tx0, tx0, tx0 - 8, f"{D:.0f} shell")
    _, typ = T(0, D + P.plate_t - P.spigot_t)
    dim_v(ax, T(0, -P.lip_proud)[1], typ, tx0, tx0, tx0 - 16,
          f"{D + P.plate_t - P.spigot_t + P.lip_proud:.1f} lip to plate")
    mx, my = P.mic_c
    lx, ly = P.led_c
    centre_mark(ax, T(mx, my))
    centre_mark(ax, T(lx, ly))
    dim_h(ax, T(mx, 0)[0], T(lx, 0)[0], T(0, my)[1], T(0, ly)[1], ty1 + 6, f"{lx - mx:.0f}")
    dim_h(ax, tx0, T(mx, 0)[0], ty1, ty1, ty1 + 12, f"{mx:.0f}")
    leader(ax, T(mx, my), T(mx - 40, my + 30), f"mic port: {P.mic_holes} x {P.mic_hole_d} holes, pitch {P.mic_pitch}",
           ha="right")
    leader(ax, T(lx, ly), T(lx + 40, ly + 30), f"UV LED {P.led_hole_d} hole, {P.led_cb_d} counterbore inside")
    dim_v(ax, ty0, T(0, my)[1], tx1, T(mx, my)[0], tx1 + 6, f"{my:.1f}")

    # right view
    ry0, rz0 = R(0, 0)
    ry1, rz1 = R(D, H)
    dim_h(ax, ry0, ry1, rz0 - 4, rz0 - 4, rz0 - 12, f"{D:.0f}")
    _, rzl = R(0, H + P.led_proud)
    _, rzf = R(0, -P.foot_h)
    dim_v(ax, rzf, rzl, ry1 + 4, ry1 + 4, ry1 + 14, f"{H + P.foot_h + P.led_proud:.0f} overall")

    # back view
    bx0, bz0 = B(W, 0)
    bx1, bz1 = B(0, H)
    i = P.corner_boss_inset
    dim_h(ax, B(W - i, 0)[0], B(i, 0)[0], B(0, i)[1], B(0, i)[1], bz0 - 12, f"{W - 2 * i:.0f} (4 x M3 csk)")
    dim_v(ax, B(0, i)[1], B(0, H - i)[1], B(i, 0)[0], B(i, 0)[0], bx1 + 8, f"{H - 2 * i:.0f}")
    kx, kz = P.keyhole_c
    centre_mark(ax, B(kx, kz))
    leader(ax, B(kx, DV.cable_z), (B(kx, 0)[0] - 4, bz0 - 16.5),
           f"cable exit: keyhole {P.keyhole_d:.0f} dia, cable seat {DV.cable_z:.1f} above the base", ha="right")
    leader(ax, B(22, 96), (B(22, 0)[0] - 6, bz1 + 14), f"hanger keyholes {W - 44:.0f} apart", ha="center")

    # notes and title block
    w1, h1 = P.tunnel_sensor
    notes = [
        "NOTES",
        "1. Dimensions in mm. Hidden lines omitted. Internal parts not shown.",
        f"2. Finger tunnel: {w0:.0f} x {h0:.0f} at entry, {w1:.0f} x {h1:.0f} over the sensor, "
        f"{P.tunnel_len:.0f} deep to the end stop.",
        f"3. Sensor window {P.window[0]} x {P.window[1]:.0f}, centred {P.window_from_stop:.0f} from the end stop; "
        f"floor {P.floor_over_sensor:.1f} thick over the sensor.",
        f"4. Shell wall {P.wall}, corner radius {P.corner_r:.0f}, front chamfer {P.front_chamfer}.",
        "5. M3 heat-set inserts: 4.0 pilot, 6.7 deep. All printed parts PETG unless stated.",
        f"6. Rear plate: 8 intake slots low, 11 exhaust slots high, {P.slot_w} wide.",
        "7. Sensor capsule and its clip on the rear plate are not shown on this sheet.",
    ]
    for k, line in enumerate(notes):
        ax.text(250, 270 - k * 5, line, fontsize=6, weight="bold" if k == 0 else "normal")
    ax.add_patch(MRect((290, 10), 120, 40, fill=False, lw=0.5))
    for y in (20, 30, 40):
        ax.plot([290, 410], [y, y], color=INK, lw=LW_THIN)
    ax.plot([350, 350], [10, 40], color=INK, lw=LW_THIN)
    ax.text(293, 43, "POD K-01 ENCLOSURE", fontsize=10, weight="bold", va="center")
    ax.text(293, 35, "Part: shell, rear plate, finger cradle, bezel", fontsize=6, va="center")
    ax.text(293, 25, "Scale 1:2 on A3", fontsize=6, va="center")
    ax.text(353, 25, f"Date {date.today().isoformat()}", fontsize=6, va="center")
    ax.text(293, 15, "Units mm", fontsize=6, va="center")
    ax.text(353, 15, "Sheet 1 of 1", fontsize=6, va="center")
    ax.text(353, 35, "Third angle projection", fontsize=6, va="center")
    third_angle_symbol(ax, 392, 35)
    fig.savefig(path)
    preview = path.parent.parent.parent / "build" / "drawing_preview.png"
    preview.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(preview, dpi=110)
    plt.close(fig)


# foam board template
LETTER = (215.9, 279.4)


def _page_frame(ax, title, page, n):
    w, h = LETTER
    for (x, y) in ((10, 10), (w - 10, 10), (10, h - 10), (w - 10, h - 10)):
        ax.add_patch(MCircle((x, y), 2.5, fill=False, lw=0.3))
        ax.plot([x - 5, x + 5], [y, y], color=INK, lw=0.3)
        ax.plot([x, x], [y - 5, y + 5], color=INK, lw=0.3)
    ax.text(w / 2, h - 12, f"Pod K-01 foam board template: {title}", ha="center", fontsize=9, weight="bold")
    ax.text(w / 2, h - 17, "Print at 100% (actual size). 5 mm foam board, butt joints, glue.", ha="center",
            fontsize=6.5)
    ax.text(w - 20, 12, f"page {page} of {n}", ha="right", fontsize=6.5)
    x0, y0 = 22, 14
    ax.plot([x0, x0 + 50], [y0, y0], color=INK, lw=0.8)
    for k in range(6):
        ax.plot([x0 + 10 * k, x0 + 10 * k], [y0, y0 + (2.5 if k % 5 else 4)], color=INK, lw=0.5)
    ax.text(x0 + 25, y0 + 5, "50 mm check bar: measure before cutting", ha="center", fontsize=6)


def _panel(ax, x0, y0, w, h, name, size_note):
    ax.add_patch(MRect((x0, y0), w, h, fill=False, lw=0.6))
    ax.text(x0 + w / 2, y0 + h + 2, f"{name}  {size_note}", ha="center", fontsize=7, weight="bold")


def _slot(ax, cx, cy, w, h):
    ax.add_patch(FancyBboxPatch((cx - w / 2 + w / 2, cy - h / 2 + w / 2), 0.001, h - w,
                                boxstyle=f"round,pad={w / 2}", fill=False, lw=0.4))


def foam_template(P, DV, path):
    W, H, D = P.W, P.H, P.D
    t = 5.0
    inner_d = D - 2 * t
    side_h = H - 2 * t
    pages = []

    # page 1: front and back, both drawn as seen from outside
    fig, ax = _paper(*LETTER)
    _page_frame(ax, "front and back", 1, 3)
    fx0, fy0 = (LETTER[0] - W) / 2, 140
    _panel(ax, fx0, fy0, W, H, "FRONT (outside face up)", f"{W:.0f} x {H:.0f}")
    gx, gz = P.grille_c
    rows = int(P.grille_field_d / (P.grille_pitch * math.sin(math.radians(60)))) + 2
    for j in range(-rows, rows + 1):
        zz = j * P.grille_pitch * math.sin(math.radians(60))
        off = (P.grille_pitch / 2) if j % 2 else 0.0
        for i in range(-rows, rows + 1):
            xx = i * P.grille_pitch + off
            if math.hypot(xx, zz) <= (P.grille_field_d - P.grille_hole_d) / 2:
                ax.add_patch(MCircle((fx0 + gx + xx, fy0 + gz + zz), P.grille_hole_d / 2, fill=False, lw=0.25))
    ax.text(fx0 + gx, fy0 + gz - P.grille_field_d / 2 - 4, "speaker grille: pierce each hole", ha="center",
            fontsize=5.5)
    cx, cz = P.cam_c
    ax.add_patch(MCircle((fx0 + cx, fy0 + cz), P.bezel_od / 2 + P.bezel_fit, fill=False, lw=0.5))
    ax.text(fx0 + cx, fy0 + cz - 14, f"camera: cut {P.bezel_od + 2 * P.bezel_fit:.1f} dia for the bezel",
            ha="center", fontsize=5.5)
    fx, fz = P.finger_c
    ax.add_patch(FancyBboxPatch((fx0 + fx - P.port_w / 2 + P.port_r, fy0 + fz - P.port_h / 2 + P.port_r),
                                P.port_w - 2 * P.port_r, P.port_h - 2 * P.port_r,
                                boxstyle=f"round,pad={P.port_r}", fill=False, lw=0.5))
    ax.text(fx0 + fx, fy0 + fz - P.port_h / 2 - 4, f"finger port {P.port_w:.0f} x {P.port_h:.0f}", ha="center",
            fontsize=5.5)
    ax.add_patch(MRect((fx0 + P.label_x, fy0 + P.label_base), 30, P.label_cap, fill=False, lw=0.3, ls="--"))
    ax.text(fx0 + P.label_x + 1, fy0 + P.label_base + 1.5, P.label, fontsize=9)
    ax.text(fx0 + P.label_x, fy0 + P.label_base - 4, "label area (draw, do not cut)", fontsize=5)

    bx0, by0 = (LETTER[0] - W) / 2, 22
    _panel(ax, bx0, by0, W, H, "BACK (outside face up)", f"{W:.0f} x {H:.0f}")

    def BX(x):
        return bx0 + (W - x)

    kx, kz = P.keyhole_c
    ax.add_patch(MCircle((BX(kx), by0 + kz), P.keyhole_d / 2, fill=False, lw=0.5))
    ax.add_patch(MCircle((BX(kx), by0 + DV.cable_z), P.cable_d / 2 + 0.2, fill=False, lw=0.5))
    ax.plot([BX(kx) - 2.2, BX(kx) - 2.2], [by0 + DV.cable_z, by0 + kz - 6.1], color=INK, lw=0.5)
    ax.plot([BX(kx) + 2.2, BX(kx) + 2.2], [by0 + DV.cable_z, by0 + kz - 6.1], color=INK, lw=0.5)
    ax.text(BX(kx), by0 + kz + 9, "cable exit", ha="center", fontsize=5.5)
    for i in range(8):
        _slot(ax, BX(100 + i * 6), by0 + 32, P.slot_w, 20)
    for i in range(11):
        _slot(ax, BX(45 + i * 6), by0 + 87, P.slot_w, 22)
    for x in (22.0, W - 22.0):
        ax.add_patch(MCircle((BX(x), by0 + 88), 4.5, fill=False, lw=0.5))
        _slot(ax, BX(x), by0 + 92, 4.4, 12.4)
    pages.append(fig)

    # page 2: top and bottom, between front and back
    fig, ax = _paper(*LETTER)
    _page_frame(ax, "top and bottom", 2, 3)
    tx0, ty0 = (LETTER[0] - W) / 2, 155
    _panel(ax, tx0, ty0, W, inner_d, "TOP (outside up, front edge at bottom)", f"{W:.0f} x {inner_d:.0f}")
    mx, my = P.mic_c
    for k in range(P.mic_holes):
        x = mx + (k - (P.mic_holes - 1) / 2) * P.mic_pitch
        ax.add_patch(MCircle((tx0 + x, ty0 + my - t), P.mic_hole_d / 2, fill=False, lw=0.4))
    ax.text(tx0 + mx, ty0 + my - t - 5, "mic holes", ha="center", fontsize=5.5)
    lx, ly = P.led_c
    ax.add_patch(MCircle((tx0 + lx, ty0 + ly - t), P.led_hole_d / 2, fill=False, lw=0.5))
    ax.text(tx0 + lx, ty0 + ly - t - 5.5, "UV LED", ha="center", fontsize=5.5)
    ax.text(tx0 + 2, ty0 + 2, "front edge", fontsize=5)
    bx0, by0 = (LETTER[0] - W) / 2, 45
    _panel(ax, bx0, by0, W, inner_d, "BOTTOM (outside up, front edge at bottom)", f"{W:.0f} x {inner_d:.0f}")
    hx, hy = P.lead_hole
    hyf = min(hy - t, inner_d - P.lead_hole_d)
    ax.add_patch(MCircle((bx0 + W - hx, by0 + hyf), P.lead_hole_d / 2, fill=False, lw=0.5))
    ax.text(bx0 + W - hx, by0 + hyf - 6, "sensor lead", ha="center", fontsize=5.5)
    for fxx in (22.0, W - 22.0):
        for fyy in (8.0, 64.0):
            ax.add_patch(MRect((bx0 + W - fxx - P.foot_w / 2, by0 + fyy - t), P.foot_w, P.foot_l, fill=False,
                               lw=0.3, ls="--"))
    ax.text(bx0 + 2, by0 + 2, "front edge (feet: dashed, glue on)", fontsize=5)
    pages.append(fig)

    # page 3: sides, inside all four
    fig, ax = _paper(*LETTER)
    _page_frame(ax, "sides", 3, 3)
    for k, name in enumerate(("LEFT SIDE", "RIGHT SIDE")):
        x0 = 18 + k * (inner_d + 16)
        _panel(ax, x0, 120, inner_d, side_h, name, f"{inner_d:.0f} x {side_h:.0f}")
    ax.text(LETTER[0] / 2, 95,
            f"Joints: front and back are full size. Top and bottom sit between them ({inner_d:.0f} deep).\n"
            f"Sides sit inside all four ({inner_d:.0f} x {side_h:.0f}). Foam is {t:.0f} mm, the printed shell "
            f"wall is {P.wall} mm,\nso the foam box has less room inside; the printed cradle and bezel "
            "are held with tape or glue.",
            ha="center", fontsize=6.5, va="top")
    pages.append(fig)

    preview = path.parent.parent.parent / "build"
    with PdfPages(path) as pdf:
        for k, f in enumerate(pages):
            pdf.savefig(f)
            f.savefig(preview / f"foam_preview_{k + 1}.png", dpi=90)
            plt.close(f)
