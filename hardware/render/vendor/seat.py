"""seat the vendor assets on the placeholders of pod_k01.assemble() and list where the real parts differ.

Run after convert.py: python -I hardware/render/vendor/seat.py
Writes hardware/build/detail/manifest.json, placeholders.npz (placeholder meshes for overlay previews)
and differences.json (every difference over 0.5 mm between a real model and the CAD parameter block).
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

HW = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(HW / "cad"))
import pod_k01 as cad  # noqa: E402

DET = HW / "build" / "detail"
P, DV = cad.P, cad.DV
LIMIT = 0.5


def asset(name):
    meta = json.loads((DET / f"{name}.json").read_text())
    d = np.load(DET / f"{name}.npz")
    names = meta["materials"]
    return meta, d["verts"].astype(float), d["tris"], np.array([names[i] for i in d["mat"]])


def mat4(R, t):
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t
    return M


def apply(M, pts):
    pts = np.asarray(pts, dtype=float)
    return pts @ M[:3, :3].T + M[:3, 3]


def tri_pts(v, t, sel):
    return v[np.unique(t[sel])] if sel.any() else np.zeros((0, 3))


def edge_segments(shape):
    segs = []
    for e in shape.edges():
        n = 2 if e.geom_type.name == "LINE" else 24
        pts = [e.position_at(u) for u in np.linspace(0, 1, n)]
        pts = np.array([[p.X, p.Y, p.Z] for p in pts])
        segs += list(zip(pts[:-1], pts[1:]))
    return np.array(segs, dtype=np.float32).reshape(-1, 2, 3)


def tess(shape):
    v, f = shape.tessellate(0.05, 0.3)
    return np.array([[p.X, p.Y, p.Z] for p in v]), np.array(f, dtype=np.int32)


DIFFS = []


def diff(part, what, cad_value, real_value, note=""):
    d = float(np.max(np.abs(np.subtract(real_value, cad_value))))
    row = {"part": part, "what": what, "cad": np.round(cad_value, 2).tolist(),
           "real": np.round(real_value, 2).tolist(), "delta_mm": round(d, 2), "note": note}
    if d > LIMIT:
        DIFFS.append(row)
    return row


def holes(meta, dmin):
    return np.array([h[:2] for h in meta["holes_xyd"] if h[2] >= dmin]), [h[2] for h in meta["holes_xyd"]
                                                                            if h[2] >= dmin]


def seat_max30101():
    meta, v, t, m = asset("max30101")
    fx = P.finger_c[0]
    hx, hd = holes(meta, 3.0)
    ph = np.array(cad.max_holes())
    R = np.eye(3)
    # holes on the placeholder hole pattern, component side up, the sensor end toward the tunnel end stop (+y)
    tr = np.array([ph[:, 0].mean() - hx[:, 0].mean(), ph[:, 1].mean() - hx[:, 1].mean(), DV.max_bot])
    M = mat4(R, tr)
    lo, hi = np.array(meta["board_bbox"][0]), np.array(meta["board_bbox"][1])
    diff("max30101", "board outline x, y, thickness", [P.max_board, P.max_board, P.max_t], hi - lo)
    diff("max30101", "mounting hole diameter", P.max_hole_d, np.mean(hd))
    real_h = apply(M, np.c_[hx, np.zeros(len(hx))])[:, :2]
    diff("max30101", "hole pattern pitch x, y", [P.max_hole_pitch] * 2, np.ptp(real_h, axis=0))
    glass = tri_pts(v, t, m == "glass")
    ic = apply(M, glass if len(glass) else tri_pts(v, t, m == "epoxy_black"))
    ic_c = (ic.min(0) + ic.max(0)) / 2
    diff("max30101", "sensor centre on the board (x, y) relative to the hole pattern centre",
         [0.0, 0.0], ic_c[:2] - ph.mean(0),
         "the MAX30101 sits 9.78 mm off centre toward one edge (SparkFun layout U2); "
         "to put it under the window move the board and its four posts by this offset the other way")
    diff("max30101", "sensor IC top above board bottom", P.max_t + P.max_ic[2], ic.max(0)[2] - DV.max_bot)
    qw = apply(M, tri_pts(v, t, m == "plastic_black"))
    diff("max30101", "Qwiic sockets: top face height above board bottom (they are on the sensor face)",
         -P.qwiic[2], qw.max(0)[2] - DV.max_bot,
         "both Qwiic sockets are on the same face as the sensor and stand above it; the CAD puts them "
         "under the board. The tunnel floor needs two pockets or a cut-out for them")
    return M, meta


def vision_m2_pads():
    """centres of the mask rings Seeed drew for the M2 screws, in the asset frame (board centre, y as in the step)."""
    import re
    s = next((HW / "build" / "vendor" / "vision").glob("*.kicad_pcb")).read_text()
    rings = {(float(a), float(b)) for a, b in
             re.findall(r'gr_circle \(center ([\d.]+) ([\d.]+)\) \(end [\d. ]+\)\s*\(stroke[^)]*\)[^)]*\)[^(]*'
                        r'\(fill solid\) \(layer "F.Mask"\)', s)}
    segs = re.findall(r'gr_line \(start ([\d.]+) ([\d.]+)\) \(end ([\d.]+) ([\d.]+)\)\s*\(stroke[^\n]*"Edge.Cuts"', s)
    pts = [(float(a), float(b)) for g in segs for a, b in (g[:2], g[2:])]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return np.array(sorted((x - cx, y - cy) for x, y in rings))


def seat_vision():
    meta, v, t, m = asset("vision_stack")
    x0, x1, y0, y1 = cad.vision_box()
    lo, hi = np.array(meta["board_bbox"][0]), np.array(meta["board_bbox"][1])
    tr = np.array([(x0 + x1) / 2 - (lo[0] + hi[0]) / 2, (y0 + y1) / 2 - (lo[1] + hi[1]) / 2, DV.vis_z0])
    M = mat4(np.eye(3), tr)
    diff("vision_stack", "Vision AI V2 board x, y, thickness", [x1 - x0, y1 - y0, P.vision[2]], hi - lo)
    hx = vision_m2_pads()
    real = apply(M, np.c_[hx, np.zeros(len(hx))])[:, :2]
    cad_h = np.array(cad.vision_holes())
    DIFFS.append({"part": "vision_stack", "what": "mounting points", "cad": cad_h.round(2).tolist(),
                  "real": real.round(2).tolist(), "delta_mm": None,
                  "note": "Seeed's layout has two 3.5 mm exposed copper rings (both faces) where its photo says "
                          "'M2 Screw Hole x 2', on a line across the board 2.40 mm from centre toward the far "
                          "end from the USB-C, 16.48 mm apart; the published file has no drill there. "
                          "The CAD has four corner holes. Check the real board before printing the standoffs"})
    pts = apply(M, v)
    top = pts[:, 2].max()
    diff("vision_stack", "stack top (XIAO shield) above tray top",
         DV.vis_z0 + P.vision[2] + 8.5 + P.xiao[2] + 2.5 - DV.tray_z1, top - DV.tray_z1)
    under = pts[:, 2].min()
    diff("vision_stack", "depth of parts under the board (USB-C, FFC socket on the bottom face)",
         1.5, DV.vis_z0 - under, "the camera FFC socket and the board USB-C are on the face toward the tray; "
                           f"they come within {under - DV.tray_z1:.2f} mm of the tray")
    steel = tri_pts(v, t, m == "steel")
    sp = apply(M, steel)
    usb_lo = sp[sp[:, 2] < DV.vis_z0 + 0.1]
    diff("vision_stack", "board USB-C mouth x", x0 - 1.0, usb_lo[:, 0].min(),
         "the receptacle is on the bottom face, not the top as in the CAD")
    fpc = apply(M, tri_pts(v, t, m == "plastic_beige"))
    fc = (fpc.min(0) + fpc.max(0)) / 2
    diff("vision_stack", "CSI camera socket centre x, y, z", [112.0, y0 + 2.5, DV.vis_z0 + P.vision[2] + 1.25], fc,
         "the 15 pin FFC socket sits on the bottom face at the far end from the USB-C, its opening facing +x; "
         "the ribbon has to enter from that end, under the board")
    xiao = sp[sp[:, 2] > DV.vis_z0 + 6]
    diff("vision_stack", "XIAO USB-C mouth x", 102.0 - 1.3, xiao[:, 0].min())
    zx = xiao[:, 2]
    diff("vision_stack", "XIAO USB-C centre height", DV.vis_z0 + P.vision[2] + 8.5 + P.xiao[2] + 1.6,
         (zx.min() + zx.max()) / 2)
    return M, meta


def seat_hub():
    meta, v, t, m = asset("hub_ch334f")
    hx, hd = holes(meta, 2.0)
    ph = np.array(cad.hub_holes())
    tr = np.array([ph[:, 0].mean() - hx[:, 0].mean(), ph[:, 1].mean() - hx[:, 1].mean(), DV.hub_z0])
    M = mat4(np.eye(3), tr)
    lo, hi = np.array(meta["board_bbox"][0]), np.array(meta["board_bbox"][1])
    x0, x1, y0, y1 = cad.hub_box()
    diff("hub_ch334f", "board x, y, thickness", [x1 - x0, y1 - y0, P.hub[2]], hi - lo,
         "Adafruit lists 31.6 mm, which includes the USB-C overhang; the board itself is shorter")
    real = apply(M, np.c_[hx, np.zeros(len(hx))])[:, :2]
    diff("hub_ch334f", "hole pattern pitch x, y", np.ptp(ph, axis=0), np.ptp(real, axis=0))
    diff("hub_ch334f", "mounting hole diameter", 2.5, np.mean(hd))
    sp = apply(M, tri_pts(v, t, m == "steel"))
    diff("hub_ch334f", "upstream USB-C mouth y", y1 + 0.8, sp[:, 1].max())
    diff("hub_ch334f", "overall height above board bottom", P.hub[2] + 3.2, apply(M, v)[:, 2].max() - DV.hub_z0)
    return M, meta


def seat_speaker():
    meta, v, t, m = asset("speaker")
    gx, gz = P.grille_c
    # asset z (axis, front at 0) -> pod -y; asset y -> pod z
    R = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float)
    M = mat4(R, [gx, P.wall, gz])
    lo, hi = np.array(meta["bbox_min"]), np.array(meta["bbox_max"])
    diff("speaker", "outer diameter", P.spk_d, hi[0] - lo[0])
    diff("speaker", "depth front of rim to back of magnet", P.spk_depth, hi[2] - lo[2],
         "Adafruit's page says 20 mm, its own CAD file is 25 mm deep; measure the part")
    diff("speaker", "magnet diameter", 26.0, 20.0, "from the CAD file: magnet cup 20 mm, the CAD uses 26")
    return M, meta


def seat_sht31():
    meta, v, t, m = asset("sht31")
    lo, hi = np.array(meta["board_bbox"][0]), np.array(meta["board_bbox"][1])
    w, h, th = P.sht31
    diff("sht31", "board width, length, thickness", [w, h, th], hi - lo,
         "Adafruit 2857 today is the STEMMA QT layout (Adafruit CAD file); at 25.4 mm wide it does not fit "
         "the 14 mm bore of the capsule tube")
    diff("sht31", "height with connectors", 2.6, (np.array(meta["bbox_max"]) - np.array(meta["bbox_min"]))[2])
    # asset x -> local -x, asset y -> local z, asset z (component side) -> local +y, then capsule_place
    R = np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], dtype=float)
    local = mat4(R, [0.0, -th / 2, 25.0 - h / 2])
    from build123d import Location
    place = Location((92.0, DV.cap_axis[0], DV.cap_axis[1])) * Location((0, 0, 0), (0, -90, 0))
    tr = place.wrapped.Transformation()
    Mp = np.eye(4)
    for i in range(3):
        for j in range(4):
            Mp[i, j] = tr.Value(i + 1, j + 1)
    return Mp @ local, meta


SEATS = {"max30101": seat_max30101, "vision_stack": seat_vision, "hub_ch334f": seat_hub,
         "speaker": seat_speaker, "sht31": seat_sht31}


def main():
    items, _ = cad.assemble()
    bought = [it for it in items if it.kind == "bought"]
    ph = {}
    for it in bought:
        vs, ts, base = [], [], 0
        for c in it.children:
            v, f = tess(c)
            vs.append(v)
            ts.append(f + base)
            base += len(v)
        ph[f"{it.name}_v"] = np.concatenate(vs).astype(np.float32)
        ph[f"{it.name}_t"] = np.concatenate(ts).astype(np.int32)
        ph[f"{it.name}_e"] = np.concatenate([edge_segments(c) for c in it.children])
    np.savez_compressed(DET / "placeholders.npz", **ph)
    missing = json.loads((DET / "missing.json").read_text()) if (DET / "missing.json").exists() else []
    parts = {}
    for it in bought:
        if it.name not in SEATS:
            continue
        M, meta = SEATS[it.name]()
        parts[it.name] = {"assets": [{"asset": meta["asset"], "file": f"{meta['asset']}.blend",
                                      "mesh": f"{meta['asset']}.npz", "matrix": np.round(M, 6).tolist()}],
                          "source": meta["source"], "asset_frame": meta["frame"]}
    man = {"written": date.today().isoformat(), "units": "mm",
           "frame": "pod_k01 assembly frame: X across the face, Y into the box, Z up",
           "matrix": "4 x 4, row major, maps asset coordinates (mm) to the assembly frame (mm)",
           "parts": parts, "no_official_model": missing,
           "bought_parts": [it.name for it in bought]}
    (DET / "manifest.json").write_text(json.dumps(man, indent=1))
    (DET / "differences.json").write_text(json.dumps(DIFFS, indent=1))
    for d in DIFFS:
        print(f"{d['part']:13s} {d['what'][:60]:60s} cad {d['cad']} real {d['real']} d {d['delta_mm']}")
    print("seated:", list(parts), "missing:", missing)


if __name__ == "__main__":
    main()
