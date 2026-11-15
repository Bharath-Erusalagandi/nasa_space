"""turn the vendor STEP files into one mesh per bought part, faces grouped into named materials.

Run: python -I hardware/render/vendor/convert.py [asset ...]
Reads hardware/build/vendor/, writes hardware/build/detail/<asset>.npz and <asset>.json.
Each npz holds verts (mm, float32), tris (int32), mat (per triangle index into the json's materials).
The canonical frame of every asset is given in ASSETS[...]["frame"] and copied to the json.
"""

import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stepread import faces_of, read  # noqa: E402

HW = Path(__file__).resolve().parent.parent.parent
VEN = HW / "build" / "vendor"
DET = HW / "build" / "detail"

# material names the render scene maps to real shaders
MATS = ["solder_mask", "fr4_edge", "enig", "tin", "silkscreen", "epoxy_black", "mlcc_ceramic", "resistor_top",
        "steel", "steel_dark", "plastic_black", "plastic_white", "plastic_beige", "led_lens", "silicon", "glass",
        "copper", "copper_under_mask", "rubber_black", "cone_paper", "label_white"]


def near(c, rgb, tol=0.02):
    return c is not None and all(abs(a - b) <= tol for a, b in zip(c, rgb))


def grey(c, lo, hi, chroma=0.1):
    return c is not None and max(c) - min(c) < chroma and lo <= c[0] <= hi


# rules: (path regex or None, colour test or None, material); first match wins
KICAD_RULES = [
    (r"OESIP.*cover_glass", None, "glass"),
    (r"OESIP.*led_dies", None, "led_die"),
    (r"OESIP.*photodiode", None, "silicon"),
    (r"OESIP.*pad\d", None, "enig"),
    (r"OESIP", None, "epoxy_black"),
    (r"_soldermask$", None, "solder_mask"),
    (r"_silkscreen$", None, "silkscreen"),
    (r"_PCB$", None, "board"),
    (r"_pads?$", None, "enig"),
    (r"_(tracks?|copper|vias?)$", None, "copper_under_mask"),
    (r"BGA-90", lambda c: grey(c, 0.0, 0.05), "silicon"),
    (r"BGA-90", None, "drop"),
    (r"C_0[46]0[23]|C_0805", lambda c: near(c, (0.119, 0.059, 0.038), 0.05), "mlcc_ceramic"),
    (r"R_0[46]0[23]|R_0805", lambda c: grey(c, 0.0, 0.03), "resistor_top"),
    (r"LED_0", lambda c: c is not None and c[1] > 0.3 and c[0] < 0.2, "led_lens"),
    (r"TE_1_84952|FPC", lambda c: near(c, (0.776, 0.768, 0.624), 0.03) or near(c, (0.644, 0.638, 0.571), 0.03),
     "plastic_beige"),
    (r"JST_S4B_PH|JST_PH", lambda c: near(c, (0.776, 0.768, 0.624), 0.03) or near(c, (0.644, 0.638, 0.571), 0.03),
     "plastic_white"),
    (r"JST_SH|SM04B", lambda c: near(c, (0.776, 0.768, 0.624), 0.03) or grey(c, 0.0, 0.1), "plastic_black"),
    (r"USB_C_Receptacle", lambda c: c is not None and c[0] > 0.6 and c[2] < 0.3, "enig"),
    (r"USB_C_Receptacle", lambda c: grey(c, 0.5, 1.0), "steel"),
    (r"USB_C_Receptacle", None, "plastic_black"),
    (r"Crystal", lambda c: c is not None and c[0] > 0.6 and c[2] < 0.3, "steel"),
    (r"PinSocket|PinHeader", lambda c: c is not None and c[0] > 0.6 and c[2] < 0.3, "enig"),
    (r"PinSocket|PinHeader", None, "plastic_black"),
    (r"SW_SPST_PTS810", lambda c: grey(c, 0.5, 1.0), "steel"),
    (r"Knowles", lambda c: grey(c, 0.5, 1.0), "steel"),
    (r"SD-TF|microsd|shell|tab\d", lambda c: grey(c, 0.4, 1.0), "steel"),
    (r"contact\d", None, "enig"),
    (r"insulator", None, "plastic_black"),
    (None, lambda c: c is not None and c[0] > 0.6 and 0.35 < c[1] < 0.8 and c[2] < 0.45, "tin"),
    (None, lambda c: grey(c, 0.55, 0.85), "tin"),
    (None, lambda c: grey(c, 0.0, 0.12), "epoxy_black"),
]

XIAO_RULES = [
    (r"Silkscreen", None, "silkscreen"),
    (r"Shield", None, "shield"),
    (r"USB TYPE C PORT.*(CUT-EXTRUDE|MIRROR)", lambda c: not near(c, (0.905, 0.784, 0.386), 0.05), "plastic_black"),
    (r"USB TYPE C PORT", lambda c: near(c, (0.905, 0.784, 0.386), 0.05), "enig"),
    (r"USB TYPE C PORT", None, "steel"),
    (r"PCB \(1\).*COMPOUND", lambda c: near(c, (0.905, 0.784, 0.386), 0.05), "enig"),
    (r"PCB \(1\).*COMPOUND", None, "board:black"),
    (r"MSM261", None, "steel"),
    (r"SKTAAAE.*Pins", None, "tin"),
    (r"SKTAAAE", None, "plastic_black"),
    (r"/LED|/USR", None, "led_lens"),
    (r"/CAP|/ANT1", None, "mlcc_ceramic"),
]

ADA_RULES = [
    (r"Board", lambda c: near(c, (0.965, 0.658, 0.397), 0.03), "enig_board"),
    (r"Board", None, "board"),
    (r"USB_C", lambda c: near(c, (1.0, 0.617, 0.212), 0.03), "enig"),
    (r"USB_C", None, "steel"),
    (r"JST_SH", lambda c: grey(c, 0.3, 0.4), "tin"),
    (r"JST_SH", None, "plastic_black"),
    (r"CHIPLED", None, "led_lens"),
    (r"CRYSTAL", None, "steel"),
    (r"0603|0805|1206", lambda c: near(c, (1.0, 1.0, 1.0)), "tin"),
    (r"0603", None, "resistor_top"),
    (r"0805|1206", None, "mlcc_ceramic"),
    (r"QFN", lambda c: grey(c, 0.5, 0.6), "epoxy_black"),
    (r"SHT3X", lambda c: grey(c, 0.5, 0.6), "sensor_dfn"),
    (None, lambda c: grey(c, 0.5, 0.6), "tin"),
    (None, None, "epoxy_black"),
]


XIAO_IN = [("XIAO.*(" + rx + ")" if rx else "XIAO", test, mat) for rx, test, mat in XIAO_RULES] + \
    [("XIAO", None, "epoxy_black")]


def frame_pcb(top="+z"):
    return f"board outline centred on x and y, z = 0 on the bottom face of the bare board, component side {top}"


ASSETS = {
    "vision_stack": {
        "src": [("kicad_out/vision_ai_v2.step", XIAO_IN + KICAD_RULES, None)],
        "mask": "blue", "flip": True,
        "frame": frame_pcb("(the XIAO and sockets, KiCad B.Cu) +z; CSI and USB-C side -z") +
                 "; x along the 40 mm edge with the USB-C end at -x",
        "source": "Seeed Grove Vision AI V2 KiCad layout + Seeed XIAO nRF52840 Sense STEP + KiCad library models",
    },
    "xiao_nrf52840_sense": {
        "src": [("xiao/XIAO-nRF52840 v15.step", XIAO_RULES, None)],
        "mask": "black", "yup": True,
        "frame": frame_pcb() + "; USB-C at +x" ,
        "source": "Seeed XIAO nRF52840 3D model",
    },
    "hub_ch334f": {
        "src": [("kicad_out/hub4.step", KICAD_RULES, None),
                ("ada/5997-CH334F-4-Port-Hub.step", ADA_RULES, None)],
        "mask": "black", "align": "hub",
        "frame": frame_pcb() + "; upstream USB-C at +y",
        "source": "Adafruit CAD parts 5997 STEP (components) + Adafruit CH334F Eagle board via KiCad (mask, silk, pads)",
    },
    "sht31": {
        "src": [("kicad_out/sht31qt.step", KICAD_RULES, None),
                ("ada/2857_SHT31-D.step", ADA_RULES, None)],
        "mask": "black", "align": "hub",
        "frame": frame_pcb() + "; 25.4 mm edge along x",
        "source": "Adafruit CAD parts 2857 STEP + Adafruit SHT31-D STEMMA QT Eagle board via KiCad",
    },
    "max30101": {
        "src": [("kicad_out/max30101.step", KICAD_RULES, None)],
        "mask": "red",
        "frame": frame_pcb("(MAX30101 and both Qwiic sockets)"),
        "source": "SparkFun SEN-16474 Eagle board via KiCad, KiCad library models per package",
    },
    "speaker": {
        "src": [("ada/3968_Speaker_40mm.step", [(None, None, "speaker")], None)],
        "flip": True,
        "frame": "axis +z, z = 0 on the front face of the rim, magnet toward -z",
        "source": "Adafruit CAD parts 3968 STEP",
        "speaker": True,
    },
}


def speaker_face(v):
    """the Adafruit 3968 model is one uncoloured solid: name its faces from where they sit (front at z = 0)."""
    r = np.hypot(v[:, 0], v[:, 1])
    z0, z1, r0, r1 = v[:, 2].min(), v[:, 2].max(), r.min(), r.max()
    if z1 <= 2.01 and r1 <= 9.95:
        return "cone_paper"
    if z1 <= 2.01 and r1 <= 13.95:
        return "rubber_black"
    if z1 <= 2.01 and r0 >= 13.9 and r1 < 19.9:
        return "rubber_black"
    if 7.0 <= z0 and z1 <= 16.01 and r1 < 12.0:
        return "copper"
    return "steel"


def classify(rules, path, col):
    for rx, test, mat in rules:
        if rx is not None and not re.search(rx, path):
            continue
        if test is not None and not test(col):
            continue
        return mat
    return "epoxy_black"


def up_split(v, t, up, rest):
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return np.where(n[:, 2] > 0.9, up, rest)


def board_split(v, t, mask):
    """board body: faces whose normal is vertical are the masked faces, the rest is the routed edge."""
    n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    return np.where(np.abs(n[:, 2]) > 0.9, f"solder_mask_{mask}", "fr4_edge")


def cyl_info(face, v):
    """(cx, cy, r, angular span in degrees) when the face is a cylinder with a vertical axis."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    a = BRepAdaptor_Surface(face)
    if a.GetType() != GeomAbs_Cylinder:
        return None
    r = a.Cylinder().Radius()
    span = v[:, 2].max() - v[:, 2].min()
    if span < 0.3:
        return None
    # circle fit on the tessellated points, already in the assembly frame
    x, y = v[:, 0], v[:, 1]
    A = np.stack([x, y, np.ones_like(x)], axis=1)
    sol = np.linalg.lstsq(A, -(x * x + y * y), rcond=None)[0]
    c = np.array([-sol[0] / 2, -sol[1] / 2])
    ang = np.degrees(np.arctan2(v[:, 1] - c[1], v[:, 0] - c[0]))
    srt = np.sort(ang)
    gaps = np.diff(np.concatenate([srt, [srt[0] + 360]]))
    return c[0], c[1], r, 360 - gaps.max()


HOLES = []


def gather(spec):
    out = []
    for fn, rules, skip in spec["src"]:
        leaves, ctool = read(VEN / fn)
        for lf in leaves:
            path = "/".join(lf["names"])
            if skip and re.search(skip, path):
                continue
            coarse = re.search(r"_(tracks?|copper|vias?|pads?)$|BGA", path)
            tol, ang = (0.03, 0.4) if coarse else (0.01, 0.2)
            for col, v, t, _ in faces_of(lf, ctool, tol=tol, ang=ang):  # noqa: B007
                c = col or lf["colour"]
                mat = classify(rules, path, c)
                if mat == "speaker":
                    mat = speaker_face(v)
                if mat == "board" and not fn.startswith("ada"):
                    ci = cyl_info(_, v)
                    if ci:
                        HOLES.append(ci)
                if mat != "drop":
                    out.append((fn, path, mat, v, t, c))
    return out


def yup_to_zup(v):
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1)


def debug(faces, top=30):
    from collections import Counter
    n, mats = Counter(), {}
    for fn, p, m, v, t, c in faces:
        key = re.sub(r"=>\[[^\]]*\]", "", p)[-70:]
        n[key] += len(t)
        mats.setdefault(key, set()).add((m, c))
    for k, c in n.most_common(top):
        print(c, k, sorted(mats[k], key=str)[:4])


def holes_of(flip, centre):
    groups = []
    for x, y, r, span in HOLES:
        for g in groups:
            if abs(g[0] - x) < 0.05 and abs(g[1] - y) < 0.05 and abs(g[2] - r) < 0.02:
                g[3] += span
                break
        else:
            groups.append([x, y, r, span])
    out = []
    for x, y, r, span in groups:
        if span < 300 or r < 0.2:
            continue
        y = -y if flip else y
        out.append([round(x - centre[0], 3), round(y - centre[1], 3), round(2 * r, 3)])
    return sorted(out)


def build(name, spec):
    HOLES.clear()
    faces = gather(spec)
    if "--debug" in sys.argv:
        debug(faces)
    if spec.get("yup"):
        faces = [(fn, p, m, yup_to_zup(v), t, c) for fn, p, m, v, t, c in faces]
    if spec.get("flip"):
        faces = [(fn, p, m, v * np.array([1, -1, -1]), t[:, [0, 2, 1]], c) for fn, p, m, v, t, c in faces]
    if spec.get("align"):
        # the KiCad board and the Adafruit component STEP share the Eagle outline: align on the board extents
        def ext(sel):
            vs = np.concatenate([v for fn, p, m, v, t, c in faces if sel(fn, m)])
            return vs.min(0), vs.max(0)
        k_lo, k_hi = ext(lambda fn, m: fn.startswith("kicad_out") and m == "board")
        a_lo, a_hi = ext(lambda fn, m: fn.startswith("ada") and m == "board")
        print("board extents kicad", (k_hi - k_lo).round(3), "adafruit", (a_hi - a_lo).round(3))
        faces = align_ada(faces, np.array([k_lo[0], k_lo[1], k_hi[2]]), np.array([a_lo[0], a_lo[1], a_hi[2]]))
    verts, tris, mats, main = [], [], [], []
    base = 0
    for fn, p, m, v, t, c in faces:
        main.append(np.full(len(t), m == "board" and not (spec.get("align") and fn.startswith("ada"))))
        if m.startswith("board"):
            tri_m = board_split(v, t, m.split(":")[1] if ":" in m else spec["mask"])
        elif m in ("solder_mask", "copper_under_mask"):
            tri_m = np.full(len(t), f"{m}_{spec['mask']}" if m == "solder_mask" else f"copper_under_mask_{spec['mask']}")
        elif m == "shield":
            tri_m = up_split(v, t, "label_white", "steel")
        else:
            tri_m = np.full(len(t), m)
        verts.append(v)
        tris.append(t + base)
        mats.append(tri_m)
        base += len(v)
    v = np.concatenate(verts)
    t = np.concatenate(tris)
    m = np.concatenate(mats)
    board = np.concatenate(main)
    ref = v[np.unique(t[board])] if board.any() else v
    lo, hi = ref.min(0), ref.max(0)
    centre = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    if spec.get("speaker"):
        lo, hi = v.min(0), v.max(0)
        centre = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2]])
    v = v - centre
    names = sorted(set(m.tolist()))
    idx = {n: i for i, n in enumerate(names)}
    mi = np.array([idx[x] for x in m], dtype=np.int16)
    DET.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(DET / f"{name}.npz", verts=v.astype(np.float32), tris=t.astype(np.int32), mat=mi)
    bl, bh = v.min(0), v.max(0)
    meta = {"asset": name, "source": spec["source"], "frame": spec["frame"], "units": "mm",
            "mask_colour": spec.get("mask"), "materials": names,
            "bbox_min": [round(x, 3) for x in bl.tolist()], "bbox_max": [round(x, 3) for x in bh.tolist()],
            "board_bbox": None if not board.any() else
            [[round(x, 3) for x in (lo - centre).tolist()], [round(x, 3) for x in (hi - centre).tolist()]],
            "holes_xyd": holes_of(spec.get("flip"), centre), "triangles": int(len(t))}
    (DET / f"{name}.json").write_text(json.dumps(meta, indent=1))
    counts = {n: int((mi == idx[n]).sum()) for n in names}
    print(name, len(t), "tris", "bbox", meta["bbox_min"], meta["bbox_max"], counts)


def align_ada(faces, k_lo, a_lo):
    """move the Adafruit component STEP onto the KiCad board (same Eagle outline) and drop its plain board."""
    rest = [f for f in faces if not f[0].startswith("ada")]
    ada = [f for f in faces if f[0].startswith("ada") and f[2] not in ("board", "enig_board")]
    shift = k_lo - a_lo
    return rest + [(fn, p, m, v + shift, t, c) for fn, p, m, v, t, c in ada]

def main(names):
    names = [n for n in names if not n.startswith("--")]
    for n in names or list(ASSETS):
        build(n, ASSETS[n])


if __name__ == "__main__":
    main(sys.argv[1:])
