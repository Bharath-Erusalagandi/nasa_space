"""Photoreal studio renders of pod K-01 from the CAD meshes.

Run with Blender's Python (bpy) after export_meshes.py:
  python hardware/render/render_k01.py [--preview] [shot ...]
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

HW = Path(__file__).resolve().parent.parent
MESH = HW / "build" / "meshes"
HDRI = HW / "build" / "hdri" / "studio_small_09_1k.hdr"
FINAL = HW / "out" / "renders"
PREV = HW / "build" / "previews"
MM = 0.001
PIVOT = Vector((75.0, 46.0, -9.0))
SHOTS = ["hero", "front", "top", "rear", "underside", "open", "exploded"]

PRINTED_GREY = {"shell": "Y", "rear_plate": "Y", "tray": "Z"}
PRINTED_BLACK = {"finger_cradle": "Y", "camera_bezel": "Y", "speaker_clamp": "Y", "cable_clamp": "Y"}
PRINTED_WHITE = {"sensor_capsule": "X", "capsule_clip": "X"}
MASKS = {"max30101_pcb": (0.50, 0.02, 0.03), "ov5647_pcb": (0.02, 0.17, 0.06),
         "vision_ai_v2_pcb": (0.02, 0.16, 0.06), "xiao_nrf52840_pcb": (0.01, 0.05, 0.20),
         "ch334f_pcb": (0.008, 0.008, 0.01), "sht31d_pcb": (0.008, 0.008, 0.01)}
STEEL = ("_usb_c", "xiao_shield", "usb_mic_plug", "speaker_magnet")
CHIPS = ("max30101_ic", "ch334f_chip", "sht31d_sensor")


def srgb(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


class Nodes:
    def __init__(self, mat):
        mat.use_nodes = True
        self.t = mat.node_tree
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

    def math(self, op, a, b=None, out=0):
        n = self.new("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.link(v[0], v[1], n, i) if isinstance(v, tuple) else self.link(v, out, n, i)
        return n

    def set(self, **vals):
        for k, v in vals.items():
            self.bsdf.inputs[k].default_value = v

    def normal(self, height=None, distance=3e-5, bevel=0.35):
        bev = self.new("ShaderNodeBevel", samples=6)
        bev.inputs["Radius"].default_value = bevel * MM
        if height is None:
            self.link(bev, 0, self.bsdf, "Normal")
            return
        bump = self.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = distance
        self.link(height[0], height[1], bump, "Height")
        self.link(bev, 0, bump, "Normal")
        self.link(bump, 0, self.bsdf, "Normal")


def mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m, None
    m = bpy.data.materials.new(name)
    return m, Nodes(m)


def printed_mat(name, base, rough, axis, bed=None):
    """fdm part: 0.2 mm layer lines along the print axis, textured bed face if given."""
    m, n = mat(name)
    if n is None:
        return m
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(tc, "Object", sep, 0)
    jitter = n.new("ShaderNodeTexNoise")
    jitter.inputs["Scale"].default_value = 900.0
    n.link(tc, "Object", jitter, 0)
    phase = n.math("MULTIPLY_ADD", (sep, "XYZ".index(axis)), math.pi / (0.2 * MM))
    phase.inputs[2].default_value = 0.0
    wav = n.math("SINE", phase)
    ridge = n.math("ABSOLUTE", wav)
    # layer-to-layer extrusion drift: 1d noise along the print axis, a few layers wide
    drift = n.new("ShaderNodeTexNoise", noise_dimensions="1D")
    drift.inputs["Scale"].default_value = 600.0
    drift.inputs["Detail"].default_value = 3.0
    n.link(sep, "XYZ".index(axis), drift, "W")
    ridge = n.math("MULTIPLY_ADD", ridge, 0.7)
    n.link(drift, "Fac", ridge, 2)
    tint = n.new("ShaderNodeMix", data_type="RGBA")
    n.link(drift, "Fac", tint, "Factor")
    tint.inputs[6].default_value = (*(c * 0.93 for c in base), 1)
    tint.inputs[7].default_value = (*(min(1.0, c * 1.04) for c in base), 1)
    n.link(tint, 2, n.bsdf, "Base Color")
    pebble = n.new("ShaderNodeTexNoise")
    pebble.inputs["Scale"].default_value = 1400.0
    pebble.inputs["Detail"].default_value = 4.0
    n.link(tc, "Object", pebble, 0)
    if bed:
        dot = n.new("ShaderNodeVectorMath", operation="DOT_PRODUCT")
        n.link(tc, "Normal", dot, 0)
        dot.inputs[1].default_value = bed
        mask = n.new("ShaderNodeMapRange")
        mask.inputs["From Min"].default_value = 0.92
        mask.inputs["From Max"].default_value = 0.99
        n.link(dot, "Value", mask, "Value")
        h = n.new("ShaderNodeMix", data_type="FLOAT")
        n.link(mask, 0, h, "Factor")
        n.link(ridge, 0, h, 2)
        n.link(pebble, 0, h, 3)
        height = (h, 0)
        r = n.new("ShaderNodeMix", data_type="FLOAT")
        n.link(mask, 0, r, "Factor")
        r.inputs[2].default_value = rough
        r.inputs[3].default_value = rough - 0.18
        n.link(r, 0, n.bsdf, "Roughness")
    else:
        height = (ridge, 0)
        r = n.math("MULTIPLY_ADD", (jitter, 0), 0.1)
        r.inputs[2].default_value = rough - 0.05
        n.link(r, 0, n.bsdf, "Roughness")
    n.set(**{"Specular IOR Level": 0.45, "Subsurface Weight": 0.12, "Subsurface Scale": 0.0006,
             "Subsurface Radius": (1.0, 0.9, 0.8)})
    n.normal(height, distance=7e-5, bevel=0.6)
    return m


def plain_mat(name, base, rough, metal=0.0, coat=0.0, bevel=0.25, **extra):
    m, n = mat(name)
    if n is None:
        return m
    n.set(**{"Base Color": (*base, 1), "Roughness": rough, "Metallic": metal, "Coat Weight": coat,
             "Coat Roughness": 0.12, **extra})
    n.normal(bevel=bevel)
    return m


def board_mat(name, mask):
    """solder mask with a slight gloss and sparse tinned pads on the top face."""
    m, n = mat(name)
    if n is None:
        return m
    tc = n.new("ShaderNodeTexCoord")
    grid = n.new("ShaderNodeVectorMath", operation="SCALE")
    grid.inputs["Scale"].default_value = 1 / (1.27 * MM)
    n.link(tc, "Object", grid, 0)
    cell = n.new("ShaderNodeVectorMath", operation="FLOOR")
    n.link(grid, 0, cell, 0)
    rnd = n.new("ShaderNodeTexWhiteNoise", noise_dimensions="3D")
    n.link(cell, 0, rnd, 0)
    frac = n.new("ShaderNodeVectorMath", operation="FRACTION")
    n.link(grid, 0, frac, 0)
    sep = n.new("ShaderNodeSeparateXYZ")
    n.link(frac, 0, sep, 0)
    inx = n.math("MULTIPLY", n.math("GREATER_THAN", (sep, 0), 0.22), n.math("LESS_THAN", (sep, 0), 0.78))
    iny = n.math("MULTIPLY", n.math("GREATER_THAN", (sep, 1), 0.3), n.math("LESS_THAN", (sep, 1), 0.7))
    pick = n.math("GREATER_THAN", (rnd, "Value"), 0.86)
    nz = n.new("ShaderNodeSeparateXYZ")
    n.link(tc, "Normal", nz, 0)
    top = n.math("GREATER_THAN", (nz, 2), 0.9)
    pad = n.math("MULTIPLY", n.math("MULTIPLY", inx, iny), n.math("MULTIPLY", pick, top))
    tin = n.new("ShaderNodeMix", data_type="RGBA")
    n.link(pad, 0, tin, "Factor")
    tin.inputs[6].default_value = (*mask, 1)
    tin.inputs[7].default_value = (0.78, 0.78, 0.76, 1)
    n.link(tin, 2, n.bsdf, "Base Color")
    n.link(pad, 0, n.bsdf, "Metallic")
    rr = n.math("MULTIPLY_ADD", pad, 0.0)
    rr.inputs[1].default_value = -0.05
    rr.inputs[2].default_value = 0.32
    n.link(rr, 0, n.bsdf, "Roughness")
    cw = n.math("SUBTRACT", 0.35, pad)
    n.link(cw, 0, n.bsdf, "Coat Weight")
    n.set(**{"Coat Roughness": 0.18})
    n.normal(bevel=0.15)
    return m


def braid_mat(name):
    m, n = mat(name)
    if n is None:
        return m
    tc = n.new("ShaderNodeTexCoord")
    w1 = n.new("ShaderNodeTexWave", bands_direction="DIAGONAL")
    w1.inputs["Scale"].default_value = 1100.0
    w1.inputs["Distortion"].default_value = 1.5
    n.link(tc, "Object", w1, 0)
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0, math.pi / 2, math.pi / 2)
    n.link(tc, "Object", mapping, 0)
    w2 = n.new("ShaderNodeTexWave", bands_direction="DIAGONAL")
    w2.inputs["Scale"].default_value = 1100.0
    n.link(mapping, 0, w2, 0)
    h = n.math("MULTIPLY", (w1, "Fac"), (w2, "Fac"))
    n.set(**{"Base Color": (0.018, 0.018, 0.02, 1), "Roughness": 0.62, "Sheen Weight": 0.4,
             "Sheen Roughness": 0.4})
    n.normal((h, 0), distance=1.5e-4, bevel=0.1)
    return m


def material_for(name):
    if name in PRINTED_GREY:
        bed = (0, -1, 0) if name == "shell" else (0, 1, 0) if name == "rear_plate" else (0, 0, -1)
        return printed_mat(f"petg_grey_{name}", srgb((0.78, 0.79, 0.78)), 0.6, PRINTED_GREY[name], bed)
    if name in PRINTED_BLACK:
        return printed_mat(f"petg_black_{PRINTED_BLACK[name]}", (0.02, 0.02, 0.021), 0.5, PRINTED_BLACK[name])
    if name in PRINTED_WHITE:
        return printed_mat("asa_white", srgb((0.9, 0.9, 0.88)), 0.5, PRINTED_WHITE[name])
    if name in MASKS:
        return board_mat(f"mask_{name}", MASKS[name])
    if name in CHIPS:
        return plain_mat("chip", (0.015, 0.015, 0.016), 0.45, bevel=0.1)
    if name.endswith(STEEL):
        return plain_mat("steel", (0.72, 0.72, 0.72), 0.22, metal=1.0, bevel=0.15)
    if name == "uv_led_365nm":
        return plain_mat("epoxy", srgb((0.80, 0.70, 0.98)), 0.06, bevel=0.05,
                         **{"Transmission Weight": 0.8, "IOR": 1.52})
    if name == "uv_led_leads":
        return plain_mat("tinned", (0.8, 0.8, 0.78), 0.3, metal=1.0, bevel=0.05)
    if name == "usb_c_cable":
        return braid_mat("braid")
    if name == "sht31_lead":
        return plain_mat("pvc_jacket", (0.02, 0.02, 0.022), 0.45, bevel=0.0)
    if name == "csi_ribbon":
        return plain_mat("fpc", srgb((0.86, 0.82, 0.70)), 0.35, coat=0.3, bevel=0.05)
    if name.startswith("usb_c_plug") or name == "usb_audio_adapter" or name == "usb_mic_dongle":
        return plain_mat("moulded_black", (0.025, 0.025, 0.027), 0.42, bevel=0.7)
    return plain_mat("black_plastic", (0.02, 0.02, 0.022), 0.5)


def add_mesh(name, verts, faces, mat_):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", (verts * MM).astype(np.float32).ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))
    me.update()
    me.materials.append(mat_)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def prim(name, mat_, kind, **kw):
    getattr(bpy.ops.mesh, f"primitive_{kind}_add")(**kw)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat_)
    bpy.ops.object.shade_smooth()
    return ob


def sized(ob, scale):
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def bevel(ob, w, seg=3):
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width, md.segments, md.limit_method = w, seg, "ANGLE"
    return ob


def shade_by_angle(ob, deg=40):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(deg))
    ob.select_set(False)


def screw(name, x, z, y_face, d_head=6.0, length=10.0):
    """iso 10642 m3 countersunk hex-socket screw, zinc plated, head flush with the face at y_face."""
    m = plain_mat("zinc", srgb((0.80, 0.81, 0.84)), 0.26, metal=1.0, bevel=0.12)
    head = prim(name, m, "cone", vertices=64, radius1=d_head / 2 * MM, radius2=1.5 * MM, depth=1.7 * MM,
                location=(x * MM, (y_face - 0.85 + 0.02) * MM, z * MM), rotation=(math.pi / 2, 0, 0))
    sock = prim(name + "_socket", m, "cylinder", vertices=6, radius=1.15 * MM, depth=3.0 * MM,
                location=(x * MM, (y_face + 0.02) * MM, z * MM), rotation=(-math.pi / 2, 0, 0))
    md = head.modifiers.new("socket", "BOOLEAN")
    md.object, md.operation = sock, "DIFFERENCE"
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.modifier_apply(modifier="socket")
    bpy.data.objects.remove(sock)
    shank = prim(name + "_shank", m, "cylinder", vertices=32, radius=1.45 * MM, depth=length * MM,
                 location=(x * MM, (y_face - 1.7 - length / 2) * MM, z * MM), rotation=(math.pi / 2, 0, 0))
    bpy.ops.object.select_all(action="DESELECT")
    shank.select_set(True)
    head.select_set(True)
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.join()
    bevel(head, 0.12 * MM, 2)
    shade_by_angle(head, 35)
    return head


def coin(name):
    """us quarter, 24.26 mm x 1.75 mm cupronickel with a reeded edge."""
    m, n = mat("cupronickel")
    if n is not None:
        tc = n.new("ShaderNodeTexCoord")
        sep = n.new("ShaderNodeSeparateXYZ")
        n.link(tc, "Object", sep, 0)
        ang = n.math("ARCTAN2", (sep, 1), (sep, 0))
        reed = n.math("SINE", n.math("MULTIPLY", ang, 119.0))
        nrm = n.new("ShaderNodeSeparateXYZ")
        n.link(tc, "Normal", nrm, 0)
        edge = n.math("LESS_THAN", n.math("ABSOLUTE", (nrm, 2)), 0.5)
        wear = n.new("ShaderNodeTexNoise")
        wear.inputs["Scale"].default_value = 900.0
        wear.inputs["Detail"].default_value = 6.0
        n.link(tc, "Object", wear, 0)
        h = n.math("MULTIPLY_ADD", n.math("MULTIPLY", reed, edge), 0.6)
        n.link(wear, "Fac", h, 2)
        n.set(**{"Base Color": (*srgb((0.78, 0.77, 0.74)), 1), "Metallic": 1.0, "Roughness": 0.33})
        n.normal((h, 0), distance=6e-5, bevel=0.2)
    ob = prim(name, m, "cylinder", vertices=160, radius=12.13 * MM, depth=1.75 * MM)
    bevel(ob, 0.25 * MM, 3)
    shade_by_angle(ob, 30)
    return ob


def lead(name, pts, radius, mat_, sag=0.0, twist=None):
    """flexible lead through control points (mm, pod frame), sagging under its own weight."""
    P = np.array(pts, dtype=float)
    t = np.linspace(0, 1, 120)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    seg /= seg[-1]
    C = np.stack([np.interp(t, seg, P[:, k]) for k in range(3)], 1)
    for _ in range(40):
        C[1:-1] = 0.5 * C[1:-1] + 0.25 * (C[:-2] + C[2:])
    C[:, 2] -= sag * np.sin(np.pi * t) ** 1.5
    paths = [C]
    if twist:
        sepd, pitch = twist
        T = np.gradient(C, axis=0)
        T /= np.linalg.norm(T, axis=1)[:, None]
        N = np.cross(T, (0, 0, 1.0))
        N /= np.maximum(np.linalg.norm(N, axis=1), 1e-6)[:, None]
        B = np.cross(T, N)
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]
        ph = 2 * np.pi * s / pitch
        off = sepd / 2 * (np.cos(ph)[:, None] * N + np.sin(ph)[:, None] * B)
        paths = [C + off, C - off]
    obs = []
    for i, Q in enumerate(paths):
        cu = bpy.data.curves.new(f"{name}{i}", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth, cu.bevel_resolution = radius * MM, 4
        cu.use_fill_caps = True
        sp = cu.splines.new("POLY")
        sp.points.add(len(Q) - 1)
        for p, q in zip(sp.points, Q):
            p.co = (*(q * MM), 1)
        ob = bpy.data.objects.new(f"{name}{i}", cu)
        ob.data.materials.append(mat_[i] if isinstance(mat_, list) else mat_)
        bpy.context.scene.collection.objects.link(ob)
        obs.append(ob)
    return obs


def usb_c_end(name, at, direction):
    """loose moulded usb-c plug on the end of the cable."""
    d = Vector(direction).normalized()
    q = d.to_track_quat("Z", "Y")
    rubber = plain_mat("moulded_black", (0.025, 0.025, 0.027), 0.42, bevel=0.3)
    steel = plain_mat("steel", (0.72, 0.72, 0.72), 0.22, metal=1.0, bevel=0.15)
    body = prim(name, rubber, "cube", size=1)
    sized(body, (11.5 * MM, 6.5 * MM, 22 * MM))
    body.location = Vector(at) + d * 11 * MM
    body.rotation_mode = "QUATERNION"
    body.rotation_quaternion = q
    bevel(body, 2.4 * MM, 6)
    shell = prim(name + "_shell", steel, "cube", size=1)
    sized(shell, (8.3 * MM, 2.5 * MM, 6.6 * MM))
    shell.location = Vector(at) + d * (22 + 3.3) * MM
    shell.rotation_mode = "QUATERNION"
    shell.rotation_quaternion = q
    bevel(shell, 1.2 * MM, 6)
    return [body, shell]


def cable_tail(start, pts, radius=2.0):
    cu = bpy.data.curves.new("cable_tail", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.resolution_u = radius * MM, 6, 24
    sp = cu.splines.new("BEZIER")
    all_pts = [start] + pts
    sp.bezier_points.add(len(all_pts) - 1)
    for bp, p in zip(sp.bezier_points, all_pts):
        bp.co = Vector(p) * MM
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    first = sp.bezier_points[0]
    first.handle_left_type = first.handle_right_type = "ALIGNED"
    first.handle_right = first.co + Vector((0, 0, -3 * MM))
    first.handle_left = first.co + Vector((0, 0, 3 * MM))
    ob = bpy.data.objects.new("cable_tail", cu)
    ob.data.materials.append(braid_mat("braid"))
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.shade_smooth()
    ob.select_set(False)
    return ob, Vector(all_pts[-1]) * MM, (Vector(all_pts[-1]) - Vector(all_pts[-2])).normalized()


def stage():
    floor = bpy.data.materials.new("backdrop")
    floor.use_nodes = True
    b = floor.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*srgb((0.74, 0.72, 0.69)), 1)
    b.inputs["Roughness"].default_value = 0.85
    b.inputs["Specular IOR Level"].default_value = 0.3
    verts, faces = [], []
    r, zmax, depth, w = 0.45, 2.0, 3.0, 6.0
    prof = [(-depth, 0.0)] + [(0.6 + r * math.sin(a), r - r * math.cos(a))
                              for a in np.linspace(0, math.pi / 2, 24)] + [(0.6 + r, zmax)]
    for y, z in prof:
        verts += [(-w / 2, y, z), (w / 2, y, z)]
    for i in range(len(prof) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    me = bpy.data.meshes.new("backdrop")
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set("use_smooth", [True] * len(faces))
    me.materials.append(floor)
    ob = bpy.data.objects.new("backdrop", me)
    bpy.context.scene.collection.objects.link(ob)

    def area(name, loc, size, power, temp_rgb):
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape, ld.size, ld.energy, ld.color = "DISK", size, power, temp_rgb
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector((0, 0, 0.05)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.collection.objects.link(lo)
        return lo

    area("key", (-0.75, -0.55, 0.85), 0.55, 55, (1.0, 0.97, 0.93))
    area("fill", (0.9, -0.7, 0.25), 1.2, 12, (0.95, 0.97, 1.0))
    area("rim", (0.35, 0.75, 0.55), 0.5, 35, (1.0, 1.0, 1.0))

    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    if HDRI.exists():
        env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(HDRI))
        w.node_tree.links.new(env.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 0.09
    else:
        bg.inputs[0].default_value = (0.6, 0.6, 0.6, 1)
        bg.inputs[1].default_value = 0.3


def setup_render(preview):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    c = sc.cycles
    c.device = "CPU"
    c.samples = 32 if preview else 80
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.03 if preview else 0.02
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.max_bounces, c.glossy_bounces, c.transmission_bounces = 10, 4, 8
    c.caustics_reflective = c.caustics_refractive = False
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 12
    sc.render.resolution_x, sc.render.resolution_y = (1000, 667) if preview else (2000, 1334)
    sc.render.resolution_percentage = 100
    sc.render.use_persistent_data = True
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.view_settings.exposure = -0.85
    im = sc.render.image_settings
    im.file_format, im.quality, im.color_mode = "JPEG", 90, "RGB"


GROUP_TRAY = {"tray", "hub_ch334f", "vision_stack", "usb_plug_vision", "usb_plug_xiao", "audio_adapter",
              "usb_plug_hub", "usb_cable", "cable_tail", "cable_end"}
GROUP_PLATE = {"rear_plate", "cable_clamp", "capsule_clip", "plate_screws", "clamp_screws"}
GROUP_FRONT = {"finger_cradle", "camera_bezel", "camera_ov5647", "max30101", "speaker", "speaker_clamp",
               "mic_dongle", "mic_pigtail", "uv_led", "lens"}
GROUP_CAPSULE = {"sensor_capsule", "sht31"}
TRAY_OUT = 40.0
PARTING_GAP = 0.35


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    man = json.loads((MESH / "manifest.json").read_text())
    root = bpy.data.objects.new("pod", None)
    bpy.context.scene.collection.objects.link(root)
    groups = {}

    def grp(item, ob):
        groups.setdefault(item, []).append(ob)

    for m in man:
        d = np.load(MESH / f"{m['name']}.npz")
        grp(m["item"], add_mesh(m["name"], d["v"], d["f"], material_for(m["name"])))

    glass = plain_mat("lens_glass", (0.01, 0.01, 0.012), 0.02, bevel=0.05,
                      **{"Thin Film Thickness": 320.0, "Thin Film IOR": 1.38})
    cx, cz = 112.0, 86.0
    lens = prim("lens", glass, "uv_sphere", segments=48, ring_count=24, radius=5.0 * MM,
                location=(cx * MM, 2.6 * MM, cz * MM))
    lens.scale = (1, 0.18, 1)
    grp("lens", lens)

    rubber = plain_mat("rubber", (0.022, 0.022, 0.022), 0.85, bevel=0.3)
    for fx in (22.0, 128.0):
        for py in (23.0, 79.0):
            f = prim("foot_pad", rubber, "cylinder", vertices=64, radius=4.85 * MM, depth=2.0 * MM,
                     location=(fx * MM, py * MM, -8.0 * MM))
            bevel(f, 0.5 * MM, 3)
            shade_by_angle(f, 30)
            grp("feet", f)

    for x in (7.5, 142.5):
        for z in (7.5, 102.5):
            grp("plate_screws", screw("plate_screw", x, z, 94.0))
    for x in (21.2, 43.2):
        grp("clamp_screws", screw("clamp_screw", x, 30.0, 97.0))

    tail, end, dirn = cable_tail((32.2, 135.0, -6.0), [(32.2, 152.0, -7.0), (62.0, 190.0, -7.0),
                                                        (128.0, 214.0, -7.0), (196.0, 262.0, -7.0),
                                                        (270.0, 320.0, -7.0)])
    grp("cable_tail", tail)
    for ob in usb_c_end("cable_end", end, dirn):
        grp("cable_end", ob)
    end_objs = groups["cable_end"]
    end_objs[0].location.z = end_objs[1].location.z = -5.75 * MM

    # the air-sensor lead: soft pvc jacket sagging from the capsule into the floor grommet
    for ob in groups.pop("sensor_lead", []):
        bpy.data.objects.remove(ob)
    jacket_s = plain_mat("pvc_jacket_matte", (0.025, 0.025, 0.027), 0.58, bevel=0.0)
    for ob in lead("sht31_lead", [(67, 114.5, 7.5), (60, 115, 3), (54, 106, -4.5), (50.5, 93, -5.6),
                                  (50, 86.5, -4), (50, 84, -1.5), (50, 84, 3)], 1.75, jacket_s):
        grp("sensor_lead", ob)
    rubber_lip = plain_mat("rubber", (0.022, 0.022, 0.022), 0.85, bevel=0.3)
    lip = prim("grommet_lip", rubber_lip, "torus", major_radius=2.9 * MM, minor_radius=0.75 * MM,
               major_segments=48, minor_segments=16, location=(50 * MM, 84 * MM, -0.3 * MM))
    grp("sensor_lead", lip)

    # internal wiring, only seen in the open view; ends on the tray move with it
    ty = TRAY_OUT
    jacket = plain_mat("pvc_jacket", (0.02, 0.02, 0.022), 0.45, bevel=0.0)
    red = plain_mat("pvc_red", srgb((0.62, 0.06, 0.05)), 0.4, bevel=0.0)
    shrink = plain_mat("heatshrink", (0.015, 0.015, 0.016), 0.55, bevel=0.0)
    wiring = [
        lead("usb_lead_vision", [(71, 60, 21.8 ), (60, 58, 22), (48, 52, 20.5), (42.4, 50, 19.6)], 1.6, jacket),
        lead("usb_lead_xiao", [(80.7, 60, 31.5), (66, 62, 30), (50, 58, 24), (42.4, 56, 19.6)], 1.6, jacket, sag=1.5),
        lead("usb_lead_audio", [(36, 33, 19.6), (38, 30, 26), (44, 28, 29), (50, 26, 26.8)], 1.4, jacket),
    ]
    for obs in wiring:
        for ob in obs:
            ob.location.y = ty * MM
    hang = [lead("usb_lead_mic", [(60, 82.5, 103), (58, 90, 96), (52, 104, 70), (46, 94 + ty * 0.4, 40),
                                  (42.4, 44 + ty, 19.6)], 1.6, jacket, sag=4.0),
            lead("speaker_leads", [(40, 22.4, 60), (40, 32, 56), (34, 40 + ty * 0.5, 40),
                                   (28, 22 + ty, 30), (26, 18 + ty, 26.6)], 0.55, [red, jacket], sag=3.0,
                 twist=(1.15, 9.0))]
    sleeves = [lead(f"sleeve{i}", [(42.0, yy + ty, 19.6), (43.4, yy + ty, 19.6), (46, yy + ty, 19.7)], 2.0, shrink)
               for i, yy in enumerate((44, 50, 56))]
    for obs in wiring + hang + sleeves:
        for ob in obs:
            grp("open_wiring", ob)

    for obs in groups.values():
        for ob in obs:
            ob.parent = root
            ob.matrix_parent_inverse = Matrix.Translation(-PIVOT * MM)
    groups["coin"] = [coin("coin")]
    stage()
    return root, groups


def pose(groups, shot):
    for item, obs in groups.items():
        for ob in obs:
            ob.hide_render = False
            ob.delta_location = (0, 0, 0)
    for ob in groups["open_wiring"]:
        ob.hide_render = shot != "open"
    for ob in groups["coin"]:
        ob.hide_render = shot != "hero"
    if shot not in ("open", "exploded"):
        for item in GROUP_PLATE | GROUP_CAPSULE | {"plate_screws", "clamp_screws"}:
            for ob in groups.get(item, []):
                ob.delta_location = (0, PARTING_GAP * MM, 0)
    if shot == "open":
        for item in GROUP_PLATE | {"csi_ribbon", "plate_screws", "clamp_screws"}:
            for ob in groups.get(item, []):
                ob.hide_render = True
        for item in GROUP_TRAY:
            for ob in groups.get(item, []):
                ob.delta_location = (0, TRAY_OUT * MM, 0)
        for item in GROUP_CAPSULE:
            for ob in groups.get(item, []):
                ob.delta_location = (0, 0, -4 * MM)
    if shot == "underside":
        for item in {"cable_tail", "cable_end", "usb_cable"}:
            for ob in groups.get(item, []):
                ob.hide_render = True
    if shot == "exploded":
        for item in {"csi_ribbon", "sensor_lead", "cable_tail", "cable_end", "usb_cable"}:
            for ob in groups.get(item, []):
                ob.hide_render = True
        offs = [(GROUP_FRONT, (0, 105, 0)), (GROUP_TRAY, (0, 175, 0)), (GROUP_PLATE | GROUP_CAPSULE, (0, 290, 0)),
                ({"plate_screws", "clamp_screws"}, (0, 318, 0))]
        for items, off in offs:
            for item in items:
                for ob in groups.get(item, []):
                    ob.delta_location = Vector(off) * MM


# yaw of the pod, flip, camera elevation, distance, target (pod frame mm), focus (pod frame mm), lens
VIEWS = {
    "hero": dict(yaw=-38, flip=False, el=17, dist=0.92, tgt=(85, 85, 40), focus=(75, 0, 50), lens=80),
    "front": dict(yaw=-14, flip=False, el=9, dist=1.0, tgt=(78, 30, 52), focus=(75, 0, 55), lens=80),
    "top": dict(yaw=-18, flip=False, el=58, dist=0.84, tgt=(75, 46, 62), focus=(75, 30, 110), lens=85),
    "rear": dict(yaw=148, flip=False, el=16, dist=1.02, tgt=(75, 60, 50), focus=(75, 94, 50), lens=80),
    "underside": dict(yaw=62, roll=90, z=0.075, el=20, dist=0.98, tgt=(75, 50, 10), focus=(75, 46, -9),
                      lens=80),
    "open": dict(yaw=150, flip=False, el=30, dist=1.15, tgt=(75, 85, 40), focus=(75, 110, 30), lens=80),
    "exploded": dict(yaw=125, flip=False, el=24, dist=1.42, tgt=(75, 175, 45), focus=(75, 160, 50), lens=75),
}


def frame(root, shot):
    v = VIEWS[shot]
    root.rotation_euler = (0, math.radians(v.get("roll", 0)), math.radians(v["yaw"]))
    root.location = (0, 0, v.get("z", 0))
    bpy.context.view_layer.update()
    to_world = root.matrix_world @ Matrix.Translation(-PIVOT * MM)
    c = bpy.data.objects["coin"]
    c.location = to_world @ (Vector((34, -42, -9)) * MM)
    c.location.z = 0.875 * MM
    tgt = to_world @ (Vector(v["tgt"]) * MM)
    foc = to_world @ (Vector(v["focus"]) * MM)
    cam = bpy.data.objects.get("camera")
    if cam is None:
        cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
        bpy.context.scene.collection.objects.link(cam)
        bpy.context.scene.camera = cam
    el = math.radians(v["el"])
    cam.location = tgt + Vector((0, -math.cos(el), math.sin(el))) * v["dist"]
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    cd = cam.data
    cd.lens, cd.sensor_width, cd.sensor_fit = v["lens"], 36, "HORIZONTAL"
    cd.dof.use_dof = True
    cd.dof.focus_distance = (foc - cam.location).length
    cd.dof.aperture_fstop = 11.0 if shot != "exploded" else 16.0
    cd.clip_start = 0.01


def main():
    args = sys.argv[1:]
    preview = "--preview" in args
    shots = [a for a in args if a in SHOTS] or SHOTS
    root, groups = build()
    setup_render(preview)
    out = PREV if preview else FINAL
    out.mkdir(parents=True, exist_ok=True)
    for shot in shots:
        pose(groups, shot)
        frame(root, shot)
        bpy.context.scene.render.filepath = str(out / f"{shot}.jpg")
        bpy.ops.render.render(write_still=True)
        print("rendered", shot, flush=True)


if __name__ == "__main__":
    main()
