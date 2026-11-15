"""Preview renders of pod K-01. Run with Blender's Python (bpy) after pod_k01.py --render-meshes."""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HW = Path(__file__).resolve().parent.parent
MESH = HW / "build" / "render"
OUT = HW / "out" / "engineering_previews"
CENTER = Vector((75, 46, 50))


MATS = {}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MATS.clear()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.threads_mode = "FIXED"
    sc.render.threads = 6
    sc.render.resolution_x, sc.render.resolution_y = 1200, 800
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 85
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.93, 0.93, 0.92, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    return sc


def material(rgb, kind):
    key = (tuple(round(c, 3) for c in rgb), kind)
    if key in MATS:
        return MATS[key]
    m = bpy.data.materials.new(f"m{len(MATS)}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    lin = [c ** 2.2 for c in rgb]
    b.inputs["Base Color"].default_value = (*lin, 1)
    metal = rgb[0] > 0.6 and abs(rgb[0] - rgb[2]) < 0.05 and kind == "bought" and rgb[0] < 0.8
    b.inputs["Metallic"].default_value = 0.8 if metal else 0.0
    b.inputs["Roughness"].default_value = 0.35 if metal else (0.55 if kind != "bought" else 0.45)
    MATS[key] = m
    return m


def load(path, rgb, kind, offset=(0, 0, 0)):
    bpy.ops.wm.stl_import(filepath=str(path))
    ob = bpy.context.selected_objects[0]
    ob.location = offset
    ob.data.materials.append(material(rgb, kind))
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def lights(sc, target):
    for name, loc, energy, size in (("key", (-180, -260, 260), 9e5, 120), ("fill", (260, -120, 120), 3e5, 160),
                                    ("rim", (60, 300, 200), 3e5, 120)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = energy, size
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        sc.collection.objects.link(lo)
        lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def ground(sc, z):
    bpy.ops.mesh.primitive_plane_add(size=2000, location=(75, 46, z))
    g = bpy.context.active_object
    g.data.materials.append(material((0.95, 0.95, 0.94), "ground"))


def camera(sc, loc, target, lens=50, ortho=None):
    cd = bpy.data.cameras.new("cam")
    cd.lens = lens
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    co = bpy.data.objects.new("cam", cd)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(co)
    sc.camera = co


def shoot(sc, name):
    OUT.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(OUT / f"{name}.jpg")
    bpy.ops.render.render(write_still=True)
    print("wrote", sc.render.filepath)


def scene_assembly(man, name, cam_loc, hide=(), section=False, lens=50, target=None):
    sc = reset()
    for e in man:
        if e["kind"] == "print" or e["item"] in hide:
            continue
        f = e.get("section") if section else e["file"]
        if not f:
            continue
        load(MESH / f, e["rgb"], e["kind"])
    ground(sc, -8.0)
    lights(sc, CENTER)
    camera(sc, cam_loc, target or CENTER, lens)
    shoot(sc, name)


def scene_print(man):
    sc = reset()
    prints = [e for e in man if e["kind"] == "print"]
    x = 0.0
    row_y = 0.0
    row_h = 0.0
    for e in sorted(prints, key=lambda e: -e["size"][0] * e["size"][1]):
        w, d = e["size"][0], e["size"][1]
        if x + w > 300:
            x, row_y, row_h = 0.0, row_y + row_h + 15, 0.0
        load(MESH / e["file"], e["rgb"], "printed", (x + w / 2, row_y + d / 2, 0))
        x += w + 15
        row_h = max(row_h, d)
    ground(sc, 0.0)
    span = max(x, 300)
    c = Vector((span / 2, (row_y + row_h) / 2, 0))
    lights(sc, c)
    camera(sc, c + Vector((0, -0.45, 1.0)) * (row_y + row_h + span) * 0.8, c, 35)
    shoot(sc, "print_parts")


def main():
    man = json.loads((MESH / "manifest.json").read_text())
    which = sys.argv[1:] or ["front", "rear", "section", "tunnel", "interior", "print"]
    if "front" in which:
        scene_assembly(man, "assembly_front", (-110, -300, 170))
    if "rear" in which:
        scene_assembly(man, "assembly_rear", (280, 360, 170))
    if "section" in which:
        scene_assembly(man, "section_tunnel_camera", (420, 30, 60), section=True, lens=45)
    if "tunnel" in which:
        scene_assembly(man, "section_tunnel_detail", (260, 16, 34), section=True, lens=75, target=(108, 16, 30))
    if "interior" in which:
        scene_assembly(man, "interior", (-120, 260, 300), hide=("shell", "rear_plate", "cable_clamp", "capsule_clip",
                                                                 "sensor_capsule"))
    if "print" in which:
        scene_print(man)


main()
