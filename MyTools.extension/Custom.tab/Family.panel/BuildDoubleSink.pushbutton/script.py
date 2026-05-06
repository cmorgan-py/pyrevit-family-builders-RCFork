# -*- coding: utf-8 -*-
__title__ = 'Build\nDouble\nSink'
__doc__   = 'Builds a double-basin institutional scrub sink from the active Plumbing Fixture.rft template.'

import clr
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    Extrusion, Material, BuiltInParameter,
    SpecTypeId, GroupTypeId, FilteredElementCollector, View
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active document must be a Plumbing Fixture family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build Double Scrub Sink")
    t.Start()
    try:
        # ---- Purge previously-built geometry (idempotent reruns) ----
        old_ids = []
        for e in FilteredElementCollector(doc).OfClass(Extrusion):
            old_ids.append(e.Id)
        for eid in old_ids:
            try:
                doc.Delete(eid)
            except Exception:
                pass

        # ---- Find-or-create family types ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std  = find_or_create_type("Double Scrub Sink - 36\"x24\"")
        ft_wide = find_or_create_type("Double Scrub Sink - 48\"x24\"")

        # ---- Parameters (type parameters, False = type) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        fm.CurrentType = ft_std   # must have CurrentType before fm.Set()

        p_W = add_param("Width",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_D = add_param("Depth",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_H = add_param("Height", SpecTypeId.Length, GroupTypeId.Geometry)

        # Default values in feet
        W_std = 36.0 / 12.0   # 36"
        D_std = 24.0 / 12.0   # 24"
        H_std = 34.0 / 12.0   # 34" floor to rim

        fm.CurrentType = ft_std
        fm.Set(p_W, W_std)
        fm.Set(p_D, D_std)
        fm.Set(p_H, H_std)

        fm.CurrentType = ft_wide
        fm.Set(p_W, 48.0 / 12.0)
        fm.Set(p_D, D_std)
        fm.Set(p_H, H_std)

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            # FamilyType.AsDouble(FamilyParameter) — NOT FamilyParameter.AsDouble()
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        W = read_len(p_W, W_std)
        D = read_len(p_D, D_std)
        H = read_len(p_H, H_std)

        # ---- Geometry constants (all in feet) ----
        body_h    = 10.0 / 12.0   # outer shell height (rim down to underside)
        basin_dep =  9.0 / 12.0   # basin interior depth from rim
        wall_t    =  1.5 / 12.0   # shell wall thickness (all 4 sides)
        back_lip  =  1.5 / 12.0   # basin setback from back inner wall
        front_lip =  2.0 / 12.0   # basin setback from front inner wall (wider ledge)
        div_t     =  1.5 / 12.0   # center divider between basins
        slab_t    =  0.5 / 12.0   # basin floor slab thickness (0.5")
        leg_s     =  1.5 / 12.0   # leg square cross-section
        faucet_h  =  3.0 / 12.0   # faucet bridge height above rim
        faucet_d  =  2.0 / 12.0   # faucet bridge depth (front-to-back)

        hW = W / 2.0
        hD = D / 2.0

        # Origin at CENTER of sink footprint on floor. X=width, Y=depth, Z=up.
        # Y=−hD is the back wall side; Y=+hD is the front (user-facing) side.
        z_rim      = H                # top of sink rim
        z_body_bot = H - body_h      # underside of outer shell
        z_basin_fl = H - basin_dep   # basin floor level

        # ---- Single shared sketch plane at Z=0; use MoveElement for vertical offsets ----
        # (One SketchPlane for all extrusions — established pattern in this extension)
        plane_xy = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
        sk_xy    = SketchPlane.Create(doc, plane_xy)

        def rect_loop(x1, y1, x2, y2):
            """Closed rectangular CurveArray in XY plane at Z=0."""
            pts = [XYZ(x1, y1, 0), XYZ(x2, y1, 0),
                   XYZ(x2, y2, 0), XYZ(x1, y2, 0)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def set_mat(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        def box(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            """Solid rectangular extrusion at the given Z range."""
            prof = CurveArrArray()
            prof.Append(rect_loop(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_mat(ext, mat_id)
            return ext

        def hollow_box(ox1, oy1, ox2, oy2, ix1, iy1, ix2, iy2, z_low, z_high, mat_id=None):
            """Ring extrusion: outer rect with inner rectangular void.
            Open at top and bottom — interior geometry is visible from above."""
            prof = CurveArrArray()
            prof.Append(rect_loop(ox1, oy1, ox2, oy2))  # outer profile
            prof.Append(rect_loop(ix1, iy1, ix2, iy2))  # inner void (must be inside outer)
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_mat(ext, mat_id)
            return ext

        # ---- Materials ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_porcelain = find_or_create_material("Porcelain - White")
        mat_metal     = find_or_create_material("Metal - Satin Stainless")

        # ================================================================
        # GEOMETRY
        # ================================================================

        # 1. Outer sink shell — hollow ring (open top), wall_t thick on all sides.
        #    Open top means basin floors and divider are visible in 3D from above.
        hollow_box(
            -hW, -hD,  hW,  hD,                                         # outer rect
            -hW + wall_t, -hD + wall_t, hW - wall_t, hD - wall_t,       # inner void
            z_body_bot, z_rim,
            mat_porcelain
        )
        print("Built: outer sink shell  ({:.0f}\"W x {:.0f}\"D x {:.0f}\"H, walls {:.1f}\" thick)".format(
            W*12, D*12, body_h*12, wall_t*12))

        # 2. Left basin floor slab (visible inside open shell from above)
        box(
            -hW + wall_t,    -hD + back_lip,
            -div_t / 2.0,     hD - front_lip,
            z_basin_fl, z_basin_fl + slab_t,
            mat_porcelain
        )
        print("Built: left basin floor  ({:.1f}\" below rim)".format(basin_dep * 12))

        # 3. Right basin floor slab
        box(
             div_t / 2.0,    -hD + back_lip,
             hW - wall_t,     hD - front_lip,
            z_basin_fl, z_basin_fl + slab_t,
            mat_porcelain
        )
        print("Built: right basin floor ({:.1f}\" below rim)".format(basin_dep * 12))

        # 4. Center divider — runs basin floor to rim, visible inside open shell
        box(
            -div_t / 2.0,  -hD + back_lip,
             div_t / 2.0,   hD - front_lip,
            z_basin_fl, z_rim,
            mat_porcelain
        )
        print("Built: center divider    ({:.1f}\" thick, {:.1f}\" tall)".format(div_t*12, basin_dep*12))

        # 5. Four legs — square steel tubes from floor to underside of shell
        leg_corners = [
            (-hW,         -hD,         -hW + leg_s,  -hD + leg_s),   # back-left
            ( hW - leg_s, -hD,          hW,           -hD + leg_s),   # back-right
            (-hW,          hD - leg_s,  -hW + leg_s,   hD),           # front-left
            ( hW - leg_s,  hD - leg_s,   hW,            hD),           # front-right
        ]
        for i, (lx1, ly1, lx2, ly2) in enumerate(leg_corners):
            box(lx1, ly1, lx2, ly2, 0.0, z_body_bot, mat_metal)
        print("Built: 4 legs            ({:.1f}\"x{:.1f}\" square, {:.1f}\" tall)".format(
            leg_s*12, leg_s*12, z_body_bot*12))

        # 6. Faucet bridge — full-width bar at back rim representing wall-mount rail
        box(
            -hW, -hD,
             hW, -hD + faucet_d,
            z_rim, z_rim + faucet_h,
            mat_metal
        )
        print("Built: faucet bridge     (full-width, {:.0f}\" tall at back rim)".format(faucet_h*12))

        # 7. Symbolic lines in plan view — footprint outline + basin centerline
        plan_views = [
            v for v in FilteredElementCollector(doc).OfClass(View).ToElements()
            if not v.IsTemplate and v.ViewType.ToString() == "FloorPlan"
        ]
        if plan_views:
            # Sink footprint rectangle
            fp_pts = [XYZ(-hW, -hD, 0), XYZ(hW, -hD, 0),
                      XYZ( hW,  hD, 0), XYZ(-hW, hD, 0)]
            for i in range(4):
                fc.NewSymbolicCurve(
                    Line.CreateBound(fp_pts[i], fp_pts[(i + 1) % 4]),
                    sk_xy
                )
            # Basin centerline
            fc.NewSymbolicCurve(
                Line.CreateBound(XYZ(0, -hD, 0), XYZ(0, hD, 0)),
                sk_xy
            )
            print("Built: plan symbolic lines (footprint + centerline) in '{}'".format(
                plan_views[0].Name))
        else:
            print("No FloorPlan view found in template — symbolic lines skipped.")

        t.Commit()

        print("")
        print("=== BUILD COMPLETE ===")
        print("  Shell:        {:.0f}\"W x {:.0f}\"D x {:.0f}\"H, hollow ring open at top".format(W*12, D*12, body_h*12))
        print("  Basin floors: 2 slabs {:.1f}\" deep, each ~{:.1f}\"W".format(
            basin_dep*12, (hW - wall_t - div_t/2.0)*12))
        print("  Divider:      {:.1f}\" thick center wall, basin floor to rim".format(div_t*12))
        print("  Legs:         4 x {:.1f}\"x{:.1f}\" square, {:.1f}\" tall".format(
            leg_s*12, leg_s*12, z_body_bot*12))
        print("  Faucet rail:  {:.0f}\" tall bar at back rim".format(faucet_h*12))
        print("  Types:        '36\"x24\"' (default) and '48\"x24\"' (wide)")
        print("")
        print("Done. Open a 3D view and Elevation views to verify.")
        print("Use Align (AL) + lock to connect geometry to reference planes for parametric flex.")
        print("Save As -> Family -> DoubleScrubSink.rfa")

    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
