# -*- coding: utf-8 -*-
__title__ = 'Build\nPedestal\nTable'
__doc__   = 'Builds an oval pedestal dining table (oval top, 4-leg splayed pedestal base) in the active Furniture.rft template.'

import clr
import math
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Ellipse, Plane, SketchPlane,
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

    t = Transaction(doc, "Build pedestal table")
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

        # ---- Remove parameters left over from earlier versions ----
        def remove_param_if_exists(name):
            p = fm.get_Parameter(name)
            if p is not None:
                try:
                    fm.RemoveParameter(p)
                except Exception:
                    pass
        for stale in ("Leg Size", "Leg Size at Hub", "Leg Size at Floor",
                      "Hub Size", "Hub Height"):
            remove_param_if_exists(stale)

        # ---- Find-or-create our named types ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("Pedestal Table - 72\"x40\"")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_W       = add_param("Top Long Axis",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_D       = add_param("Top Short Axis",        SpecTypeId.Length, GroupTypeId.Geometry)
        p_H       = add_param("Height",                SpecTypeId.Length, GroupTypeId.Geometry)
        p_TopT    = add_param("Top Thickness",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_FlrSpl  = add_param("Floor Splay Radius",    SpecTypeId.Length, GroupTypeId.Geometry)
        p_TopSpl  = add_param("Top Splay Radius",      SpecTypeId.Length, GroupTypeId.Geometry)
        p_Waist   = add_param("Waist Drop Below Top",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_WTop    = add_param("Leg Width at Top",      SpecTypeId.Length, GroupTypeId.Geometry)
        p_WFlr    = add_param("Leg Width at Floor",    SpecTypeId.Length, GroupTypeId.Geometry)
        p_WWst    = add_param("Leg Width at Waist",    SpecTypeId.Length, GroupTypeId.Geometry)
        p_LegThk  = add_param("Leg Thickness",         SpecTypeId.Length, GroupTypeId.Geometry)

        # 72"x40" defaults (all values in feet)
        W       = 72.0  / 12.0   # top long axis (X)
        D       = 40.0  / 12.0   # top short axis (Y)
        H       = 30.0  / 12.0   # total height
        TopT    = 1.0   / 12.0   # 1" top thickness (slim)
        FlrSpl  = 14.0  / 12.0   # 14" floor splay radius
        TopSpl  = 8.0   / 12.0   # 8" top splay (where upper struts meet underside of top)
        Waist   = 8.0   / 12.0   # waist sits 8" below top
        WTop    = 4.0   / 12.0   # 4" wide blade where it meets the top
        WFlr    = 2.5   / 12.0   # 2-1/2" wide where it meets the floor
        WWst    = 1.25  / 12.0   # 1-1/4" wide at the waist (pinch)
        LegThk  = 0.75  / 12.0   # 3/4" thick (tangential dimension, constant)

        fm.Set(p_W, W);             fm.Set(p_D, D);           fm.Set(p_H, H)
        fm.Set(p_TopT, TopT)
        fm.Set(p_FlrSpl, FlrSpl);   fm.Set(p_TopSpl, TopSpl); fm.Set(p_Waist, Waist)
        fm.Set(p_WTop, WTop);       fm.Set(p_WFlr, WFlr);     fm.Set(p_WWst, WWst)
        fm.Set(p_LegThk, LegThk)

        # 84"x48" alternate type
        ft_big = find_or_create_type("Pedestal Table - 84\"x48\"")
        fm.CurrentType = ft_big
        fm.Set(p_W, 84.0/12.0);   fm.Set(p_D, 48.0/12.0); fm.Set(p_H, H)
        fm.Set(p_TopT, TopT)
        fm.Set(p_FlrSpl, 16.0/12.0); fm.Set(p_TopSpl, 9.0/12.0); fm.Set(p_Waist, Waist)
        fm.Set(p_WTop, WTop);     fm.Set(p_WFlr, WFlr);   fm.Set(p_WWst, WWst)
        fm.Set(p_LegThk, LegThk)

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        W      = read_len(p_W,      W)
        D      = read_len(p_D,      D)
        H      = read_len(p_H,      H)
        TopT   = read_len(p_TopT,   TopT)
        FlrSpl = read_len(p_FlrSpl, FlrSpl)
        TopSpl = read_len(p_TopSpl, TopSpl)
        Waist  = read_len(p_Waist,  Waist)
        WTop   = read_len(p_WTop,   WTop)
        WFlr   = read_len(p_WFlr,   WFlr)
        WWst   = read_len(p_WWst,   WWst)
        LegThk = read_len(p_LegThk, LegThk)

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

        def rect_loop_xy(x1, y1, x2, y2):
            pts = [XYZ(x1, y1, 0), XYZ(x2, y1, 0),
                   XYZ(x2, y2, 0), XYZ(x1, y2, 0)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def ellipse_loop_xy(cx, cy, rx, ry):
            """Closed elliptical loop on the XY plane, made of two half-ellipses
            (Revit rejects a single full-sweep ellipse as a sketch profile)."""
            center = XYZ(cx, cy, 0)
            xaxis  = XYZ(1, 0, 0)
            yaxis  = XYZ(0, 1, 0)
            top_half = Ellipse.CreateCurve(center, rx, ry, xaxis, yaxis, 0.0, math.pi)
            bot_half = Ellipse.CreateCurve(center, rx, ry, xaxis, yaxis, math.pi, 2.0 * math.pi)
            ca = CurveArray()
            ca.Append(top_half)
            ca.Append(bot_half)
            return ca

        def box(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(rect_loop_xy(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        def rect_loop_at(center_xyz, size_rad, size_tang, rad, tang):
            """Closed CurveArray of a (size_rad x size_tang) rectangle centered at
            center_xyz, lying in the plane spanned by rad and tang basis vectors.
            Wound counter-clockwise when viewed from +n (where n = rad x tang) so
            NewBlend treats the loft as solid in the +n direction."""
            hr = size_rad  / 2.0
            ht = size_tang / 2.0
            q1 = center_xyz.Add(rad.Multiply( hr)).Add(tang.Multiply(-ht))
            q2 = center_xyz.Add(rad.Multiply( hr)).Add(tang.Multiply( ht))
            q3 = center_xyz.Add(rad.Multiply(-hr)).Add(tang.Multiply( ht))
            q4 = center_xyz.Add(rad.Multiply(-hr)).Add(tang.Multiply(-ht))
            ca = CurveArray()
            ca.Append(Line.CreateBound(q1, q2))
            ca.Append(Line.CreateBound(q2, q3))
            ca.Append(Line.CreateBound(q3, q4))
            ca.Append(Line.CreateBound(q4, q1))
            return ca

        def tapered_blade(start_xyz, end_xyz,
                          start_width, end_width, thickness,
                          mat_id=None):
            """Tapered flat-blade leg via Blend, going from start to end as a
            'leaning prism'. Cross-section is a HORIZONTAL rectangle at each end
            (so the leg's bottom seats flat on the floor and its top seats flush
            against the underside of the slab — not slanted with the leg axis).
            'width' is the radial dimension (aligned with the XY direction from
            start to end), 'thickness' is the perpendicular horizontal dimension.
            Both profiles lie on parallel horizontal planes (z = start.Z and
            z = end.Z), so Revit can loft between them with NewBlend."""
            # Radial direction in the XY plane: from start toward end (horizontally).
            horiz_d = XYZ(end_xyz.X - start_xyz.X, end_xyz.Y - start_xyz.Y, 0.0)
            if horiz_d.GetLength() < 1e-9:
                rad_xy = XYZ(1, 0, 0)
            else:
                rad_xy = horiz_d.Normalize()
            tang_xy = XYZ(-rad_xy.Y, rad_xy.X, 0.0)

            # Make sure 'base' is the lower-Z profile so the sketch-plane normal (+Z)
            # points from base toward top — NewBlend requires top above base.
            if start_xyz.Z <= end_xyz.Z:
                base_pt, base_w = start_xyz, start_width
                top_pt,  top_w  = end_xyz,   end_width
            else:
                base_pt, base_w = end_xyz,   end_width
                top_pt,  top_w  = start_xyz, start_width

            base_prof = rect_loop_at(base_pt, base_w, thickness, rad_xy, tang_xy)
            top_prof  = rect_loop_at(top_pt,  top_w,  thickness, rad_xy, tang_xy)

            # Use a sketch plane AT the base profile's Z so the base actually
            # lies on the sketch plane (the world XY sk_xy at z=0 doesn't match
            # the upper strut's base at z=waist_z, which produced wrong geometry).
            plane_at_base = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1),
                                                         XYZ(0, 0, base_pt.Z))
            sk = SketchPlane.Create(doc, plane_at_base)
            blend = fc.NewBlend(True, top_prof, base_prof, sk)
            if mat_id is not None:
                set_material(blend, mat_id)
            return blend

        # === Build the table ===
        # Origin (0,0,0): center of footprint at floor level. X = long axis, Y = short axis, Z = up.

        rx = W / 2.0
        ry = D / 2.0

        # ---- Oval top slab ----
        z_top_lo = H - TopT
        z_top_hi = H
        top_prof = CurveArrArray()
        top_prof.Append(ellipse_loop_xy(0.0, 0.0, rx, ry))
        top_ext = fc.NewExtrusion(True, top_prof, sk_xy, TopT)
        ElementTransformUtils.MoveElement(doc, top_ext.Id, XYZ(0, 0, z_top_lo))
        set_material(top_ext, mat_wood_id)

        # ---- Bowtie X-pedestal: 4 lower struts (waist->floor) + 4 upper struts (waist->top) ----
        # All 8 struts converge at a single 'waist' point sitting Waist below the top.
        # Cross-section: a flat blade (wide radial face, thin tangential face), pinched
        # narrow at the waist and flared wide at top and floor.
        waist_z   = z_top_lo - Waist
        waist_pt  = XYZ(0.0, 0.0, waist_z)
        top_meet_z = z_top_lo   # underside of slab
        flr_z      = 0.0

        for i in range(4):
            theta = math.pi / 4.0 + i * math.pi / 2.0   # 45, 135, 225, 315 deg
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            # Lower strut: waist (narrow) -> floor splay (wider)
            flr_pt = XYZ(FlrSpl * cos_t, FlrSpl * sin_t, flr_z)
            tapered_blade(waist_pt, flr_pt,
                          start_width=WWst, end_width=WFlr, thickness=LegThk,
                          mat_id=mat_wood_id)

            # Upper strut: waist (narrow) -> top contact (widest)
            top_pt = XYZ(TopSpl * cos_t, TopSpl * sin_t, top_meet_z)
            tapered_blade(waist_pt, top_pt,
                          start_width=WWst, end_width=WTop, thickness=LegThk,
                          mat_id=mat_wood_id)

        t.Commit()
        print("Done. Built oval bowtie-pedestal table (default type: 72\"x40\", 30\" tall).")
        print("Origin: center on floor. X=long axis, Y=short axis, Z=up.")
        print("For full parametric flex: Align (AL) faces to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
