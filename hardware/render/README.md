# K-01 renders (Blender)

These scripts made the images in `hardware/out/renders/` and the `open.jpg` and `exploded.jpg` previews in `hardware/out/engineering_previews/`. They replace the simple boards from `hardware/cad/pod_k01.py` with the manufacturers' 3D models, which are not in this repo: `vendor/SOURCES.md` lists each file, where to download it and its licence.

- `export_meshes.py`: writes the CAD parts as meshes for Blender (run with the build123d Python).
- `render_k01.py`: lays out the scene and renders it (run with Blender's Python).
- `detail/`: the cables, plugs, fasteners and bought parts placed in the render. `detail/layout_dump.py` writes the CAD positions they are seated by.
- `vendor/`: converts and fixes the downloaded vendor models. `vendor/inspect_step.py` prints the solids in a STEP file, to check a download.

The renders are pictures of the design, not photographs of a built pod.
