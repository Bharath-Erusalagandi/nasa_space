# Vendor 3D models for the K-01 renders

Downloads stay out of the repo, in `hardware/build/vendor/`. Converted assets, `manifest.json`,
`differences.json` and `missing.json` are in `hardware/build/detail/`. None of them are
added to the repo. `hardware/cad/pod_k01.py` is unchanged; its simple models stay in the STEP assembly.
All files were fetched on 2026-11-14.

## Sources

| Part | File | URL | Licence or terms at the source |
|---|---|---|---|
| XIAO nRF52840 Sense | `seeed-studio-xiao-nrf52840-3d-model.zip` (`XIAO-nRF52840 v15.step`, includes the MSM261 PDM mic, so the Sense board) | https://files.seeedstudio.com/wiki/XIAO-BLE/seeed-studio-xiao-nrf52840-3d-model.zip, linked from https://wiki.seeedstudio.com/XIAO_BLE/ | Seeed wiki licence page: product documents CC BY-SA 4.0; third-party content stays with its owners (https://wiki.seeedstudio.com/License/) |
| Grove Vision AI V2 | `Grove_Vision_AI_Module_V2_Layout.zip` (KiCad 7 board and schematic) | https://files.seeedstudio.com/wiki/grove-vision-ai-v2/Grove_Vision_AI_Module_V2_Layout.zip, linked from https://wiki.seeedstudio.com/grove_vision_ai_v2/ | as above, CC BY-SA 4.0 |
| Grove Vision AI V2 kit case | `grove_vision_ai_v2_kit_case.stp` | https://files.seeedstudio.com/wiki/grove-vision-ai-v2/grove_vision_ai_v2_kit_case.stp | as above. Inspected: four solids, case only, no board or camera. Not used |
| CH334F hub, Adafruit 5997 | `5997-CH334F-4-Port-Hub.step` | https://github.com/adafruit/Adafruit_CAD_Parts/tree/main/5997%20CH334F%204-Port%20Hub (commit 9f2a89f) | MIT (repository LICENSE) |
| CH334F hub board | `Adafruit CH334F Mini 4-Port USB Hub Breakout.brd` (Eagle) | https://github.com/adafruit/Adafruit-CH334F-Breakout-PCB (commit a29ea77) | CC BY-SA 3.0 (repository license.txt) |
| SHT31-D, Adafruit 2857 | `2857 SHT31-D.step` (STEMMA QT layout) | https://github.com/adafruit/Adafruit_CAD_Parts/tree/main/2857%20SHT31-D | MIT |
| SHT31-D board | `Adafruit SHT31-D STEMMA QT Breakout.brd` (Eagle) | https://github.com/adafruit/Adafruit-SHT31-Sensor-Breakout-PCB (commit 00cb07a) | CC BY-SA 3.0 |
| Speaker 40 mm, Adafruit 3968 | `3968 Speaker 40mm.step` | https://github.com/adafruit/Adafruit_CAD_Parts/tree/main/3968%20Speaker%2040mm | MIT |
| USB-C cable, Adafruit 4056 | `4056-USB-C-to-micro-B.step` | https://github.com/adafruit/Adafruit_CAD_Parts/tree/main/4056%20USBC-to-microB-cable | MIT. Inspected: one 40 face solid with no plug detail. Not used |
| MAX30101 Qwiic, SparkFun SEN-16474 | `Hardware/SparkFun_MAX30101_Qwiic.brd` (Eagle). SparkFun publishes board design files only, no 3D model | https://github.com/sparkfun/SparkFun_Photodetector_Breakout_MAX30101_Qwiic (commit 854e0ef) | CC BY-SA 4.0 for hardware (repository LICENSE.md) |
| Raspberry Pi Camera Module 3 | `camera-module-3-step.zip` | https://datasheets.raspberrypi.com/camera/camera-module-3-step.zip | no licence stated in the zip. Downloaded as a reference for the 25 x 24 board family; not used, it is a different camera (IMX708, larger lens) |
| Footprint models | KiCad 10.0.8 library, docker image `kicad/kicad:10.0.8-full` | https://hub.docker.com/r/kicad/kicad, library at https://gitlab.com/kicad/libraries/kicad-packages3D | CC BY-SA 4.0 with the KiCad library exception |

Not found or not usable:

- Mini USB microphone, Adafruit 3367: no folder in Adafruit_CAD_Parts (485 folders listed through the GitHub API) and no file on the product page.
- OV5647 camera (Seeed 114110127, OV5647-62): the Seeed page lists no drawing or 3D file. Arducam's pages block automated access and cover other modules. Raspberry Pi publishes no STEP for the v1.3 board.
- Overmoulded USB-C and USB-A cable plugs: no maker-published cable plug model was reachable without an account. The Molex part page did not answer requests from the box, and the KiCad library has only board-mount plugs. The Adafruit 4056 cable model is a plain block.
- Audio adapter, 5 mm UV LED, ribbon, cables: no specific product is named in the CAD, so there is no vendor file to fetch.

No source used here forbids rendering. CC BY-SA files need attribution if renders or derived models are published; the attribution lines are the rows above.

## How the boards are built

`kicad_boards.sh` runs KiCad 10 in docker and exports STEP with copper, pads, solder mask and silkscreen, so the boards carry their real artwork, not a plain slab.

- Grove Vision AI V2: Seeed's own layout. `fix_vision_pcb.py` repoints its model paths to the KiCad 10 library and swaps the models Seeed did not publish: USB-C receptacle C2765186 to GCT USB4105 (Seeed's own alternate), PDM mic SPK0641HT4H to Knowles SPH0645LM4H (same 3.5 x 2.65 package), KLS7-TS3401 4.2 x 3.2 buttons to C&K PTS810 (same size), X2SON-4 to X2SON-8 1.4 x 1, SOIC-8 5.275 to SOIC-8 5.3, Grove 2.0 mm right angle socket to JST PH S4B-PH-K, DFN6 1.5 x 1.5 (no model) to WSON-6 1.5 x 1.5, SD-TF-MR267 socket (no model) to a stand-in from `make_subst.py` built on Seeed's footprint outline. The XIAO nRF52840 is Seeed's STEP, seated by Seeed's footprint (the file had the SAMD21 XIAO switched on).
- CH334F hub and SHT31-D: board from Adafruit's Eagle file through KiCad (mask, silk, pads), components from Adafruit's STEP aligned on the same outline.
- MAX30101: SparkFun's Eagle board through KiCad, and `eagle_fix.py` gives each Eagle package the KiCad library model of the same package (SOT-416 uses SOT-323 scaled to 1.6 x 0.8, the library has no SOT-416). The MAX30101 OESIP has no library model; `make_subst.py` builds it at the datasheet outline 5.6 x 3.3 x 1.55 with cover glass; its window sizes are read off photos.
- Speaker: Adafruit's STEP is one uncoloured solid; `convert.py` names its faces by position (dust cap, surround, gasket ring, voice coil seen through the basket windows, steel frame and magnet).

## Assets in hardware/build/detail

Each asset is `<name>.blend` (one object, Z up, millimetres, scene unit scale 0.001), plus `<name>.npz` (verts in mm, triangles, per triangle material index) and `<name>.json` (materials, frame, board box, board holes).

| Asset | Used for (assemble name) | Origin and axes |
|---|---|---|
| `vision_stack` | `vision_stack` | board centre, z = 0 on the board face toward the tray; +z is the XIAO side (KiCad B.Cu); the board USB-C and the CSI socket are on the -z face; x along the 40 mm edge, USB-C ends at -x |
| `xiao_nrf52840_sense` | spare, the XIAO alone | board centre, z = 0 on the board bottom, parts +z, USB-C at +x |
| `hub_ch334f` | `hub_ch334f` | board centre, z = 0 board bottom, parts +z, upstream USB-C at +y |
| `sht31` | `sht31` | board centre, z = 0 board bottom, parts +z, 25.4 mm edge along x |
| `max30101` | `max30101` | board centre, z = 0 board bottom, sensor and Qwiic sockets +z, sensor toward +y, header pads toward -y |
| `speaker` | `speaker` | cone axis, z = 0 on the front face of the rim, magnet toward -z |

Material names (the scene maps them to real shaders): `solder_mask_<colour>` (blue Vision AI, black XIAO and Adafruit, red SparkFun), `copper_under_mask_<colour>` (tracks and vias under the mask), `fr4_edge`, `enig`, `tin`, `silkscreen`, `epoxy_black`, `mlcc_ceramic`, `resistor_top`, `steel`, `plastic_black`, `plastic_white`, `plastic_beige`, `led_lens`, `led_die`, `silicon`, `glass`, `copper`, `rubber_black`, `cone_paper`, `label_white`, `sensor_dfn`.

## Seating and differences

`seat.py` imports `pod_k01.py` (read only), writes `manifest.json` with a 4 x 4 row major matrix per part that maps asset millimetres into the assembly frame, `placeholders.npz` for overlay checks, and `differences.json` with every difference over 0.5 mm. Boards with four holes are seated hole pattern on hole pattern; the Vision AI V2 on its outline (its layout has no drilled holes); the speaker on its rim front face and axis.

## Commands

```
cd hardware/build/vendor && sh ../../render/vendor/kicad_boards.sh
cd hardware && python -I render/vendor/convert.py
python -I render/vendor/blendtools.py build vision_stack xiao_nrf52840_sense hub_ch334f sht31 max30101 speaker
python -I render/vendor/seat.py
python -I render/vendor/blendtools.py overlay <out.jpg> <part> [iso|low|top]
```
