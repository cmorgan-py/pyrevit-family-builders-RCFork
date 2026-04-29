# -*- coding: utf-8 -*-
__title__ = 'Build\nDoor'
__doc__   = 'Builds a simple double-acting (swings both ways) door family from the active Door.rft template.'

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Arc, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector, View,
    Extrusion, SymbolicCurve, CurveElement,
    Material, BuiltInParameter
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a Door family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build simple door")
    t.Start()
    try:
        # ---- Purge previously-built geometry so reruns are idempotent ----
        old_ids = []
        for e in FilteredElementCollector(doc).OfClass(Extrusion):
            old_ids.append(e.Id)
        for e in FilteredElementCollector(doc).OfClass(CurveElement):
            if isinstance(e, SymbolicCurve):
                old_ids.append(e.Id)
        for eid in old_ids:
            try:
                doc.Delete(eid)
            except Exception:
                pass

        # ---- Ensure a current FamilyType exists ----
        ft = fm.CurrentType or fm.NewType("Standard")
        fm.CurrentType = ft

        # ---- Add custom parameters ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_th = add_param("Panel Thickness", SpecTypeId.Length, GroupTypeId.Geometry)
        p_fw = add_param("Frame Width",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_fd = add_param("Frame Depth",     SpecTypeId.Length, GroupTypeId.Geometry)
        fm.Set(p_th, 1.75 / 12.0)
        fm.Set(p_fw, 2.0  / 12.0)
        fm.Set(p_fd, 4.5  / 12.0)

        # ---- Read Width / Height from the current FamilyType ----
        # FamilyParameter has no AsDouble(); FamilyType.AsDouble(FamilyParameter) does.
        def read_len(param_name, default):
            p = fm.get_Parameter(param_name)
            if p is None:
                return default
            v = ft.AsDouble(p)
            return v if v is not None else default

        W = read_len("Width",  3.0)   # 3'-0"
        H = read_len("Height", 7.0)   # 7'-0"
        TH, FW, FD = 1.75/12.0, 2.0/12.0, 4.5/12.0

        # ---- Materials (find by name, or create if missing) ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_panel_id = find_or_create_material("Wood - Birch")
        mat_frame_id = find_or_create_material("Metal - Steel")

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- Vertical sketch plane (XZ, normal = +Y) ----
        plane = Plane.CreateByNormalAndOrigin(XYZ(0, 1, 0), XYZ(0, 0, 0))
        sk    = SketchPlane.Create(doc, plane)

        def rect(x1, z1, x2, z2):
            pts = [XYZ(x1, 0, z1), XYZ(x2, 0, z1),
                   XYZ(x2, 0, z2), XYZ(x1, 0, z2)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        # Panel
        prof = CurveArrArray()
        prof.Append(rect(-W/2 + FW, 0, W/2 - FW, H - FW))
        panel = fc.NewExtrusion(True, prof, sk, TH)
        ElementTransformUtils.MoveElement(doc, panel.Id, XYZ(0, -TH/2, 0))
        set_material(panel, mat_panel_id)

        # Frame: left jamb, right jamb, head
        def frame_piece(loop):
            pa = CurveArrArray(); pa.Append(loop)
            ext = fc.NewExtrusion(True, pa, sk, FD)
            ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, -FD/2, 0))
            set_material(ext, mat_frame_id)
            return ext

        frame_piece(rect(-W/2,      0,       -W/2 + FW, H))
        frame_piece(rect( W/2 - FW, 0,        W/2,      H))
        frame_piece(rect(-W/2,      H - FW,   W/2,      H))

        # ---- Plan swing arcs (symbolic) — double-acting (both directions) ----
        plans = [v for v in FilteredElementCollector(doc).OfClass(View)
                 if v.ViewType.ToString() == "FloorPlan" and not v.IsTemplate]
        if plans:
            plan_sk = SketchPlane.Create(
                doc, Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
            )
            hinge = XYZ(-W/2 + FW, 0, 0)
            leaf  = W - 2*FW

            arc_fwd  = Arc.Create(hinge, leaf, 0, 1.5708, XYZ(1, 0, 0), XYZ(0,  1, 0))
            open_fwd = Line.CreateBound(hinge, XYZ(-W/2 + FW,  leaf, 0))
            fc.NewSymbolicCurve(arc_fwd,  plan_sk)
            fc.NewSymbolicCurve(open_fwd, plan_sk)

            arc_back  = Arc.Create(hinge, leaf, 0, 1.5708, XYZ(1, 0, 0), XYZ(0, -1, 0))
            open_back = Line.CreateBound(hinge, XYZ(-W/2 + FW, -leaf, 0))
            fc.NewSymbolicCurve(arc_back,  plan_sk)
            fc.NewSymbolicCurve(open_back, plan_sk)

        t.Commit()
        print("Done. Now Align+lock edges to ref planes for full parametric flex.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))