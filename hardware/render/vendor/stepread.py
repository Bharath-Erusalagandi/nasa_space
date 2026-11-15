"""read a STEP assembly with names and colours (shape, face level) and tessellate it."""

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_ColorRGBA
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from OCP.XCAFDoc import XCAFDoc_ColorCurv, XCAFDoc_ColorGen, XCAFDoc_ColorSurf, XCAFDoc_ColorTool, XCAFDoc_DocumentTool


_KEEP = []


def _name(label):
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return TCollection_AsciiString(attr.Get()).ToCString()
    return ""


def _colour(ctool, obj):
    c = Quantity_ColorRGBA()
    get = XCAFDoc_ColorTool.GetColor_s if isinstance(obj, TDF_Label) else ctool.GetColor
    for kind in (XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv):
        try:
            found = get(obj, kind, c)
        except Exception:  # noqa: BLE001
            found = False
        if found:
            rgb = c.GetRGB()
            return (round(rgb.Red(), 3), round(rgb.Green(), 3), round(rgb.Blue(), 3))
    return None


def read(path):
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader()
    r.SetColorMode(True)
    r.SetNameMode(True)
    if r.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"cannot read {path}")
    r.Transfer(doc)
    stool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    ctool = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    leaves = []

    def walk(label, loc, path_names, inherited):
        name = _name(label)
        names = path_names + [name]
        col = _colour(ctool, label) or inherited
        if stool.IsReference_s(label):
            ref = TDF_Label()
            stool.GetReferredShape_s(label, ref)
            walk(ref, loc, path_names + [name] if name else path_names, col)
            return
        if stool.IsAssembly_s(label):
            kids = TDF_LabelSequence()
            stool.GetComponents_s(label, kids)
            for i in range(1, kids.Length() + 1):
                k = kids.Value(i)
                walk(k, loc.Multiplied(stool.GetLocation_s(k)), names, col)
            return
        shape = stool.GetShape_s(label)
        leaves.append({"names": [n for n in names if n], "shape": shape, "loc": loc, "colour": col})

    roots = TDF_LabelSequence()
    stool.GetFreeShapes(roots)
    for i in range(1, roots.Length() + 1):
        walk(roots.Value(i), TopLoc_Location(), [], None)
    _KEEP.append(doc)
    return leaves, ctool


def tessellate_face(face, tol):
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(face, loc)
    if tri is None:
        return None
    trsf = loc.Transformation()
    v = np.array([[p.X(), p.Y(), p.Z()] for p in
                  (tri.Node(i).Transformed(trsf) for i in range(1, tri.NbNodes() + 1))], dtype=np.float64)
    t = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)], dtype=np.int64) - 1
    if face.Orientation() == TopAbs_REVERSED:
        t = t[:, [0, 2, 1]]
    return v, t


def faces_of(leaf, ctool, tol=0.01, ang=0.15):
    """yield (face colour or None, verts in the assembly frame, triangles, face) for every face of a leaf."""
    shape = leaf["shape"]
    BRepMesh_IncrementalMesh(shape, tol, False, ang, True)
    trsf = leaf["loc"].Transformation()
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        f = TopoDS.Face(ex.Current())
        m = tessellate_face(f, tol)
        if m is not None and len(m[1]):
            v, t = m
            mat = np.array([[trsf.Value(i, j) for j in range(1, 5)] for i in range(1, 4)])
            v = v @ mat[:, :3].T + mat[:, 3]
            yield _colour(ctool, f), v, t, f
        ex.Next()
