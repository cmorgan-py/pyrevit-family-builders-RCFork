# -*- coding: utf-8 -*-
__title__ = 'Build\nShiny\nTrashcan'
__doc__   = 'Builds a tall polished-brass cylindrical trashcan with a rounded-rectangle mail-slot opening in the active Furniture.rft template.'

import clr
import math
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Arc, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector,
    Extrusion, Material, BuiltInParameter, Color
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a Furniture family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build shiny trashcan")
    t.Start()
    try:
        # ---- Purge previously-built geometry so reruns are idempotent ----
        old_ids = []
        for e in FilteredElementCollector(doc).OfClass(Extrusion):
            old_ids.append(e.Id)
        for eid in old_ids:
            try:
                doc.Delete(eid)
            except Exception:
                pass

        # ---- Find-or-create our named type ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("Shiny Trashcan - Standard")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_H    = add_param("Height",             SpecTypeId.Length, GroupTypeId.Geometry)
        p_Dia  = add_param("Diameter",           SpecTypeId.Length, GroupTypeId.Geometry)
        p_Wall = add_param("Wall Thickness",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_TopT = add_param("Top Thickness",      SpecTypeId.Length, GroupTypeId.Geometry)
        p_SL   = add_param("Slot Length",        SpecTypeId.Length, GroupTypeId.Geometry)
        p_SW   = add_param("Slot Width",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_SR   = add_param("Slot Corner Radius", SpecTypeId.Length, GroupTypeId.Geometry)

        # Defaults (inputs in inches, converted to feet for the API)
        H    = 36.00      / 12.0   # 3'-0"  total height
        Dia  = 17.00      / 12.0   # 1'-5"  outer diameter
        Wall =  3.0/16.0  / 12.0   # 3/16"  wall thickness
        TopT =  1.0/4.0   / 12.0   # 1/4"   top cap thickness
        SL   = 12.00      / 12.0   # 1'-0"  slot length (long axis, X)
        SW   =  4.75      / 12.0   # 4-3/4" slot width (short axis, Y)
        SR   =  2.00      / 12.0   # 2"     slot corner radius

        fm.Set(p_H, H);     fm.Set(p_Dia, Dia)
        fm.Set(p_Wall, Wall); fm.Set(p_TopT, TopT)
        fm.Set(p_SL, SL);   fm.Set(p_SW, SW);  fm.Set(p_SR, SR)

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        H    = read_len(p_H,    H)
        Dia  = read_len(p_Dia,  Dia)
        Wall = read_len(p_Wall, Wall)
        TopT = read_len(p_TopT, TopT)
        SL   = read_len(p_SL,   SL)
        SW   = read_len(p_SW,   SW)
        SR   = read_len(p_SR,   SR)

        R_out = Dia / 2.0
        R_in  = R_out - Wall

        # ---- Material (polished brass) ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            mat_id = Material.Create(doc, name)
            mat = doc.GetElement(mat_id)
            try:
                mat.Color = Color(212, 175, 55)
                mat.Shininess = 128
                mat.Smoothness = 90
                mat.SurfacePatternColor = Color(212, 175, 55)
            except Exception:
                pass
            return mat_id

        mat_brass_id = find_or_create_material("Brass, Polished")

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- Sketch plane: world XY at floor; we extrude up Z ----
        plane_xy = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
        sk_xy    = SketchPlane.Create(doc, plane_xy)

        def circle_loop_xy(cx, cy, radius):
            """Closed circular CurveArray on the XY plane, made of two half-arcs.
            Revit rejects a single full-sweep arc as a sketch profile."""
            p_right = XYZ(cx + radius, cy, 0)
            p_left  = XYZ(cx - radius, cy, 0)
            p_top   = XYZ(cx, cy + radius, 0)
            p_bot   = XYZ(cx, cy - radius, 0)
            ca = CurveArray()
            ca.Append(Arc.Create(p_right, p_left, p_top))
            ca.Append(Arc.Create(p_left,  p_right, p_bot))
            return ca

        def rounded_rect_loop_xy(cx, cy, length, width, radius):
            """Closed rounded-rectangle CurveArray on the XY plane.
            length = total long-axis dimension (along X)
            width  = total short-axis dimension (along Y)
            radius is clamped so it never exceeds half the shorter side."""
            L = length / 2.0
            W = width  / 2.0
            r = max(0.0, min(radius, min(L, W) - 1e-6))

            # Corner-arc midpoints sit on the 45deg diagonal from each corner center.
            c45 = math.cos(math.pi / 4.0) * r   # = r / sqrt(2)

            ca = CurveArray()
            # Right edge (going +Y)
            ca.Append(Line.CreateBound(
                XYZ(cx + L,           cy - (W - r), 0),
                XYZ(cx + L,           cy + (W - r), 0)))
            # Top-right corner arc
            ca.Append(Arc.Create(
                XYZ(cx + L,           cy + (W - r), 0),
                XYZ(cx + (L - r),     cy + W,       0),
                XYZ(cx + (L - r) + c45, cy + (W - r) + c45, 0)))
            # Top edge (going -X)
            ca.Append(Line.CreateBound(
                XYZ(cx + (L - r),     cy + W,       0),
                XYZ(cx - (L - r),     cy + W,       0)))
            # Top-left corner arc
            ca.Append(Arc.Create(
                XYZ(cx - (L - r),     cy + W,       0),
                XYZ(cx - L,           cy + (W - r), 0),
                XYZ(cx - (L - r) - c45, cy + (W - r) + c45, 0)))
            # Left edge (going -Y)
            ca.Append(Line.CreateBound(
                XYZ(cx - L,           cy + (W - r), 0),
                XYZ(cx - L,           cy - (W - r), 0)))
            # Bottom-left corner arc
            ca.Append(Arc.Create(
                XYZ(cx - L,           cy - (W - r), 0),
                XYZ(cx - (L - r),     cy - W,       0),
                XYZ(cx - (L - r) - c45, cy - (W - r) - c45, 0)))
            # Bottom edge (going +X)
            ca.Append(Line.CreateBound(
                XYZ(cx - (L - r),     cy - W,       0),
                XYZ(cx + (L - r),     cy - W,       0)))
            # Bottom-right corner arc
            ca.Append(Arc.Create(
                XYZ(cx + (L - r),     cy - W,       0),
                XYZ(cx + L,           cy - (W - r), 0),
                XYZ(cx + (L - r) + c45, cy - (W - r) - c45, 0)))
            return ca

        # === Build the trashcan ===
        # Origin: center of footprint at floor. X = slot long axis, Y = slot short axis, Z = up.

        # 1) Solid outer cylinder, full height.
        body_prof = CurveArrArray()
        body_prof.Append(circle_loop_xy(0.0, 0.0, R_out))
        body = fc.NewExtrusion(True, body_prof, sk_xy, H)
        set_material(body, mat_brass_id)

        # 2) Inner void: hollows out the can, leaving wall + bottom plate + top cap intact.
        cavity_h = H - TopT - Wall
        cavity_prof = CurveArrArray()
        cavity_prof.Append(circle_loop_xy(0.0, 0.0, R_in))
        cavity = fc.NewExtrusion(False, cavity_prof, sk_xy, cavity_h)
        ElementTransformUtils.MoveElement(doc, cavity.Id, XYZ(0, 0, Wall))

        # 3) Slot void: cuts the rounded-rectangle opening through the top cap.
        # A small overlap above and below the cap avoids coincident-face artifacts.
        eps = 0.01 / 12.0
        slot_prof = CurveArrArray()
        slot_prof.Append(rounded_rect_loop_xy(0.0, 0.0, SL, SW, SR))
        slot = fc.NewExtrusion(False, slot_prof, sk_xy, TopT + 2.0 * eps)
        ElementTransformUtils.MoveElement(doc, slot.Id, XYZ(0, 0, H - TopT - eps))

        t.Commit()
        print("Done. Built shiny trashcan: 3'-0\" tall, 17\" diameter, brass.")
        print("Origin: center on floor. X = slot long axis, Y = slot short axis, Z = up.")
        print("If voids didn't auto-cut the body, run Modify > Geometry > Cut > Cut Geometry.")
        print("For full parametric flex: Align (AL) outer wall faces and top to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
