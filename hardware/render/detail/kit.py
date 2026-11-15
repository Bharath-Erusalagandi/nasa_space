"""shared helpers for the hand-built detail assets: meshes, materials, saving, previews.

assets are authored and saved in millimetres (1 blender unit = 1 mm, scene unit scale 0.001), the same
convention as the vendor assets in build/detail; previews put everything under a 0.001 scaled root.
"""

import json
import math
import sys
from pathlib import Path

import bpy  # noqa: I001
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HW = Path(__file__).resolve().parents[2]
OUT = HW / "build" / "detail"
PREV = OUT / "previews"
MESH = HW / "build" / "meshes"
HDRI = HW / "build" / "hdri" / "studio_small_09_1k.hdr"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MM = 0.001
GROUND_Z = -9.8  # pod frame: bottom of the rubber pads


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()
    us = bpy.context.scene.unit_settings
    us.system, us.length_unit, us.scale_length = "METRIC", "MILLIMETERS", 0.001


def link(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


# mesh building
def mesh_obj(name, verts, faces, mat=None, smooth=True, mat_idx=None, mats=None, coll=None, recalc=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(int(i) for i in f) for f in faces])
    me.validate(clean_customdata=False)
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    for m in (mats or [mat]):
        if m is not None:
            me.materials.append(m)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.asarray(mat_idx, dtype=np.int32)[:len(me.polygons)])
    me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
    ob = bpy.data.objects.new(name, me)
    link(ob, coll)
    return ob


def rev_rows(rows, segs, theta0=0.0, pole_start=None, pole_end=None, closed=False):
    """surface of revolution around +Z. rows: list of (r, z), each scalar or an array of length segs.
    pole_start / pole_end: z of a closing vertex on the axis. returns verts, faces."""
    th = theta0 + np.arange(segs) * 2 * math.pi / segs
    c, s = np.cos(th), np.sin(th)
    V, F = [], []
    if pole_start is not None:
        V.append((0.0, 0.0, pole_start))
    base = len(V)
    for r, z in rows:
        r = np.broadcast_to(np.asarray(r, float), (segs,))
        z = np.broadcast_to(np.asarray(z, float), (segs,))
        V += list(zip(r * c, r * s, z))
    n = len(rows)
    for i in range(n - 1 + (1 if closed else 0)):
        a, b = base + i * segs, base + ((i + 1) % n) * segs
        for j in range(segs):
            j1 = (j + 1) % segs
            F.append((a + j, a + j1, b + j1, b + j))
    if pole_start is not None:
        F += [(0, base + (j + 1) % segs, base + j) for j in range(segs)]
    if pole_end is not None:
        V.append((0.0, 0.0, pole_end))
        e, a = len(V) - 1, base + (n - 1) * segs
        F += [(a + j, a + (j + 1) % segs, e) for j in range(segs)]
    return np.array(V), F


def lathe(name, prof, segs, mat, pole_start=None, pole_end=None, closed=False, theta0=0.0, coll=None, smooth=True):
    v, f = rev_rows([(r, z) for r, z in prof], segs, theta0, pole_start, pole_end, closed)
    return mesh_obj(name, v, f, mat, smooth=smooth, coll=coll)


def transform(ob, M):
    ob.data.transform(M)
    ob.data.update()
    return ob


def rot_to(axis_from, axis_to):
    return Vector(axis_from).rotation_difference(Vector(axis_to)).to_matrix().to_4x4()


def frame_matrix(origin, z_dir, x_hint=(1, 0, 0)):
    z = Vector(z_dir).normalized()
    x = Vector(x_hint)
    x = (x - z * x.dot(z))
    if x.length < 1e-6:
        x = Vector((0, 1, 0)) - z * z.y
    x.normalize()
    y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4()
    M.translation = Vector(origin)
    return M


def superellipse(a, b, n, th):
    """radius of |x/a|^n + |y/b|^n = 1 along angle th."""
    c, s = np.abs(np.cos(th)), np.abs(np.sin(th))
    return 1.0 / ((c / a) ** n + (s / b) ** n) ** (1.0 / n)


def rounded_rect_r(w, h, rc, th):
    """polar radius of a w x h rectangle with corner radius rc, centred, along angle th."""
    out = np.empty_like(th)
    hw, hh = w / 2, h / 2
    for i, t in enumerate(th):
        d = np.array([math.cos(t), math.sin(t)])
        lo, hi = 0.0, max(w, h)
        for _ in range(40):
            m = (lo + hi) / 2
            p = np.abs(d * m)
            q = np.maximum(p - np.array([hw - rc, hh - rc]), 0)
            inside = (p[0] <= hw and p[1] <= hh) and (np.hypot(*q) <= rc if (q > 0).all() else True)
            lo, hi = (m, hi) if inside else (lo, m)
        out[i] = lo
    return out


def boolean(ob, cutter, op="DIFFERENCE", keep=False):
    md = ob.modifiers.new("bool", "BOOLEAN")
    md.object, md.operation, md.solver = cutter, op, "EXACT"
    apply_mods(ob)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)
    return ob


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def bevel_mod(ob, width, seg=3, angle=40):
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width, md.segments, md.limit_method = width, seg, "ANGLE"
    md.angle_limit = math.radians(angle)
    md.harden_normals = False
    return md


def cube(name, size, center, mat, bevel=0.0, seg=3, coll=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(center)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mat:
        me.materials.append(mat)
    ob = link(bpy.data.objects.new(name, me), coll)
    if bevel > 0:
        bevel_mod(ob, bevel, seg)
        apply_mods(ob)
        ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
        auto_smooth(ob)
    return ob


def auto_smooth(ob, angle=35):
    try:
        with bpy.context.temp_override(object=ob, selected_editable_objects=[ob], active_object=ob):
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:  # noqa: BLE001
        md = ob.modifiers.new("smooth", "NODES")
        bpy.ops.object.shade_smooth()
    return ob


def text_obj(name, body, size, mat, extrude=0.0, font=FONT, align="CENTER", coll=None):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.align_x, cu.align_y = align, "CENTER"
    cu.resolution_u = 4
    tmp = link(bpy.data.objects.new(name + "_tmp", cu), coll)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    if mat:
        me.materials.append(mat)
    return link(bpy.data.objects.new(name, me), coll)


def join(objs, name):
    objs = [o for o in objs if o is not None]
    with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, object=objs[0]):
        bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


# paths, tubes and strips
def catmull(ctrl, t0=None, t1=None, step=0.25):
    """smooth path through control points (mm) with optional end tangents, resampled every `step` mm."""
    P = [np.array(p, float) for p in ctrl]
    first = P[0] - (np.array(t0, float) / np.linalg.norm(t0) * np.linalg.norm(P[1] - P[0]) if t0 is not None
                    else (P[1] - P[0]))
    last = P[-1] + (np.array(t1, float) / np.linalg.norm(t1) * np.linalg.norm(P[-1] - P[-2]) if t1 is not None
                    else (P[-1] - P[-2]))
    pts = [first] + P + [last]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        # centripetal parametrisation
        def tj(ti, a, b):
            return ti + max(np.linalg.norm(b - a), 1e-6) ** 0.5
        ta, tb = 0.0, tj(0.0, p0, p1)
        tc = tj(tb, p1, p2)
        td = tj(tc, p2, p3)
        n = max(8, int(np.linalg.norm(p2 - p1) / step * 2))
        for t in np.linspace(tb, tc, n, endpoint=False):
            a1 = (tb - t) / (tb - ta) * p0 + (t - ta) / (tb - ta) * p1
            a2 = (tc - t) / (tc - tb) * p1 + (t - tb) / (tc - tb) * p2
            a3 = (td - t) / (td - tc) * p2 + (t - tc) / (td - tc) * p3
            b1 = (tc - t) / (tc - ta) * a1 + (t - ta) / (tc - ta) * a2
            b2 = (td - t) / (td - tb) * a2 + (t - tb) / (td - tb) * a3
            out.append((tc - t) / (tc - tb) * b1 + (t - tb) / (tc - tb) * b2)
    out.append(P[-1])
    return resample(np.array(out), step)


def resample(P, step):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(round(d[-1] / step)) + 1)
    s = np.linspace(0, d[-1], n)
    return np.stack([np.interp(s, d, P[:, k]) for k in range(3)], axis=1)


def path_len(P):
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


def min_bend_radius(P, skip=2.0, where=False):
    """smallest radius of curvature along a resampled path, ignoring `skip` mm at each end."""
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    T = np.diff(P, axis=0) / d[:, None]
    ang = np.arccos(np.clip((T[1:] * T[:-1]).sum(1), -1, 1))
    ds = (d[1:] + d[:-1]) / 2
    s = np.cumsum(ds)
    k = ang / ds
    # smooth over 2 mm so sampling noise does not dominate
    w = max(1, int(2.0 / ds.mean()))
    k = np.convolve(k, np.ones(w) / w, mode="same")
    m = (s > skip) & (s < s[-1] - skip)
    if not m.any() or k[m].max() <= 0:
        return (float("inf"), None) if where else float("inf")
    i = np.where(m)[0][np.argmax(k[m])]
    return (float(1 / k[i]), P[i + 1].round(1).tolist()) if where else float(1 / k[i])


def frames(P, n0=None):
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    if n0 is None:
        a = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
        n0 = np.cross(T[0], a)
    N = np.zeros_like(P)
    n = np.array(n0, float)
    for i in range(len(P)):
        n = n - n.dot(T[i]) * T[i]
        n /= np.linalg.norm(n)
        N[i] = n
    B = np.cross(T, N)
    return T, N, B


def tube_mesh(P, radius, segs=16, n0=None, rfun=None, caps=True, twist=0.0):
    """tube along path P. radius scalar or per-point array; rfun(i, theta, s) -> extra radial offset."""
    T, N, B = frames(P, n0)
    r = np.broadcast_to(np.asarray(radius, float), (len(P),))
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    th0 = np.arange(segs) * 2 * math.pi / segs
    V, F = [], []
    for i in range(len(P)):
        th = th0 + twist * s[i]
        rr = r[i] + (rfun(i, th, s[i]) if rfun else 0.0)
        ring = P[i] + (rr * np.cos(th))[:, None] * N[i] + (rr * np.sin(th))[:, None] * B[i]
        V.append(ring)
    V = np.concatenate(V)
    for i in range(len(P) - 1):
        a, b = i * segs, (i + 1) * segs
        for j in range(segs):
            j1 = (j + 1) % segs
            F.append((a + j, a + j1, b + j1, b + j))
    if caps:
        V = np.vstack([V, P[0], P[-1]])
        c0, c1 = len(V) - 2, len(V) - 1
        last = (len(P) - 1) * segs
        F += [(c0, (j + 1) % segs, j) for j in range(segs)]
        F += [(last + j, last + (j + 1) % segs, c1) for j in range(segs)]
    return V, F


def tube(name, P, radius, mat, segs=16, n0=None, rfun=None, caps=True, coll=None, twist=0.0):
    v, f = tube_mesh(P, radius, segs, n0, rfun, caps, twist)
    return mesh_obj(name, v, f, mat, coll=coll, recalc=False)


def strip_mesh(P, width, thick, n0, edge_r=0.08, nw=24):
    """flat strip along P: width along N, thickness along B, rounded long edges."""
    T, N, B = frames(P, n0)
    hw, ht = width / 2, thick / 2
    # cross-section loop: rectangle with small rounded corners
    sec = []
    for cx, cy, a0 in ((hw - edge_r, ht - edge_r, 0), (-hw + edge_r, ht - edge_r, 90),
                       (-hw + edge_r, -ht + edge_r, 180), (hw - edge_r, -ht + edge_r, 270)):
        for a in np.linspace(a0, a0 + 90, 4):
            sec.append((cx + edge_r * math.cos(math.radians(a)), cy + edge_r * math.sin(math.radians(a))))
    sec = np.array(sec)
    m = len(sec)
    V = np.concatenate([P[i] + sec[:, :1] * N[i] + sec[:, 1:] * B[i] for i in range(len(P))])
    F = []
    for i in range(len(P) - 1):
        a, b = i * m, (i + 1) * m
        for j in range(m):
            j1 = (j + 1) % m
            F.append((a + j, a + j1, b + j1, b + j))
    last = (len(P) - 1) * m
    F.append(tuple(range(m))[::-1])
    F.append(tuple(range(last, last + m)))
    return V, F, (T, N, B)


# materials
_MATS = {}


class Nodes:
    def __init__(self, m):
        m.use_nodes = True
        self.t = m.node_tree
        self.t.nodes.clear()
        self.out = self.new("ShaderNodeOutputMaterial")
        self.bsdf = self.new("ShaderNodeBsdfPrincipled")
        self.link(self.bsdf, 0, self.out, 0)

    def new(self, kind, **props):
        n = self.t.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, ao, b, bi):
        self.t.links.new(a.outputs[ao], b.inputs[bi])

    def set(self, **vals):
        for k, v in vals.items():
            self.bsdf.inputs[k.replace("_", " ")].default_value = v

    def bump(self, scale, strength, distance, kind="noise", detail=4.0):
        """micro surface only (tool marks, grain); shape is always geometry."""
        tc = self.new("ShaderNodeTexCoord")
        if kind == "voronoi":
            tx = self.new("ShaderNodeTexVoronoi", feature="SMOOTH_F1")
            tx.inputs["Scale"].default_value = scale
            out = "Distance"
        else:
            tx = self.new("ShaderNodeTexNoise")
            tx.inputs["Scale"].default_value = scale
            tx.inputs["Detail"].default_value = detail
            out = "Fac"
        self.link(tc, "Object", tx, 0)
        b = self.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        self.t.links.new(tx.outputs[out], b.inputs["Height"])
        self.link(b, 0, self.bsdf, "Normal")
        return b


def srgb(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def _mk(name, base, rough, metal=0.0, bump=None, **extra):
    m = bpy.data.materials.new(name)
    n = Nodes(m)
    n.set(**{"Base Color": (*base, 1.0), "Roughness": rough, "Metallic": metal, **extra})
    if bump:
        n.bump(*bump)
    return m


def M(name):
    """physically based materials, linear colours. cached by name."""
    if name in _MATS:
        return _MATS[name]
    lib = {
        # metals
        "nickel": dict(base=(0.66, 0.62, 0.56), rough=0.16, metal=1.0, bump=(9000, 0.08, 2e-5)),
        "nickel_satin": dict(base=(0.62, 0.59, 0.54), rough=0.32, metal=1.0, bump=(9000, 0.15, 2e-5)),
        "tin": dict(base=(0.72, 0.72, 0.70), rough=0.28, metal=1.0, bump=(6000, 0.1, 2e-5)),
        "solder": dict(base=(0.7, 0.7, 0.68), rough=0.2, metal=1.0, bump=(2500, 0.12, 3e-5)),
        "copper": dict(base=(0.93, 0.60, 0.48), rough=0.28, metal=1.0),
        "gold": dict(base=(1.0, 0.76, 0.34), rough=0.18, metal=1.0),
        "brass": dict(base=(0.86, 0.68, 0.38), rough=0.3, metal=1.0, bump=(7000, 0.12, 2e-5)),
        "black_oxide": dict(base=(0.045, 0.045, 0.048), rough=0.38, metal=1.0, bump=(5000, 0.15, 2e-5),
                            **{"Coat Weight": 0.25, "Coat Roughness": 0.25}),
        "stainless": dict(base=(0.6, 0.6, 0.58), rough=0.26, metal=1.0, bump=(7000, 0.1, 2e-5)),
        "steel_zinc": dict(base=(0.68, 0.70, 0.72), rough=0.3, metal=1.0, bump=(4000, 0.12, 2e-5)),
        "steel_black_paint": dict(base=(0.025, 0.025, 0.027), rough=0.42, metal=0.0, bump=(3000, 0.1, 2e-5),
                                  **{"Coat Weight": 0.3, "Coat Roughness": 0.3}),
        "silver_plate": dict(base=(0.85, 0.85, 0.82), rough=0.2, metal=1.0),
        # plastics and elastomers
        "pvc_black": dict(base=(0.016, 0.016, 0.017), rough=0.5, bump=(2500, 0.1, 2e-5)),
        "pvc_red": dict(base=srgb((0.62, 0.05, 0.04)), rough=0.38, bump=(2500, 0.08, 2e-5)),
        "pvc_white": dict(base=srgb((0.86, 0.86, 0.84)), rough=0.4, bump=(2500, 0.08, 2e-5),
                          **{"Subsurface Weight": 0.15}),
        "pvc_green": dict(base=srgb((0.08, 0.42, 0.16)), rough=0.38, bump=(2500, 0.08, 2e-5)),
        "pvc_blue": dict(base=srgb((0.06, 0.2, 0.55)), rough=0.38, bump=(2500, 0.08, 2e-5)),
        "pvc_yellow": dict(base=srgb((0.86, 0.68, 0.06)), rough=0.38, bump=(2500, 0.08, 2e-5)),
        "pvc_wire_black": dict(base=(0.012, 0.012, 0.013), rough=0.34, bump=(2500, 0.08, 2e-5)),
        "silicone_red": dict(base=srgb((0.66, 0.07, 0.05)), rough=0.55, **{"Subsurface Weight": 0.1}),
        "silicone_black": dict(base=(0.015, 0.015, 0.016), rough=0.6),
        "tpe_black": dict(base=(0.018, 0.018, 0.019), rough=0.48, bump=(1800, 0.12, 2e-5)),
        "braid_black": dict(base=(0.02, 0.02, 0.022), rough=0.55, **{"Sheen Weight": 0.5, "Sheen Roughness": 0.35}),
        "heatshrink_black": dict(base=(0.014, 0.014, 0.015), rough=0.55, bump=(1200, 0.1, 2e-5)),
        "abs_black_gloss": dict(base=(0.012, 0.012, 0.013), rough=0.22, bump=(1500, 0.05, 1e-5)),
        "abs_black_matte": dict(base=(0.02, 0.02, 0.021), rough=0.62, bump=(2200, 0.25, 2e-5)),
        "abs_grey": dict(base=srgb((0.33, 0.33, 0.34)), rough=0.5, bump=(2200, 0.2, 2e-5)),
        "nylon_natural": dict(base=srgb((0.86, 0.84, 0.76)), rough=0.42, **{"Subsurface Weight": 0.35,
                                                                            "Subsurface Scale": 0.0005}),
        "nylon_black": dict(base=(0.02, 0.02, 0.021), rough=0.45),
        "jst_ivory": dict(base=srgb((0.92, 0.9, 0.82)), rough=0.4, **{"Subsurface Weight": 0.3,
                                                                     "Subsurface Scale": 0.0004}),
        "pbt_black": dict(base=(0.02, 0.02, 0.021), rough=0.4),
        "pbt_white": dict(base=srgb((0.9, 0.9, 0.88)), rough=0.35),
        "pu_black": dict(base=(0.02, 0.02, 0.021), rough=0.32, **{"Coat Weight": 0.3, "Coat Roughness": 0.2}),
        "foam_black": dict(base=(0.022, 0.022, 0.024), rough=0.92, bump=(1400, 0.6, 1.2e-4, "voronoi")),
        "epoxy_clear": dict(base=(1, 1, 1), rough=0.02, **{"Transmission Weight": 1.0, "IOR": 1.52}),
        "led_die": dict(base=(0.18, 0.16, 0.2), rough=0.3, metal=0.4),
        "fpc_white": dict(base=srgb((0.9, 0.89, 0.84)), rough=0.32, **{"Subsurface Weight": 0.2,
                                                                       "Subsurface Scale": 0.0003}),
        "fpc_blue": dict(base=srgb((0.05, 0.22, 0.62)), rough=0.42),
        "ink_grey": dict(base=srgb((0.35, 0.35, 0.36)), rough=0.5),
        "resistor_body": dict(base=srgb((0.80, 0.68, 0.48)), rough=0.3, **{"Coat Weight": 0.4,
                                                                           "Coat Roughness": 0.2}),
        "band_brown": dict(base=srgb((0.36, 0.18, 0.08)), rough=0.3, **{"Coat Weight": 0.4}),
        "band_black": dict(base=(0.015, 0.015, 0.015), rough=0.3, **{"Coat Weight": 0.4}),
        "band_red": dict(base=srgb((0.75, 0.08, 0.06)), rough=0.3, **{"Coat Weight": 0.4}),
        "band_blue": dict(base=srgb((0.1, 0.25, 0.7)), rough=0.3, **{"Coat Weight": 0.4}),
        "band_grey": dict(base=srgb((0.5, 0.5, 0.5)), rough=0.3, **{"Coat Weight": 0.4}),
        "band_gold": dict(base=(0.7, 0.52, 0.22), rough=0.3, metal=0.8),
        "paper_cone": dict(base=(0.02, 0.02, 0.022), rough=0.85, bump=(600, 0.5, 4e-5)),
        "rubber_surround": dict(base=(0.018, 0.018, 0.019), rough=0.55),
        "ferrite": dict(base=(0.05, 0.05, 0.052), rough=0.7, bump=(5000, 0.4, 3e-5)),
        "lacquer_jack_green": dict(base=srgb((0.25, 0.65, 0.2)), rough=0.35),
        "lacquer_jack_pink": dict(base=srgb((0.9, 0.42, 0.62)), rough=0.35),
        "led_lens_green": dict(base=srgb((0.4, 0.9, 0.4)), rough=0.1, **{"Transmission Weight": 0.8}),
        "clay": dict(base=srgb((0.7, 0.7, 0.69)), rough=0.75),
        "clay_dark": dict(base=srgb((0.25, 0.25, 0.26)), rough=0.7),
    }
    d = dict(lib[name])
    base, rough = d.pop("base"), d.pop("rough")
    metal, bump = d.pop("metal", 0.0), d.pop("bump", None)
    m = _mk(name, base, rough, metal, bump, **d)
    _MATS[name] = m
    return m


# saving
def finalize_scale():
    for ob in bpy.context.scene.objects:
        if ob.type == "MESH" and ob.modifiers:
            apply_mods(ob)


def save(asset, meta, groups=None):
    """groups: {collection name: [objects]}; everything else goes into a collection named after the asset."""
    finalize_scale()
    sc = bpy.context.scene
    groups = groups or {asset: [o for o in sc.collection.objects]}
    for cname, objs in groups.items():
        coll = bpy.data.collections.new(cname)
        sc.collection.children.link(coll)
        for o in objs:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
    sc["detail_asset"] = json.dumps(meta)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{asset}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    print("saved", path.name, flush=True)
    return path


# previews
def load_context(names, mat="clay"):
    """CAD meshes from build/meshes (pod frame, mm) as matte clay for context."""
    obs = []
    for n in names:
        f = MESH / f"{n}.npz"
        if not f.exists():
            continue
        d = np.load(f)
        me = bpy.data.meshes.new("ctx_" + n)
        v = d["v"].astype(np.float32)
        fa = d["f"]
        me.vertices.add(len(v))
        me.vertices.foreach_set("co", v.ravel())
        me.loops.add(fa.size)
        me.loops.foreach_set("vertex_index", fa.ravel())
        me.polygons.add(len(fa))
        me.polygons.foreach_set("loop_start", np.arange(0, fa.size, 3, dtype=np.int32))
        me.update(calc_edges=True)
        me.materials.append(M(mat) if isinstance(mat, str) else mat)
        obs.append(link(bpy.data.objects.new("ctx_" + n, me)))
    return obs


def stage(ground_z, size=1.0):
    sc = bpy.context.scene
    gm = bpy.data.materials.new("ground")
    n = Nodes(gm)
    n.set(**{"Base Color": (*srgb((0.6, 0.6, 0.59)), 1), "Roughness": 0.85})
    n.bump(300, 0.08, 1e-4)
    bpy.ops.mesh.primitive_plane_add(size=size * 8, location=(0, 0, ground_z))
    g = bpy.context.object
    g.name = "ground"
    g.data.materials.append(gm)
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    if HDRI.exists():
        env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(HDRI))
        w.node_tree.links.new(env.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 0.4
    else:
        bg.inputs[1].default_value = 0.4
    return g


def area_light(name, loc, target, size, power, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape, ld.size, ld.energy, ld.color = "DISK", size, power, color
    lo = link(bpy.data.objects.new(name, ld))
    lo.location = loc
    lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


def bbox_of(objs):
    pts = []
    for o in objs:
        if o.type != "MESH" or len(o.data.vertices) == 0:
            continue
        v = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get("co", v)
        v = v.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        v = v @ mw[:3, :3].T + mw[:3, 3]
        pts.append(v.min(0))
        pts.append(v.max(0))
    pts = np.array(pts)
    return pts.min(0), pts.max(0)


def preview(asset, subject, az=-35, el=28, lens=100, ground_z=None, fill=0.82, target=None, dist_scale=1.0,
            res=800, samples=32, fstop=None, extra_lights=True, name=None, radius=None, hide=()):
    """render subject objects at res x res on a neutral ground. az/el in degrees, camera looks at the bbox."""
    sc = bpy.context.scene
    for o in list(sc.objects):
        if o.type in ("LIGHT", "CAMERA") or o.name.startswith("ground"):
            bpy.data.objects.remove(o, do_unlink=True)
    root = sc.objects.get("preview_root")
    if root is None:
        root = link(bpy.data.objects.new("preview_root", None))
        root.scale = (MM, MM, MM)
    for o in sc.objects:
        if o.type == "MESH" and o.parent is None and not o.name.startswith("ground"):
            o.parent = root
    bpy.context.view_layer.update()
    lo, hi = bbox_of(subject)
    ctr = (lo + hi) / 2 if target is None else np.array(target) * MM
    rad = float(np.linalg.norm(hi - lo)) / 2 if radius is None else radius * MM
    for o in hide:
        o.hide_render = True
    gz = lo[2] - 0.0002 if ground_z is None else ground_z * MM
    stage(gz, max(rad * 4, 0.3))
    fov = 2 * math.atan(18 / lens)
    dist = rad / math.sin(fov / 2) * fill * dist_scale
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    link(cam)
    sc.camera = cam
    cam.location = Vector(ctr) + d * dist
    cam.rotation_euler = (Vector(ctr) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens, cam.data.sensor_width = lens, 36
    cam.data.clip_start = dist * 0.02
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = dist
        cam.data.dof.aperture_fstop = fstop
    s = max(rad * 3, 0.03)
    key = Vector(ctr) + Vector((-0.8, -0.6, 0.9)).normalized() * s * 3
    area_light("key", key, ctr, s * 1.6, 3.0 * (s / 0.1) ** 2, (1.0, 0.97, 0.93))
    if extra_lights:
        area_light("rim", Vector(ctr) + Vector((0.6, 0.8, 0.6)).normalized() * s * 3, ctr, s, 1.4 * (s / 0.1) ** 2)
        area_light("fill", Vector(ctr) + Vector((0.9, -0.5, 0.3)).normalized() * s * 3, ctr, s * 2,
                   0.8 * (s / 0.1) ** 2, (0.95, 0.97, 1.0))
    r = sc.render
    r.engine = "CYCLES"
    c = sc.cycles
    c.device, c.samples = "CPU", samples
    c.use_adaptive_sampling, c.use_denoising, c.denoiser = True, True, "OPENIMAGEDENOISE"
    c.max_bounces, c.glossy_bounces, c.transmission_bounces, c.transparent_max_bounces = 12, 6, 12, 8
    r.threads_mode, r.threads = "FIXED", 6
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = -0.3
    im = r.image_settings
    im.file_format, im.quality, im.color_mode = "JPEG", 88, "RGB"
    PREV.mkdir(parents=True, exist_ok=True)
    r.filepath = str(PREV / f"detail-{name or asset}.jpg")
    bpy.ops.render.render(write_still=True)
    print("preview", r.filepath, flush=True)


def report(asset, **facts):
    f = OUT / "facts.json"
    data = json.loads(f.read_text()) if f.exists() else {}
    data[asset] = facts
    f.write_text(json.dumps(data, indent=1))


def argv():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def prism_xz(name, pts, y0, y1, mat, bevel=0.0, coll=None):
    """prism from a polygon in the xz plane (counter-clockwise seen from -y), extruded from y0 to y1."""
    n = len(pts)
    V = [(x, y0, z) for x, z in pts] + [(x, y1, z) for x, z in pts]
    F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    F += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    ob = mesh_obj(name, V, F, mat, smooth=False, coll=coll)
    if bevel:
        bevel_mod(ob, bevel, 2, 30)
        apply_mods(ob)
        auto_smooth(ob, 30)
    return ob


def place(objs, M):
    for o in objs:
        o.data.transform(M)
        o.data.update()
    return objs


def smooth_path(pts, t0=None, t1=None, step=0.25, k=0.38, floor=None):
    """piecewise cubic bezier through pts with tangents (given at the ends, chordal inside) and handle
    length k x chord. optional floor: z below which the path rests on a surface."""
    P = [np.array(p, float) for p in pts]
    n = len(P)
    T = []
    for i in range(n):
        if i == 0 and t0 is not None:
            t = np.array(t0, float)
        elif i == n - 1 and t1 is not None:
            t = np.array(t1, float)
        else:
            t = P[min(i + 1, n - 1)] - P[max(i - 1, 0)]
        T.append(t / np.linalg.norm(t))
    out = []
    for i in range(n - 1):
        a, b = P[i], P[i + 1]
        L = np.linalg.norm(b - a)
        c1, c2 = a + T[i] * L * k, b - T[i + 1] * L * k
        m = max(8, int(L / step * 3))
        for u in np.linspace(0, 1, m, endpoint=False):
            out.append((1 - u) ** 3 * a + 3 * (1 - u) ** 2 * u * c1 + 3 * (1 - u) * u ** 2 * c2 + u ** 3 * b)
    out.append(P[-1])
    Q = resample(np.array(out), step)
    if floor is not None:
        Q[:, 2] = np.maximum(Q[:, 2], floor)
    return Q


def append_blend(asset):
    """bring the objects of a saved detail asset into the current scene (already in metres)."""
    path = OUT / f"{asset}.blend"
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = list(src.objects)
    objs = [o for o in dst.objects if o is not None]
    for o in objs:
        link(o)
    return objs


def plan_block(name, w, l, h, rc, re, mat, segs=96, n=4.0, groove=None):
    """block with a superellipse plan (w along X, l along Y), rounded top and bottom edges of radius re,
    optional parting groove (z, depth, width). origin at the bottom centre."""
    th = np.arange(segs) * 2 * math.pi / segs
    base = superellipse(w / 2, l / 2, n, th)
    rows = []
    for a in np.linspace(0, 90, 7):
        d = re * (1 - math.sin(math.radians(a)))
        rows.append((base - d, re * (1 - math.cos(math.radians(a)))))
    zs = [h * 0.5] if groove is None else [groove[0] - groove[2] / 2 - 0.02, groove[0] - groove[2] / 2,
                                            groove[0] + groove[2] / 2, groove[0] + groove[2] / 2 + 0.02]
    for i, z in enumerate(zs):
        inset = groove[1] if groove is not None and i in (1, 2) else 0.0
        rows.append((base - inset, z))
    for a in np.linspace(90, 0, 7):
        d = re * (1 - math.sin(math.radians(a)))
        rows.append((base - d, h - re * (1 - math.cos(math.radians(a)))))
    v, f = rev_rows(rows, segs, pole_start=0.0, pole_end=h)
    return auto_smooth(mesh_obj(name, v, f, mat), 35)


def relax(P, rmin, keep=3.0, floor=None, iters=4000, step=None):
    """smooth a resampled path until no point bends tighter than rmin; the first and last `keep` mm stay put
    so plug tangents hold. floor keeps it resting on a surface."""
    P = P.copy()
    ds = np.linalg.norm(np.diff(P, axis=0), axis=1).mean() if step is None else step
    nk = max(2, int(keep / ds))
    for _ in range(iters):
        a, b, c = P[:-2], P[1:-1], P[2:]
        lap = (a + c) / 2 - b
        d1, d2 = b - a, c - b
        n1, n2 = np.linalg.norm(d1, axis=1), np.linalg.norm(d2, axis=1)
        cosang = np.clip((d1 * d2).sum(1) / (n1 * n2), -1, 1)
        k = np.arccos(cosang) / ((n1 + n2) / 2)
        k = np.convolve(k, np.ones(5) / 5, mode="same")
        bad = k > 1.0 / rmin
        bad[:nk] = False
        bad[-nk:] = False
        if not bad.any():
            break
        grow = np.convolve(bad.astype(float), np.ones(15), mode="same") > 0
        grow[:nk] = False
        grow[-nk:] = False
        P[1:-1][grow] += 0.5 * lap[grow]
        if floor is not None:
            P[:, 2] = np.maximum(P[:, 2], floor)
    return resample(P, ds)
