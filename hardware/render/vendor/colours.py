"""colour table of a STEP: colour -> faces, area share, a few leaf names."""

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stepread import faces_of, read  # noqa: E402


def main(path):
    leaves, ctool = read(path)
    tab = defaultdict(lambda: [0, 0.0, set()])
    for lf in leaves:
        for col, v, t, f in faces_of(lf, ctool, tol=0.05, ang=0.5):
            c = col or lf["colour"]
            a = np.linalg.norm(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]), axis=1).sum() / 2
            e = tab[c]
            e[0] += 1
            e[1] += a
            if len(e[2]) < 4:
                e[2].add("/".join(lf["names"][-2:])[:40])
    print(len(leaves), "leaves")
    for c, (n, a, names) in sorted(tab.items(), key=lambda kv: -kv[1][1]):
        print(c, n, round(a, 1), sorted(names))


if __name__ == "__main__":
    main(sys.argv[1])
