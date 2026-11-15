"""clean a KiCad board imported from Eagle and give SparkFun's footprints KiCad library 3D models.

Eagle libraries carry no 3D models. For the MAX30101 board each package gets the KiCad library model
of the same package; the sensor itself (no library model) gets the stand-in from make_subst.py.
usage: python3 -I eagle_fix.py <in.kicad_pcb> <out.kicad_pcb> [max30101]
"""

import re
import sys

LIB = "${KICAD10_3DMODEL_DIR}"

# (footprint, reference prefix) -> (model, offset xyz, rotate z)
MAX30101 = {
    ("0603", "R"): ("Resistor_SMD.3dshapes/R_0603_1608Metric.step", (0, 0, 0), 0),
    ("0603", "C"): ("Capacitor_SMD.3dshapes/C_0603_1608Metric.step", (0, 0, 0), 0),
    ("0402", "C"): ("Capacitor_SMD.3dshapes/C_0402_1005Metric.step", (0, 0, 0), 0),
    ("0805", "C"): ("Capacitor_SMD.3dshapes/C_0805_2012Metric.step", (0, 0, 0), 0),
    ("0806", "L"): ("Inductor_SMD.3dshapes/L_0805_2012Metric.step", (0, 0, 0), 0),
    ("LED-0603", "D"): ("LED_SMD.3dshapes/LED_0603_1608Metric.step", (0, 0, 0), 0),
    # no SOT-416 model in the library: SOT-323 scaled to the 1.6 x 0.8 body
    ("SOT-416FL", "Q"): ("Package_TO_SOT_SMD.3dshapes/SOT-323_SC-70.step", (0, 0, 0), 0, (0.8, 0.75, 0.85)),
    ("MSOP8", "U"): ("Package_SO.3dshapes/MSOP-8_3x3mm_P0.65mm.step", (0, 0, 0), 0),
    ("SC70", "U"): ("Package_TO_SOT_SMD.3dshapes/SOT-353_SC-70-5.step", (0, 0, 0), 0),
    ("JST04_1MM_RA", "J"): ("Connector_JST.3dshapes/JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal.step",
                            (0, 0, 0), 0),
    ("14_PIN_OESIP", "U"): ("${SUBST}/max30101_oesip.step", (0, 0, 0), 90),
}
OVERRIDE = {}


def model_block(path, off, rot, scale=(1, 1, 1)):
    full = path if path.startswith("$") else f"{LIB}/{path}"
    return (f'\t\t(model "{full}"\n\t\t\t(offset\n\t\t\t\t(xyz {off[0]} {off[1]} {off[2]})\n\t\t\t)\n'
            f'\t\t\t(scale\n\t\t\t\t(xyz {scale[0]} {scale[1]} {scale[2]})\n\t\t\t)\n\t\t\t(rotate\n\t\t\t\t(xyz 0 0 {rot})\n\t\t\t)\n\t\t)\n')


def add_models(s, table):
    parts = re.split(r"(\n\t\(footprint )", s)
    out = [parts[0]]
    for sep, blk in zip(parts[1::2], parts[2::2]):
        name = blk.split("\n")[0].split('"')[1]
        ref = re.search(r'\(property "Reference" "([^"]*)"', blk)
        ref = ref.group(1) if ref else ""
        key = (name, re.sub(r"\d+$", "", ref))
        spec = OVERRIDE.get(ref) or table.get(key)
        if spec:
            end = blk.rindex("\n\t)")
            blk = blk[:end] + "\n" + model_block(*spec).rstrip("\n") + blk[end:]
        out += [sep, blk]
    return "".join(out)


def main(src, dst, which=None):
    s = open(src, encoding="utf-8").read()
    s = s.replace('(layer "UNDEFINED")', '(layer "User.9")')
    if which == "max30101":
        s = add_models(s, MAX30101)
    open(dst, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    main(*sys.argv[1:])
