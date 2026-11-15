"""copy Seeed's Grove Vision AI V2 layout with 3D model paths that resolve in the KiCad 10 library.

Seeed's file points at its own model folder, which is not published, and at KiCad 7 .wrl names.
Each swap below is a library model of the same package (or the closest one) and is listed in SOURCES.md.
usage: python3 -I fix_vision_pcb.py <in.kicad_pcb> <out.kicad_pcb>
"""

import re
import sys

LIB = "${KICAD7_3DMODEL_DIR}"
SUB = "${SUBST}"

SWAP = {
    "USBC2.0-C2765186.step": None,
    "SPK0641HT4H-1-7.stp": f"{LIB}/Sensor_Audio.3dshapes/Knowles_SPH0645LM4H-6_3.5x2.65mm.step",
    "4.2x3.2mmButton_KLS7-TS3401.step": f"{LIB}/Button_Switch_SMD.3dshapes/SW_SPST_PTS810.step",
    "X2SON.step": f"{LIB}/Package_SON.3dshapes/X2SON-8_1.4x1mm_P0.35mm.step",
    "SOIC-8_5.275x5.275mm_P1.27mm.wrl": f"{LIB}/Package_SO.3dshapes/SOIC-8_5.3x5.3mm_P1.27mm.step",
    "WQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm.wrl": f"{LIB}/Package_DFN_QFN.3dshapes/WQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm.step",
    "Grove Connector (flat).STEP": (f"{LIB}/Connector_JST.3dshapes/JST_PH_S4B-PH-K_1x04_P2.00mm_Horizontal.step",
                                    "-3 1.524 0", "0 0 0"),
    "Seeeduino XIAO SAMD21 v4.step": None,
    "Pin_D1.0mm_L10.0mm.wrl": None,
}
SHOW = {"XIAO-nRF52840 v15.step", "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.wrl"}
ADD = {
    "Ic:DFN6-0.5-1.5X1.5X0.65MM": f"{LIB}/Package_SON.3dshapes/WSON-6_1.5x1.5mm_P0.5mm.step",
    "Connector:SD-TF-MR267": f"{SUB}/microsd_short_mr267.step",
}
MODEL = re.compile(r'\(model "([^"]+)"(.*?)\n    \)\n', re.S)


def fix_model(m):
    path, body = m.group(1), m.group(2)
    base = path.split("/")[-1]
    if base in SWAP:
        if SWAP[base] is None:
            return ""
        path, off, rot = SWAP[base] if isinstance(SWAP[base], tuple) else (SWAP[base], "0 0 0", None)
        body = re.sub(r"\(offset \(xyz [^)]*\)\)", f"(offset (xyz {off}))", body)
        if rot:
            body = re.sub(r"\(rotate \(xyz [^)]*\)\)", f"(rotate (xyz {rot}))", body)
    elif path.endswith(".wrl"):
        path = path[:-4] + ".step"
    path = path.replace("$KICAD7_3DMODEL_DIR/", f"{LIB}/")
    if base in SHOW:
        body = re.sub(r"^\s*\(hide yes\)", "", body, flags=re.M)
        if body.startswith(" hide"):
            body = body[5:]
    return f'(model "{path}"{body}\n    )\n'


def main(src, dst):
    s = open(src, encoding="utf-8").read()
    s = MODEL.sub(fix_model, s)
    for fp, model in ADD.items():
        start = s.index(f'(footprint "{fp}"')
        while True:
            end = s.index("\n  )\n", start)
            s = s[:end] + f'\n    (model "{model}"\n      (offset (xyz 0 0 0))\n      (scale (xyz 1 1 1))\n' \
                f'      (rotate (xyz 0 0 0))\n    )' + s[end:]
            nxt = s.find(f'(footprint "{fp}"', end)
            if nxt < 0:
                break
            start = nxt
    open(dst, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
