# -*- coding: utf-8 -*-
__title__ = 'Build\nEm4\nStream'
__doc__   = 'Builds an Emriver Em4 stream table (~4.2m x 1.3m welded aluminum box on legs at 3-deg slope, two reservoirs, T-slot gunwales, vertical standpipe, K500 controller, optional sand bed) in the active Furniture.rft template.'

import clr
import math
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Arc, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector,
    Extrusion, Material, BuiltInParameter, Color, ElementId
)
from System.Collections.Generic import List

print("--- BuildEm4 v2 (step-traced) ---")

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a Furniture family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build Em4 stream table")
    t.Start()
    step = "init"
    try:
        # ---- Purge previously-built geometry so reruns are idempotent ----
        step = "purge"
        old_ids = []
        for e in FilteredElementCollector(doc).OfClass(Extrusion):
            old_ids.append(e.Id)
        for eid in old_ids:
            try:
                doc.Delete(eid)
            except Exception:
                pass

        # ---- Find-or-create our type ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        step = "find_or_create_type"
        ft_std = find_or_create_type("Em4 Stream Table - Standard")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        step = "add_parameters"
        def add_param(name, spec, group, is_instance=False):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, is_instance)

        p_OL    = add_param("Overall Length",  SpecTypeId.Length,        GroupTypeId.Geometry)
        p_OW    = add_param("Overall Width",   SpecTypeId.Length,        GroupTypeId.Geometry)
        p_LH    = add_param("Leg Height",      SpecTypeId.Length,        GroupTypeId.Geometry)
        p_Slope = add_param("Slope Angle",     SpecTypeId.Angle,         GroupTypeId.Constraints)
        p_Show  = add_param("Show Media Bed",  SpecTypeId.Boolean.YesNo, GroupTypeId.Graphics)

        def mm_ft(mm): return mm / 304.8

        # Em4 published spec defaults
        OL_def    = mm_ft(4220.0)        # 4.22 m total footprint length
        OW_def    = mm_ft(1270.0)        # 1.27 m total footprint width
        LH_def    = mm_ft(762.0)         # 30" working height (pivot)
        Slope_def = math.radians(3.0)    # 3-degree designed slope
        Show_def  = 1

        step = "set_param_lengths"
        fm.Set(p_OL,    OL_def)
        fm.Set(p_OW,    OW_def)
        fm.Set(p_LH,    LH_def)
        step = "set_param_slope"
        fm.Set(p_Slope, Slope_def)
        step = "set_param_yesno"
        fm.Set(p_Show,  Show_def)

        def read_double(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        OL    = read_double(p_OL,    OL_def)
        OW    = read_double(p_OW,    OW_def)
        LH    = read_double(p_LH,    LH_def)
        slope = read_double(p_Slope, Slope_def)

        # ---- Materials ----
        def find_or_create_material(name, rgb=None, shiny=None, smooth=None):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            mat_id = Material.Create(doc, name)
            mat = doc.GetElement(mat_id)
            try:
                if rgb is not None:
                    mat.Color = Color(rgb[0], rgb[1], rgb[2])
                    mat.SurfacePatternColor = Color(rgb[0], rgb[1], rgb[2])
                if shiny is not None:
                    mat.Shininess = shiny
                if smooth is not None:
                    mat.Smoothness = smooth
            except Exception:
                pass
            return mat_id

        mat_alum  = find_or_create_material("Aluminum - Anodized",  rgb=(180, 180, 185), shiny=80,  smooth=70)
        mat_plast = find_or_create_material("Plastic - Black",      rgb=(20, 20, 20),    shiny=20,  smooth=40)
        mat_sand  = find_or_create_material("Sand - Modeling Media",rgb=(210, 180, 130), shiny=10,  smooth=10)
        mat_steel = find_or_create_material("Steel - Stainless",    rgb=(200, 200, 205), shiny=110, smooth=85)

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- World XY sketch plane ----
        plane_xy = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
        sk_xy    = SketchPlane.Create(doc, plane_xy)

        # ---- Geometry helpers ----
        def rect_xy(x1, y1, x2, y2):
            pts = [XYZ(x1, y1, 0), XYZ(x2, y1, 0),
                   XYZ(x2, y2, 0), XYZ(x1, y2, 0)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def circle_xy(cx, cy, r):
            ca = CurveArray()
            ca.Append(Arc.Create(XYZ(cx + r, cy, 0), XYZ(cx - r, cy, 0), XYZ(cx, cy + r, 0)))
            ca.Append(Arc.Create(XYZ(cx - r, cy, 0), XYZ(cx + r, cy, 0), XYZ(cx, cy - r, 0)))
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

        def hollow_box(ox1, oy1, ox2, oy2, ix1, iy1, ix2, iy2, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(rect_xy(ox1, oy1, ox2, oy2))
            prof.Append(rect_xy(ix1, iy1, ix2, iy2))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        def cylinder(cx, cy, r, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(circle_xy(cx, cy, r))
            ext = fc.NewExtrusion(True, prof, sk_xy, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        # === Coordinate system ===
        # Origin (0,0,0): center of overall footprint, on the floor.
        # +X = downstream (low end after slope tilt)
        # +Y = right side when looking downstream
        # +Z = up

        # Constants from Em4 spec / typical lab equipment proportions
        wall_t      = mm_ft(10.0)    # aluminum box wall thickness
        box_h       = mm_ft(200.0)   # box wall depth (perpendicular to bottom)
        gun_w       = mm_ft(50.0)    # T-slot gunwale cross-section width (Y)
        gun_h       = mm_ft(50.0)    # T-slot gunwale cross-section height (Z)
        leg_t       = mm_ft(60.0)    # leg square-tube cross-section
        leg_inset   = mm_ft(80.0)    # legs inset from box outer corners
        cstr_d      = mm_ft(80.0)    # caster diameter
        cstr_h      = mm_ft(50.0)    # caster height
        res_h       = mm_ft(300.0)   # reservoir wall height
        res_ext     = mm_ft(260.0)   # how far each reservoir projects beyond box end
        res_inset_y = mm_ft(120.0)   # reservoirs are narrower than box width
        media_t     = mm_ft(40.0)    # modeling media bed thickness

        # Derived: box outer dims (footprint = box + gunwale projections + reservoirs)
        W_box   = OW - gun_w               # gunwales add gun_w/2 on each Y side
        L_box   = OL - 2.0 * res_ext       # reservoirs extend res_ext on each X end
        z_pivot = LH                       # pivot height of leg-top reference plane

        ox1, oy1 = -L_box / 2.0, -W_box / 2.0
        ox2, oy2 =  L_box / 2.0,  W_box / 2.0
        ix1, iy1 = ox1 + wall_t, oy1 + wall_t
        ix2, iy2 = ox2 - wall_t, oy2 - wall_t

        # All "tilts with the box" elements get rotated together at the end.
        tilted_ids = []

        # ---- Main box: 4 walls (hollow extrusion) + bottom plate ----
        step = "main_box_walls"
        walls = hollow_box(ox1, oy1, ox2, oy2, ix1, iy1, ix2, iy2,
                           z_pivot, z_pivot + box_h, mat_alum)
        tilted_ids.append(walls.Id)
        step = "main_box_bottom"
        bottom = box(ox1, oy1, ox2, oy2,
                     z_pivot - wall_t, z_pivot, mat_alum)
        tilted_ids.append(bottom.Id)

        # ---- T-slot gunwales: 2 rails along the long edges ----
        step = "gunwales"
        for sy in (-1.0, 1.0):
            yC = sy * W_box / 2.0
            yL, yH = yC - gun_w / 2.0, yC + gun_w / 2.0
            if yL > yH: yL, yH = yH, yL
            g = box(ox1, yL, ox2, yH,
                    z_pivot + box_h, z_pivot + box_h + gun_h, mat_alum)
            tilted_ids.append(g.Id)

        # ---- Modeling media bed (visibility-controlled) ----
        step = "media_bed"
        media = box(ix1, iy1, ix2, iy2,
                    z_pivot, z_pivot + media_t, mat_sand)
        tilted_ids.append(media.Id)

        # ---- Head reservoir (-X end): 4 walls + bottom plate ----
        step = "head_reservoir"
        h_x1, h_x2 = ox1 - res_ext, ox1
        r_y1 = -W_box / 2.0 + res_inset_y
        r_y2 =  W_box / 2.0 - res_inset_y
        head_walls = hollow_box(
            h_x1, r_y1, h_x2, r_y2,
            h_x1 + wall_t, r_y1 + wall_t, h_x2 - wall_t, r_y2 - wall_t,
            z_pivot, z_pivot + res_h, mat_alum)
        tilted_ids.append(head_walls.Id)
        head_bot = box(h_x1, r_y1, h_x2, r_y2,
                       z_pivot - wall_t, z_pivot, mat_alum)
        tilted_ids.append(head_bot.Id)

        # ---- Tail reservoir (+X end): 4 walls + bottom plate ----
        step = "tail_reservoir"
        t_x1, t_x2 = ox2, ox2 + res_ext
        tail_walls = hollow_box(
            t_x1, r_y1, t_x2, r_y2,
            t_x1 + wall_t, r_y1 + wall_t, t_x2 - wall_t, r_y2 - wall_t,
            z_pivot, z_pivot + res_h, mat_alum)
        tilted_ids.append(tail_walls.Id)
        tail_bot = box(t_x1, r_y1, t_x2, r_y2,
                       z_pivot - wall_t, z_pivot, mat_alum)
        tilted_ids.append(tail_bot.Id)

        # ---- K500 flow controller: small enclosure on -Y gunwale near upstream end ----
        step = "controller"
        ctrl_L, ctrl_W, ctrl_H = mm_ft(150.0), mm_ft(100.0), mm_ft(80.0)
        ctrl_cx = ox1 + mm_ft(150.0) + ctrl_L / 2.0
        ctrl_cy = -W_box / 2.0
        ctrl = box(ctrl_cx - ctrl_L / 2.0, ctrl_cy - ctrl_W / 2.0,
                   ctrl_cx + ctrl_L / 2.0, ctrl_cy + ctrl_W / 2.0,
                   z_pivot + box_h + gun_h,
                   z_pivot + box_h + gun_h + ctrl_H, mat_plast)
        tilted_ids.append(ctrl.Id)

        # ---- Rotate the entire box assembly about Y-axis through (0, 0, z_pivot) ----
        step = "rotate"
        if abs(slope) > 1e-9:
            axis = Line.CreateUnbound(XYZ(0.0, 0.0, z_pivot), XYZ(0.0, 1.0, 0.0))
            id_list = List[ElementId]()
            for eid in tilted_ids:
                id_list.Add(eid)
            ElementTransformUtils.RotateElements(doc, id_list, axis, slope)

        cs = math.cos(slope)
        sn = math.sin(slope)

        # Force any pending state from the rotation to flush before adding more geometry.
        doc.Regenerate()

        # Create a fresh sketch plane for post-rotation extrusions. Reusing sk_xy
        # after RotateElements has been observed to fail subsequent NewExtrusion calls.
        sk_post = SketchPlane.Create(doc, Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0)))

        def cylinder_v(cx, cy, r, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(circle_xy(cx, cy, r))
            ext = fc.NewExtrusion(True, prof, sk_post, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        def box_v(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            prof = CurveArrArray()
            prof.Append(rect_xy(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sk_post, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        step = "standpipe_pipe"
        # ---- Standpipe: vertical (does NOT tilt with the box). Sits in tail reservoir. ----
        sp_local_x = (t_x1 + t_x2) / 2.0                   # mid-tail-reservoir along X
        sp_x_world = sp_local_x * cs                       # post-rotation world X
        sp_z_bot   = z_pivot - sp_local_x * sn             # post-rotation top-of-bottom-plate Z
        sp_height  = mm_ft(250.0)
        sp_z_top   = sp_z_bot + sp_height
        cylinder_v(sp_x_world, 0.0, mm_ft(25.0), sp_z_bot, sp_z_top, mat_steel)

        step = "standpipe_gear"
        # Gear-drive housing on top of standpipe
        cylinder_v(sp_x_world, 0.0, mm_ft(40.0), sp_z_top, sp_z_top + mm_ft(50.0), mat_plast)

        step = "legs"
        # ---- Legs: 4 vertical aluminum tubes, varying heights to support tilted box ----
        # Box bottom-plate corner (local) at (xc, yc, z_pivot - wall_t) maps after rotation to
        #   world_x = xc * cos(slope) - wall_t * sin(slope)        (~ xc for small slopes)
        #   world_z = z_pivot - wall_t * cos(slope) - xc * sin(slope)
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                xc = sx * (L_box / 2.0 - leg_inset)
                yc = sy * (W_box / 2.0 - leg_inset)
                world_x_top = xc * cs - wall_t * sn
                world_z_top = z_pivot - wall_t * cs - xc * sn
                box_v(world_x_top - leg_t / 2.0, yc - leg_t / 2.0,
                      world_x_top + leg_t / 2.0, yc + leg_t / 2.0,
                      cstr_h, world_z_top, mat_alum)
                cylinder_v(world_x_top, yc, cstr_d / 2.0, 0.0, cstr_h, mat_plast)

        # ---- Associate "Show Media Bed" Yes/No to media element's IS_VISIBLE_PARAM ----
        try:
            vis_p = media.get_Parameter(BuiltInParameter.IS_VISIBLE_PARAM)
            if vis_p is not None:
                fm.AssociateElementParameterToFamilyParameter(vis_p, p_Show)
        except Exception:
            pass

        t.Commit()

        h_up_mm = (z_pivot - wall_t * cs + (L_box / 2.0 - leg_inset) * sn - cstr_h) * 304.8
        h_dn_mm = (z_pivot - wall_t * cs - (L_box / 2.0 - leg_inset) * sn - cstr_h) * 304.8
        print("Done. Built Emriver Em4 stream table.")
        print("Footprint: {:.2f} m long x {:.2f} m wide. Slope: {:.1f} deg.".format(
            OL * 0.3048, OW * 0.3048, math.degrees(slope)))
        print("Leg lengths: {:.0f} mm upstream / {:.0f} mm downstream.".format(
            h_up_mm, h_dn_mm))
        print("Origin: center of footprint on floor. +X = downstream (low end after tilt).")
        print("For full parametric flex: Align (AL) outer faces and gunwales to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED at step '{}': {}".format(step, ex))
