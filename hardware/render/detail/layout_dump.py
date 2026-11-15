"""write build/detail/layout.json: the CAD parameters and derived poses the detail assets are seated by.

run with the build123d Python so the numbers come from hardware/cad/pod_k01.py itself.
"""

import json
import sys
from pathlib import Path

HW = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HW / "cad"))
import pod_k01 as cad  # noqa: E402


def main():
    P, DV = cad.P, cad.DV
    out = {
        "P": {k: v for k, v in vars(P).items()},
        "DV": {k: v for k, v in vars(DV).items()},
        "vision_box": cad.vision_box(), "vision_holes": cad.vision_holes(),
        "hub_box": cad.hub_box(), "hub_holes": cad.hub_holes(),
        "max_holes": cad.max_holes(), "adapter_box": cad.adapter_box(), "clip_screws": cad.clip_screws(),
    }
    dst = HW / "build" / "detail" / "layout.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1))
    print("wrote", dst)


if __name__ == "__main__":
    main()
