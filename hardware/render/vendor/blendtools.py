"""build the .blend assets from the converted meshes and render quick previews.

python -I hardware/render/vendor/blendtools.py build <asset> ...
python -I hardware/render/vendor/blendtools.py preview <out.jpg> <asset> [view]
python -I hardware/render/vendor/blendtools.py overlay <out.jpg> <part> ...
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HW = Path(__file__).resolve().parent.parent.parent
DET = HW / "build" / "detail"

MASK = {"blue": (0.03, 0.2, 0.65), "black": (0.012, 0.012, 0.014), "red": (0.45, 0.02, 0.02),
        "green": (0.02, 0.18, 0.05)}
# preview stand-ins only; the render scene assigns its own shaders by material name
LOOK = {
    "fr4_edge": ((0.55, 0.5, 0.33), 0.0, 0.6), "enig": ((0.9, 0.7, 0.35), 1.0, 0.25),
    "tin": ((0.8, 0.8, 0.8), 1.0, 0.3), "silkscreen": ((0.92, 0.92, 0.9), 0.0, 0.6),
    "epoxy_black": ((0.025, 0.025, 0.025), 0.0, 0.45), "mlcc_ceramic": ((0.35, 0.25, 0.15), 0.0, 0.5),
    "resistor_top": ((0.02, 0.02, 0.02), 0.0, 0.5), "steel": ((0.75, 0.75, 0.76), 1.0, 0.22),
    "steel_dark": ((0.35, 0.35, 0.36), 1.0, 0.35), "plastic_black": ((0.03, 0.03, 0.03), 0.0, 0.5),
    "plastic_white": ((0.85, 0.84, 0.8), 0.0, 0.5), "plastic_beige": ((0.75, 0.68, 0.52), 0.0, 0.5),
    "led_lens": ((0.85, 0.9, 0.85), 0.0, 0.1), "silicon": ((0.05, 0.05, 0.07), 0.3, 0.15),
    "glass": ((0.9, 0.9, 0.9), 0.0, 0.05), "copper": ((0.85, 0.45, 0.25), 1.0, 0.3),
    "rubber_black": ((0.02, 0.02, 0.02), 0.0, 0.7), "cone_paper": ((0.03, 0.03, 0.03), 0.0, 0.8),
    "label_white": ((0.85, 0.85, 0.83), 0.0, 0.5), "sensor_dfn": ((0.6, 0.6, 0.58), 0.0, 0.4),
    "led_die": ((0.55, 0.5, 0.42), 0.6, 0.3),
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material(name, mask):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    if name.startswith(("solder_mask", "copper_under_mask")):
        base = MASK.get(name.rsplit("_", 1)[1], MASK["green"])
        col, met, rough = (tuple(min(1, x * (1.6 if name.startswith("copper") else 1)) for x in base), 0.0, 0.3)
    else:
        col, met, rough = LOOK.get(name, ((0.5, 0.5, 0.5), 0.0, 0.5))
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Metallic"].default_value = met
    b.inputs["Roughness"].default_value = rough
    if name in ("led_lens", "glass"):
        b.inputs["Transmission Weight"].default_value = 0.8
    return m


def load_asset(name, link=True):
    meta = json.loads((DET / f"{name}.json").read_text())
    d = np.load(DET / f"{name}.npz")
    v, t, mi = d["verts"], d["tris"], d["mat"]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.ravel())
    me.loops.add(len(t) * 3)
    me.loops.foreach_set("vertex_index", t.ravel())
    me.polygons.add(len(t))
    me.polygons.foreach_set("loop_start", np.arange(0, len(t) * 3, 3))
    me.polygons.foreach_set("material_index", mi.astype(np.int32))
    me.update(calc_edges=True)
    me.validate()
    for n in meta["materials"]:
        me.materials.append(material(n, meta.get("mask_colour")))
    # vertices are not shared across b-rep faces, so smooth shading keeps every crease sharp
    me.polygons.foreach_set("use_smooth", np.ones(len(t), dtype=bool))
    ob = bpy.data.objects.new(name, me)
    ob["source"] = meta["source"]
    ob["frame"] = meta["frame"]
    ob["units"] = "mm"
    if link:
        bpy.context.scene.collection.objects.link(ob)
    return ob


def build(names):
    for n in names:
        reset()
        load_asset(n)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 0.001
        bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
        out = DET / f"{n}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
        print("wrote", out)


def setup_render(out, res=(1200, 900), samples=48):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 6
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 85
    sc.render.filepath = str(out)
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.6, 0.62, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    sc.world = w
    for loc, energy, size in (((-120, -160, 220), 2.2e6, 120), ((180, -60, 120), 8e5, 80), ((0, 200, 150), 5e5, 100)):
        L = bpy.data.lights.new("l", "AREA")
        L.energy, L.size = energy, size
        o = bpy.data.objects.new("l", L)
        o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(o)


def frame_camera(objs, direction=(-0.55, -1.0, 0.85), lens=60, margin=1.15, target=None):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2 if target is None else Vector(target)
    r = (hi - lo).length / 2 * margin
    cam = bpy.data.cameras.new("c")
    cam.lens = lens
    cam.clip_start, cam.clip_end = 0.5, 5000
    o = bpy.data.objects.new("c", cam)
    d = Vector(direction).normalized()
    dist = r / math.tan(math.atan(18 / lens)) * 1.05
    o.location = c + d * dist
    o.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(o)
    bpy.context.scene.camera = o


def ground(z):
    me = bpy.data.meshes.new("g")
    s = 2000
    me.from_pydata([(-s, -s, z), (s, -s, z), (s, s, z), (-s, s, z)], [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new("g", me)
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.36, 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    me.materials.append(m)
    bpy.context.scene.collection.objects.link(o)


VIEWS = {"iso": (-0.55, -1.0, 0.85), "top": (0.0, -0.05, 1.0), "bottom": (0.0, -0.05, -1.0),
         "front": (0.0, -1.0, 0.15), "iso_back": (0.6, 1.0, 0.8), "low": (-0.8, -1.0, 0.35)}


def preview(out, names, view="iso"):
    reset()
    obs = []
    x = 0.0
    for n in names:
        o = load_asset(n)
        w = o.dimensions.x
        o.location.x = x + w / 2 - (sum(Vector(c).x for c in o.bound_box) / 8)
        x += w + 6
        obs.append(o)
    bpy.context.view_layer.update()
    zmin = min((o.matrix_world @ Vector(c)).z for o in obs for c in o.bound_box)
    if view not in ("bottom",):
        ground(zmin - 0.01)
    setup_render(out)
    frame_camera(obs, VIEWS[view])
    bpy.ops.render.render(write_still=True)


def overlay(out, parts, view="iso"):
    """real model posed by the manifest (rendered) against the placeholder (red wire)."""
    reset()
    man = json.loads((DET / "manifest.json").read_text())
    ph = np.load(DET / "placeholders.npz")
    obs = []
    red = bpy.data.materials.new("ph")
    red.use_nodes = True
    nt = red.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 0.05, 0.02, 1)
    em.inputs["Strength"].default_value = 4
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs[0])
    for p in parts:
        e = man["parts"][p]
        for k, a in enumerate(e["assets"]):
            o = load_asset(a["asset"])
            o.name = f"{p}_{k}"
            o.matrix_world = Matrix(a["matrix"])
            obs.append(o)
        segs = ph[f"{p}_e"]
        cu = bpy.data.curves.new(p + "_ph", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.07
        for a, b in segs:
            sp = cu.splines.new("POLY")
            sp.points.add(1)
            sp.points[0].co = (*a, 1)
            sp.points[1].co = (*b, 1)
        cu.materials.append(red)
        o = bpy.data.objects.new(p + "_ph", cu)
        bpy.context.scene.collection.objects.link(o)
    setup_render(out, samples=32)
    frame_camera(obs, VIEWS[view], lens=60, margin=1.25)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "build":
        build(args)
    elif cmd == "preview":
        preview(args[0], [a for a in args[1:] if a not in VIEWS], next((a for a in args[1:] if a in VIEWS), "iso"))
    elif cmd == "overlay":
        overlay(args[0], [a for a in args[1:] if a not in VIEWS], next((a for a in args[1:] if a in VIEWS), "iso"))
