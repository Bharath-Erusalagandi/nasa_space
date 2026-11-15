"""Write one mesh per part of the K-01 assembly for the photoreal renders.

Run: python hardware/render/export_meshes.py
Writes hardware/build/meshes/<name>.npz (verts in mm, triangle indices) and manifest.json.
"""

import json
import sys
from pathlib import Path

import numpy as np

HW = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HW / "cad"))
import pod_k01 as cad  # noqa: E402

OUT = HW / "build" / "meshes"
TOL, ANG = 0.02, 0.12


def mesh_of(shape):
    verts, faces = [], []
    base = 0
    # tessellate face by face so b-rep edges stay sharp and curved faces stay smooth
    for f in shape.faces():
        v, t = f.tessellate(TOL, ANG)
        if not t:
            continue
        verts += [(p.X, p.Y, p.Z) for p in v]
        faces += [(a + base, b + base, c + base) for a, b, c in t]
        base += len(v)
    return np.array(verts, dtype=np.float32), np.array(faces, dtype=np.int32)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    items, _ = cad.assemble()
    manifest = []
    for it in items:
        subs = [(it.name, it.shape)] if it.kind == "printed" else [(c.label, c) for c in it.children]
        for name, shp in subs:
            v, f = mesh_of(shp)
            np.savez_compressed(OUT / f"{name}.npz", v=v, f=f)
            manifest.append({"name": name, "item": it.name, "kind": it.kind, "tris": int(len(f))})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"{len(manifest)} meshes, {sum(m['tris'] for m in manifest)} triangles")


if __name__ == "__main__":
    main()
