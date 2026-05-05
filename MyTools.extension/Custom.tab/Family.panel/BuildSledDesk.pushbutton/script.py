# -*- coding: utf-8 -*-
__title__ = 'Build\nSled\nDesk'
__doc__   = ('Builds a single-student desk with a canted top supported by a square-tube T-base sled: '
             'two vertical posts (the only contact with the top), each meeting a perpendicular '
             'stabilizer foot at the floor (the T-joint), with a ground-level connector bar '
             'tying the two T-joints together. Active doc must be a Furniture.rft template.')

import clr
import math
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

    t = Transaction(doc, "Build sled-leg desk")
    t.Start()
    step = "init"
    try:
        # ---- Purge previously-built geometry so reruns are idempotent ----
        step = "purge old extrusions/blends"
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

        # ---- Remove parameters left over from earlier versions of this script ----
        step = "remove old parameters"
        def remove_param_if_exists(name):
            p = fm.get_Parameter(name)
            if p is not None:
                try:
                    fm.RemoveParameter(p)
                except Exception:
                    pass
        remove_param_if_exists("Frame Inset F/B")
        remove_param_if_exists("Frame Inset L/R")
        remove_param_if_exists("Tube Diameter")

        # ---- Find-or-create our named types ----
        step = "find/create types"
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("Sled Desk - 26\"x20\" (HS)")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        step = "add parameters"
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_W       = add_param("Width",             SpecTypeId.Length, GroupTypeId.Geometry)
        p_D       = add_param("Depth",             SpecTypeId.Length, GroupTypeId.Geometry)
        p_H       = add_param("Top Height (avg)",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_TopT    = add_param("Top Thickness",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_Cant    = add_param("Cant Angle",        SpecTypeId.Angle,  GroupTypeId.Geometry)
        p_Tube    = add_param("Tube Size",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_PostIn  = add_param("Post Inset",        SpecTypeId.Length, GroupTypeId.Geometry)
        p_StabLen = add_param("Stabilizer Length", SpecTypeId.Length, GroupTypeId.Geometry)

        # 26"x20"x29" defaults — high-school sized
        step = "set type values (HS)"
        W       = 26.0  / 12.0
        D       = 20.0  / 12.0
        H       = 29.0  / 12.0
        TopT    = 0.75  / 12.0
        Cant    = math.radians(7.0)
        Tube    = 1.0   / 12.0
        PostIn  = 1.5   / 12.0
        StabLen = 16.0  / 12.0

        fm.Set(p_W, W);    fm.Set(p_D, D);    fm.Set(p_H, H)
        fm.Set(p_TopT, TopT);  fm.Set(p_Cant, Cant);  fm.Set(p_Tube, Tube)
        fm.Set(p_PostIn, PostIn); fm.Set(p_StabLen, StabLen)

        # 22"x18"x24" alt — elementary sized
        step = "set type values (Elem)"
        ft_elem = find_or_create_type("Sled Desk - 22\"x18\" (Elem)")
        fm.CurrentType = ft_elem
        fm.Set(p_W, 22.0/12.0); fm.Set(p_D, 18.0/12.0); fm.Set(p_H, 24.0/12.0)
        fm.Set(p_TopT, TopT);  fm.Set(p_Cant, Cant);  fm.Set(p_Tube, Tube)
        fm.Set(p_PostIn, PostIn); fm.Set(p_StabLen, 14.0/12.0)

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        W       = read_len(p_W,       W)
        D       = read_len(p_D,       D)
        H       = read_len(p_H,       H)
        TopT    = read_len(p_TopT,    TopT)
        Cant    = read_len(p_Cant,    Cant)
        Tube    = read_len(p_Tube,    Tube)
        PostIn  = read_len(p_PostIn,  PostIn)
        StabLen = read_len(p_StabLen, StabLen)

        hW       = W / 2.0
        hD       = D / 2.0
        Th       = Tube / 2.0
        x_post   = hW - PostIn
        y_stab   = StabLen / 2.0
        cosC     = math.cos(Cant)
        sinC     = math.sin(Cant)

        # ---- Materials ----
        step = "create/find materials"
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_steel_id = find_or_create_material("Steel - Powder Coat Black")
        mat_top_id   = find_or_create_material("Laminate - Maple")

        def set_material(elem, mat_id):
            p = elem.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
            if p is not None and not p.IsReadOnly:
                p.Set(mat_id)

        # ---- Helpers ----
        def rect_loop(x1, y1, x2, y2, z=0.0):
            pts = [XYZ(x1, y1, z), XYZ(x2, y1, z),
                   XYZ(x2, y2, z), XYZ(x1, y2, z)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        def box(x1, y1, x2, y2, z_low, z_high, mat_id=None):
            """Axis-aligned box extrusion sketched on world XY, then moved to z_low."""
            plane = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
            sp = SketchPlane.Create(doc, plane)
            prof = CurveArrArray()
            prof.Append(rect_loop(x1, y1, x2, y2))
            ext = fc.NewExtrusion(True, prof, sp, z_high - z_low)
            if abs(z_low) > 1e-9:
                ElementTransformUtils.MoveElement(doc, ext.Id, XYZ(0, 0, z_low))
            if mat_id is not None:
                set_material(ext, mat_id)
            return ext

        # === Coordinate system ===
        # Origin (0,0,0) at the CENTER of the desk footprint, on the floor.
        # X = width (left-right), Y = depth (front-back), Z = up.
        # Cant > 0 tilts the top down toward -Y (front) and up toward +Y (back).

        # ---- Canted top (built directly as a tilted parallelogram extrusion in YZ) ----
        # Sketch plane is the YZ plane at x = -W/2 (normal = +X).
        # The 4 corners trace a parallelogram representing the tilted slab cross-section.
        # Then extrude along +X by W to form the slab. NO rotation needed.
        step = "build canted top"
        plane_top = Plane.CreateByNormalAndOrigin(XYZ(1, 0, 0), XYZ(-hW, 0, 0))
        sp_top = SketchPlane.Create(doc, plane_top)

        x0 = -hW
        # CCW order viewed from -X: front-bot, back-bot, back-top, front-top
        p1 = XYZ(x0, -hD*cosC + (TopT/2.0)*sinC, H - hD*sinC - (TopT/2.0)*cosC)  # front-bot
        p2 = XYZ(x0,  hD*cosC + (TopT/2.0)*sinC, H + hD*sinC - (TopT/2.0)*cosC)  # back-bot
        p3 = XYZ(x0,  hD*cosC - (TopT/2.0)*sinC, H + hD*sinC + (TopT/2.0)*cosC)  # back-top
        p4 = XYZ(x0, -hD*cosC - (TopT/2.0)*sinC, H - hD*sinC + (TopT/2.0)*cosC)  # front-top

        top_corners = [p1, p2, p3, p4]
        top_loop = CurveArray()
        for i in range(4):
            top_loop.Append(Line.CreateBound(top_corners[i], top_corners[(i + 1) % 4]))
        top_prof = CurveArrArray()
        top_prof.Append(top_loop)
        top_ext = fc.NewExtrusion(True, top_prof, sp_top, W)
        set_material(top_ext, mat_top_id)

        # Vertical Z of the canted slab's underside above any (x,y):
        #   z_under(y) = H + y*tan(Cant) - TopT / (2*cos(Cant))
        def underside_z(y):
            return H + y*math.tan(Cant) - TopT / (2.0 * cosC)

        # ---- T-base sled (square steel prism tubes) ----
        z_post_top = underside_z(0.0) + Th  # embed Th into slab so post top isn't a flat disk

        step = "build post (left)"
        box(-x_post - Th, -Th, -x_post + Th, +Th, 0.0, z_post_top, mat_steel_id)

        step = "build post (right)"
        box(+x_post - Th, -Th, +x_post + Th, +Th, 0.0, z_post_top, mat_steel_id)

        step = "build stabilizer foot (left)"
        box(-x_post - Th, -y_stab, -x_post + Th, +y_stab, 0.0, Tube, mat_steel_id)

        step = "build stabilizer foot (right)"
        box(+x_post - Th, -y_stab, +x_post + Th, +y_stab, 0.0, Tube, mat_steel_id)

        step = "build ground connector"
        box(-x_post, -Th, +x_post, +Th, 0.0, Tube, mat_steel_id)

        t.Commit()
        print("Done. T-base sled desk built (default 26\"x20\", 29\" avg top, 7 cant).")
        print("Origin: top center on floor. X=width, Y=depth, Z=up.")
        print("Top tilts down toward -Y (front). Square-tube posts + stabilizer feet + ground connector.")
        print("For full parametric flex: Align (AL) edges to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED at step '{}': {}".format(step, ex))
