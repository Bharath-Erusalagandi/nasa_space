"""print the solids of a STEP file: label, colour, bounding box."""

import sys

from build123d import import_step


def walk(node, depth=0, out=None):
    out = [] if out is None else out
    kids = list(node.children) if hasattr(node, "children") else []
    b = node.bounding_box()
    col = getattr(node, "color", None)
    out.append((depth, node.label, type(node).__name__, col, b, len(kids)))
    for k in kids:
        walk(k, depth + 1, out)
    return out


def main(path, maxdepth):
    shp = import_step(path)
    for depth, label, kind, col, b, n in walk(shp):
        if depth > maxdepth:
            continue
        c = "" if col is None else "rgb(%.2f %.2f %.2f)" % tuple(tuple(col)[:3])
        print(f"{'  ' * depth}{label or '-'} [{kind} {n}] {c} min({b.min.X:.2f},{b.min.Y:.2f},{b.min.Z:.2f}) "
              f"size({b.size.X:.2f},{b.size.Y:.2f},{b.size.Z:.2f})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
