# -*- coding: utf-8 -*-
__title__ = 'Build\nCouch'
__doc__   = 'Builds a 5-person L-sectional couch (3 seats on main + 2 on return) from the active Furniture.rft template.'

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector,
    Extrusion, Material, BuiltInParameter
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a Furniture family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build L-sectional couch")
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

        # ---- Remove parameters left over from earlier (inline) versions ----
        def remove_param_if_exists(name):
            p = fm.get_Parameter(name)
            if p is not None:
                try:
                    fm.RemoveParameter(p)
                except Exception:
                    pass
        remove_param_if_exists("Length")
        remove_param_if_exists("Number of Seats")

        # ---- Find-or-create our named types ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("L-Sectional - 9'x7' (5-seat)")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_LM = add_param("Main Length",       SpecTypeId.Length, GroupTypeId.Geometry)
        p_LR = add_param("Return Length",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_D  = add_param("Depth",             SpecTypeId.Length, GroupTypeId.Geometry)
        p_H  = add_param("Height",            SpecTypeId.Length, GroupTypeId.Geometry)
        p_SH = add_param("Seat Height",       SpecTypeId.Length, GroupTypeId.Geometry)
        p_AW = add_param("Arm Width",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_BT = add_param("Back Thickness",    SpecTypeId.Length, GroupTypeId.Geometry)
        p_CT = add_param("Cushion Thickness", SpecTypeId.Length, GroupTypeId.Geometry)

        # 9'x7' defaults (all values in feet)
        LM = 108.0 / 12.0   # main length 9'-0"
        LR =  84.0 / 12.0   # return length 7'-0"
        D  =  36.0 / 12.0   # depth 3'-0"
        H  =  32.0 / 12.0   # total height 32"
        SH =  17.0 / 12.0   # seat height 17"
        AW =   5.0 / 12.0   # arm width 5"
        BT =   5.0 / 12.0   # back thickness 5"
        CT =   4.0 / 12.0   # cushion thickness 4"

        fm.Set(p_LM, LM); fm.Set(p_LR, LR); fm.Set(p_D, D)
        fm.Set(p_H,  H);  fm.Set(p_SH, SH); fm.Set(p_AW, AW)
        fm.Set(p_BT, BT); fm.Set(p_CT, CT)

        # Roomier alt: 10'x8' with slightly wider arms
        ft_big = find_or_create_type("L-Sectional - 10'x8' (5-seat, roomy)")
        fm.CurrentType = ft_big
        fm.Set(p_LM, 120.0 / 12.0)
        fm.Set(p_LR,  96.0 / 12.0)
        fm.Set(p_D,  D);  fm.Set(p_H,  H);  fm.Set(p_SH, SH)
        fm.Set(p_AW, 6.0 / 12.0)
        fm.Set(p_BT, BT); fm.Set(p_CT, CT)

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        LM = read_len(p_LM, LM)
        LR = read_len(p_LR, LR)
        D  = read_len(p_D,  D)
        H  = read_len(p_H,  H)
        SH = read_len(p_SH, SH)
        AW = read_len(p_AW, AW)
        BT = read_len(p_BT, BT)
        CT = read_len(p_CT, CT)

        # ---- Materials ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_frame_id   = find_or_create_material("Upholstery - Charcoal")
        mat_cushion_id = find_or_create_material("Upholstery - Charcoal Cushion")

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- Sketch plane: world XY, extrude up Z ----
        plane_xy = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
        sk_xy    = SketchPlane.Create(doc, plane_xy)

        def rect_xy(x1, y1, x2, y2):
            pts = [XYZ(x1, y1, 0), XYZ(x2, y1, 0),
                   XYZ(x2, y2, 0), XYZ(x1, y2, 0)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def box(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(rect_xy(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        # === Coordinate system ===
        # Origin (0,0) at the OUTSIDE-BACK corner of the L (where the two backs meet).
        # Main piece extends in -X from origin, depth D in -Y.    Back at y = 0,  front at y = -D.
        # Return piece extends in -Y from origin, depth D in -X.  Back at x = 0,  front at x = -D.
        # Their D x D overlap (x in [-D,0], y in [-D,0]) is the corner (no cushion).

        # ---- Body blocks (seat-height base) ----
        box(-LM, -D,  0.0, 0.0, 0.0, SH, mat_frame_id)   # main
        box(-D,  -LR, 0.0, 0.0, 0.0, SH, mat_frame_id)   # return (overlaps in corner)

        # ---- Backs (along outer L walls) ----
        box(-LM + AW, -BT, 0.0,  0.0, SH, H, mat_frame_id)   # main back
        box(-BT, -LR + AW, 0.0,  0.0, SH, H, mat_frame_id)   # return back

        # ---- Outer arms (no inner arm at corner) ----
        box(-LM, -D, -LM + AW, 0.0, SH, H, mat_frame_id)        # main left arm
        box(-D, -LR, 0.0, -LR + AW, SH, H, mat_frame_id)        # return bottom arm

        # ---- Seat cushions: 3 along main (X axis) + 2 along return (Y axis) ----
        gap = 0.25 / 12.0   # 1/4" gap between adjacent cushions

        # Main cushions
        n_main = 3
        m_x_lo = -LM + AW
        m_x_hi = -D                       # corner excluded
        m_w    = (m_x_hi - m_x_lo) / n_main
        m_y_lo = -D + 0.5 / 12.0
        m_y_hi = -BT - 0.5 / 12.0
        for i in range(n_main):
            x1 = m_x_lo + i*m_w     + (gap/2 if i > 0          else 0.0)
            x2 = m_x_lo + (i+1)*m_w - (gap/2 if i < n_main - 1 else 0.0)
            box(x1, m_y_lo, x2, m_y_hi, SH, SH + CT, mat_cushion_id)

        # Return cushions
        n_ret  = 2
        r_y_lo = -LR + AW
        r_y_hi = -D                       # corner excluded
        r_w    = (r_y_hi - r_y_lo) / n_ret
        r_x_lo = -D + 0.5 / 12.0
        r_x_hi = -BT - 0.5 / 12.0
        for i in range(n_ret):
            y1 = r_y_lo + i*r_w     + (gap/2 if i > 0         else 0.0)
            y2 = r_y_lo + (i+1)*r_w - (gap/2 if i < n_ret - 1 else 0.0)
            box(r_x_lo, y1, r_x_hi, y2, SH, SH + CT, mat_cushion_id)

        # ---- Back cushions: 3 against main back + 2 against return back ----
        bc_thick = 4.0 / 12.0
        bc_z_lo  = SH + CT + 0.25 / 12.0
        bc_z_hi  = H - 0.5 / 12.0

        # Against main back (y near 0)
        bc_m_y_hi = -BT - 0.25 / 12.0
        bc_m_y_lo = bc_m_y_hi - bc_thick
        for i in range(n_main):
            x1 = m_x_lo + i*m_w     + (gap/2 if i > 0          else 0.0)
            x2 = m_x_lo + (i+1)*m_w - (gap/2 if i < n_main - 1 else 0.0)
            box(x1, bc_m_y_lo, x2, bc_m_y_hi, bc_z_lo, bc_z_hi, mat_cushion_id)

        # Against return back (x near 0)
        bc_r_x_hi = -BT - 0.25 / 12.0
        bc_r_x_lo = bc_r_x_hi - bc_thick
        for i in range(n_ret):
            y1 = r_y_lo + i*r_w     + (gap/2 if i > 0         else 0.0)
            y2 = r_y_lo + (i+1)*r_w - (gap/2 if i < n_ret - 1 else 0.0)
            box(bc_r_x_lo, y1, bc_r_x_hi, y2, bc_z_lo, bc_z_hi, mat_cushion_id)

        t.Commit()
        print("Done. L-sectional built (active type: 9'x7', 3+2 seats).")
        print("Origin is at the outside-back corner of the L; main runs in -X, return runs in -Y.")
        print("Corner is exposed seat-height frame (intentional). For full parametric flex, Align (AL) faces to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
