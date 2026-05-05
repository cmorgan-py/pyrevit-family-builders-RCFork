# -*- coding: utf-8 -*-
__title__ = 'Build\nSimple\nTable'
__doc__   = 'Builds a Shaker-style square dining table (square top, apron skirt, 4 tapered legs) in the active Furniture.rft template.'

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector,
    Extrusion, Blend, Material, BuiltInParameter
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a Furniture family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build simple table")
    t.Start()
    try:
        # ---- Purge previously-built geometry so reruns are idempotent ----
        old_ids = []
        for e in FilteredElementCollector(doc).OfClass(Extrusion):
            old_ids.append(e.Id)
        for e in FilteredElementCollector(doc).OfClass(Blend):
            old_ids.append(e.Id)
        for eid in old_ids:
            try:
                doc.Delete(eid)
            except Exception:
                pass

        # ---- Remove parameters left over from earlier (untapered) versions ----
        def remove_param_if_exists(name):
            p = fm.get_Parameter(name)
            if p is not None:
                try:
                    fm.RemoveParameter(p)
                except Exception:
                    pass
        remove_param_if_exists("Leg Size")

        # ---- Find-or-create our named types ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("Square Table - 30\"x30\"")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_W      = add_param("Width",            SpecTypeId.Length, GroupTypeId.Geometry)
        p_D      = add_param("Depth",            SpecTypeId.Length, GroupTypeId.Geometry)
        p_H      = add_param("Height",           SpecTypeId.Length, GroupTypeId.Geometry)
        p_TopT   = add_param("Top Thickness",    SpecTypeId.Length, GroupTypeId.Geometry)
        p_AprH   = add_param("Apron Height",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_AprT   = add_param("Apron Thickness",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_LegTop = add_param("Leg Top Size",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_LegBot = add_param("Leg Bottom Size",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_Over   = add_param("Top Overhang",     SpecTypeId.Length, GroupTypeId.Geometry)

        # 30"x30" defaults (all values in feet)
        W      = 30.0  / 12.0   # 30" width
        D      = 30.0  / 12.0   # 30" depth
        H      = 30.0  / 12.0   # 30" total height
        TopT   = 1.0   / 12.0   # 1" top thickness
        AprH   = 4.0   / 12.0   # 4" apron height
        AprT   = 0.75  / 12.0   # 3/4" apron thickness
        LegTop = 2.0   / 12.0   # 2" leg square at top
        LegBot = 0.875 / 12.0   # 7/8" leg square at bottom (dramatic Shaker taper)
        Over   = 0.5   / 12.0   # 1/2" top overhang past leg outer face

        fm.Set(p_W, W);          fm.Set(p_D, D);          fm.Set(p_H, H)
        fm.Set(p_TopT, TopT);    fm.Set(p_AprH, AprH);    fm.Set(p_AprT, AprT)
        fm.Set(p_LegTop, LegTop); fm.Set(p_LegBot, LegBot); fm.Set(p_Over, Over)

        # 36"x36" alternate type
        ft_big = find_or_create_type("Square Table - 36\"x36\"")
        fm.CurrentType = ft_big
        fm.Set(p_W, 36.0/12.0); fm.Set(p_D, 36.0/12.0); fm.Set(p_H, H)
        fm.Set(p_TopT, TopT);   fm.Set(p_AprH, AprH);   fm.Set(p_AprT, AprT)
        fm.Set(p_LegTop, LegTop); fm.Set(p_LegBot, LegBot); fm.Set(p_Over, Over)

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        W      = read_len(p_W,      W)
        D      = read_len(p_D,      D)
        H      = read_len(p_H,      H)
        TopT   = read_len(p_TopT,   TopT)
        AprH   = read_len(p_AprH,   AprH)
        AprT   = read_len(p_AprT,   AprT)
        LegTop = read_len(p_LegTop, LegTop)
        LegBot = read_len(p_LegBot, LegBot)
        Over   = read_len(p_Over,   Over)

        # ---- Material ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_wood_id = find_or_create_material("Wood - Walnut Stain")

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- Sketch plane: world XY at floor, extrude up Z ----
        plane_xy = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
        sk_xy    = SketchPlane.Create(doc, plane_xy)

        def rect_loop(x1, y1, x2, y2, z=0.0):
            pts = [XYZ(x1, y1, z), XYZ(x2, y1, z),
                   XYZ(x2, y2, z), XYZ(x1, y2, z)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def box(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(rect_loop(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        def hollow_box(ox1, oy1, ox2, oy2, ix1, iy1, ix2, iy2, z_low, z_high, mat_id=None):
            """Extrusion with an outer rectangle and an inner rectangular hole."""
            prof = CurveArrArray()
            prof.Append(rect_loop(ox1, oy1, ox2, oy2))
            prof.Append(rect_loop(ix1, iy1, ix2, iy2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        def tapered_leg(cx, cy, top_size, bot_size, z_low, z_high, mat_id=None):
            """Square-tapered leg via Blend. Profiles are placed at different Z so
            Revit can compute the loft direction (otherwise NewBlend fails with
            'Unexpected internal error: code 1'). We also set Blend.TopOffset /
            BaseOffset explicitly afterward, since some Revit versions use those
            properties as the source of truth for the actual height."""
            ht = top_size / 2.0
            hb = bot_size / 2.0
            base_prof = rect_loop(cx - hb, cy - hb, cx + hb, cy + hb, z=z_low)
            top_prof  = rect_loop(cx - ht, cy - ht, cx + ht, cy + ht, z=z_high)
            blend = fc.NewBlend(True, top_prof, base_prof, sk_xy)
            try:
                blend.TopOffset  = z_high
                blend.BaseOffset = z_low
            except Exception:
                pass
            if mat_id is not None:
                set_material(blend, mat_id)
            return blend

        # === Coordinate system ===
        # Origin (0,0,0) at the CENTER of the table footprint, on the floor.
        # X = width (left-right), Y = depth (front-back), Z = up.

        hW = W / 2.0
        hD = D / 2.0

        # ---- Top slab ----
        z_top_lo = H - TopT
        z_top_hi = H
        box(-hW, -hD, hW, hD, z_top_lo, z_top_hi, mat_wood_id)

        # ---- Apron (rectangular ring just under the top, inset by Over from the top edge) ----
        apr_z_hi = z_top_lo
        apr_z_lo = apr_z_hi - AprH
        ox1, oy1 = -hW + Over, -hD + Over
        ox2, oy2 =  hW - Over,  hD - Over
        ix1, iy1 = ox1 + AprT, oy1 + AprT
        ix2, iy2 = ox2 - AprT, oy2 - AprT
        hollow_box(ox1, oy1, ox2, oy2, ix1, iy1, ix2, iy2, apr_z_lo, apr_z_hi, mat_wood_id)

        # ---- 4 tapered legs at the corners ----
        # Leg top outer face is flush with apron outer face: leg-top center inset by (Over + LegTop/2) from the table edge.
        leg_z_lo = 0.0
        leg_z_hi = z_top_lo  # top of leg meets bottom of top slab
        leg_inset = Over + LegTop / 2.0
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                cx = sx * (hW - leg_inset)
                cy = sy * (hD - leg_inset)
                tapered_leg(cx, cy, LegTop, LegBot, leg_z_lo, leg_z_hi, mat_wood_id)

        t.Commit()
        print("Done. Built Shaker-style square table (default type: 30\"x30\", 30\" tall, tapered legs).")
        print("Origin: center of table on floor. X=width, Y=depth, Z=up.")
        print("For full parametric flex: Align (AL) faces to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
