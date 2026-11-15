#!/bin/sh
# export the board STEP files from the vendor layouts with KiCad 10 (docker), run from hardware/build/vendor
set -e
V=../../render/vendor
python -I $V/make_subst.py subst
python3 -I $V/fix_vision_pcb.py "vision/Grove - Vision AI Module V2.kicad_pcb" kicad_out/vision_fixed.kicad_pcb
python3 -I $V/eagle_fix.py kicad_out/SparkFun_MAX30101_Qwiic.kicad_pcb kicad_out/max30101_fixed.kicad_pcb max30101
python3 -I $V/eagle_fix.py kicad_out/hub4.kicad_pcb kicad_out/hub4_fixed.kicad_pcb
python3 -I $V/eagle_fix.py kicad_out/sht31qt.kicad_pcb kicad_out/sht31qt_fixed.kicad_pcb
sudo docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/w" kicad/kicad:10.0.8-full sh -c '
L="--include-tracks --include-pads --include-silkscreen --include-soldermask -f"
D="-D KICAD7_3DMODEL_DIR=/usr/share/kicad/3dmodels -D AMZPATH=/w/amz -D SUBST=/w/subst"
kicad-cli pcb export step $L $D -o /w/kicad_out/vision_ai_v2.step /w/kicad_out/vision_fixed.kicad_pcb 2>&1 | grep -i "not found\|created"
kicad-cli pcb export step $L $D -o /w/kicad_out/max30101.step /w/kicad_out/max30101_fixed.kicad_pcb 2>&1 | grep -i "not found\|created"
kicad-cli pcb export step $L --no-components -o /w/kicad_out/hub4.step /w/kicad_out/hub4_fixed.kicad_pcb 2>&1 | grep -i "created"
kicad-cli pcb export step $L --no-components -o /w/kicad_out/sht31qt.step /w/kicad_out/sht31qt_fixed.kicad_pcb 2>&1 | grep -i "created"
'
