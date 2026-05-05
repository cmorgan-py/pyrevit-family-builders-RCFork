# -*- coding: utf-8 -*-
__title__ = 'Build\nSec Desk'
__doc__   = 'Builds a school-lobby security desk (visitor transaction counter at 42", guard worktop at 30", centered kneehole for seated guard) from the active Casework.rft template.'

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
    print("ERROR: Active doc must be a Casework family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build school-lobby security desk")
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

        # ---- Find-or-create our named types ----
        def find_or_create_type(name):
            for typ in fm.Types:
                if typ.Name == name:
                    return typ
            return fm.NewType(name)

        ft_std = find_or_create_type("Security Desk - 8'-0\" (standard lobby)")
        fm.CurrentType = ft_std

        # ---- Add parameters (False = type parameter) ----
        def add_param(name, spec, group):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, False)

        p_L  = add_param("Desk Length",         SpecTypeId.Length, GroupTypeId.Geometry)
        p_D  = add_param("Desk Depth",          SpecTypeId.Length, GroupTypeId.Geometry)
        p_HW = add_param("Worktop Height",      SpecTypeId.Length, GroupTypeId.Geometry)
        p_HT = add_param("Transaction Height",  SpecTypeId.Length, GroupTypeId.Geometry)
        p_TD = add_param("Transaction Depth",   SpecTypeId.Length, GroupTypeId.Geometry)
        p_TT = add_param("Top Thickness",       SpecTypeId.Length, GroupTypeId.Geometry)
        p_PT = add_param("Panel Thickness",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_TK = add_param("Toe Kick Height",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_TR = add_param("Toe Kick Recess",     SpecTypeId.Length, GroupTypeId.Geometry)
        p_KW = add_param("Kneehole Width",      SpecTypeId.Length, GroupTypeId.Geometry)

        # Standard lobby defaults (all values in feet)
        L  = 96.0  / 12.0   # 8'-0" length
        D  = 30.0  / 12.0   # 2'-6" depth
        HW = 30.0  / 12.0   # 30" worktop (seated guard)
        HT = 42.0  / 12.0   # 42" transaction counter (ADA accessible)
        TD = 12.0  / 12.0   # 12" deep transaction shelf (visitor side)
        TT =  1.5  / 12.0   # 1-1/2" top thickness
        PT =  0.75 / 12.0   # 3/4" panel thickness
        TK =  4.0  / 12.0   # 4" toe kick height
        TR =  4.0  / 12.0   # 4" toe kick recess
        KW = 30.0  / 12.0   # 30" kneehole width (ADA min: 30" wide x 27" tall x 19" deep)

        fm.Set(p_L, L);   fm.Set(p_D, D);   fm.Set(p_HW, HW)
        fm.Set(p_HT, HT); fm.Set(p_TD, TD); fm.Set(p_TT, TT)
        fm.Set(p_PT, PT); fm.Set(p_TK, TK); fm.Set(p_TR, TR)
        fm.Set(p_KW, KW)

        # Compact alt: 6'-0" for tight vestibules
        ft_compact = find_or_create_type("Security Desk - 6'-0\" (compact vestibule)")
        fm.CurrentType = ft_compact
        fm.Set(p_L, 72.0 / 12.0)
        fm.Set(p_D, D);   fm.Set(p_HW, HW); fm.Set(p_HT, HT)
        fm.Set(p_TD, TD); fm.Set(p_TT, TT); fm.Set(p_PT, PT)
        fm.Set(p_TK, TK); fm.Set(p_TR, TR); fm.Set(p_KW, KW)

        # Wide alt: 10'-0" for large entry foyers w/ multiple guards
        ft_wide = find_or_create_type("Security Desk - 10'-0\" (large foyer)")
        fm.CurrentType = ft_wide
        fm.Set(p_L, 120.0 / 12.0)
        fm.Set(p_D, D);   fm.Set(p_HW, HW); fm.Set(p_HT, HT)
        fm.Set(p_TD, TD); fm.Set(p_TT, TT); fm.Set(p_PT, PT)
        fm.Set(p_TK, TK); fm.Set(p_TR, TR)
        fm.Set(p_KW, 36.0 / 12.0)   # roomier kneehole on the wide unit

        # Build geometry against the standard type
        fm.CurrentType = ft_std

        def read_len(p, default):
            v = ft_std.AsDouble(p)
            return v if v is not None else default

        L  = read_len(p_L,  L);  D  = read_len(p_D,  D)
        HW = read_len(p_HW, HW); HT = read_len(p_HT, HT)
        TD = read_len(p_TD, TD); TT = read_len(p_TT, TT)
        PT = read_len(p_PT, PT); TK = read_len(p_TK, TK)
        TR = read_len(p_TR, TR); KW = read_len(p_KW, KW)

        # ---- Materials ----
        def find_or_create_material(name):
            for m in FilteredElementCollector(doc).OfClass(Material):
                if m.Name == name:
                    return m.Id
            return Material.Create(doc, name)

        mat_panel_id = find_or_create_material("Plastic Laminate - Maple")
        mat_top_id   = find_or_create_material("Solid Surface - Stone Gray")
        mat_kick_id  = find_or_create_material("Metal - Painted Black")

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
        # Origin at FRONT-CENTER of desk at floor (visitor side, ground).
        #   +X = along desk length (visitor sees the X face)
        #   +Y = back into the security area (toward the guard)
        #   +Z = up
        # Visitor-facing front is at y = 0; guard-facing back is at y = D.
        # Worktop runs full depth at HW. Transaction shelf is the raised
        # ledge on the visitor side at HT, depth TD from front.

        # ---- Toe kicks (one under each pedestal; kneehole zone has open floor) ----
        box(-L/2 + TR, TR, -KW/2,    D - TR, 0.0, TK, mat_kick_id)   # left pedestal
        box( KW/2,     TR,  L/2 - TR, D - TR, 0.0, TK, mat_kick_id)  # right pedestal

        # ---- Carcass shell: gables, modesty, back panels, kneehole side panels ----
        # Left gable (full depth & height under worktop)
        box(-L/2, 0.0, -L/2 + PT, D, TK, HW - TT, mat_panel_id)
        # Right gable
        box( L/2 - PT, 0.0, L/2, D, TK, HW - TT, mat_panel_id)
        # Front modesty panel — full length (kneehole opens from the GUARD side, not the visitor side)
        box(-L/2 + PT, 0.0, L/2 - PT, PT, TK, HW - TT, mat_panel_id)
        # Back panel — split into two segments flanking the kneehole opening
        box(-L/2 + PT, D - PT, -KW/2,    D, TK, HW - TT, mat_panel_id)   # left of kneehole
        box( KW/2,     D - PT,  L/2 - PT, D, TK, HW - TT, mat_panel_id)  # right of kneehole
        # Inboard pedestal panels (form the side walls of the kneehole; finished face toward kneehole)
        box(-KW/2,      PT, -KW/2 + PT, D, TK, HW - TT, mat_panel_id)    # left pedestal inboard
        box( KW/2 - PT, PT,  KW/2,      D, TK, HW - TT, mat_panel_id)    # right pedestal inboard

        # ---- Worktop (full L x D solid-surface slab) ----
        box(-L/2, 0.0, L/2, D, HW - TT, HW, mat_top_id)

        # ---- Transaction counter (raised visitor-side shelf at HT) ----
        # Front fascia panel: from worktop top up to underside of TC top,
        # spanning between the gable end caps that continue up.
        box(-L/2 + PT, 0.0, L/2 - PT, PT, HW, HT - TT, mat_panel_id)
        # End-cap returns on the gables, raised section (continue gables up)
        box(-L/2, 0.0, -L/2 + PT, TD, HW, HT - TT, mat_panel_id)
        box( L/2 - PT, 0.0, L/2, TD, HW, HT - TT, mat_panel_id)
        # Back wall of raised counter (separates visitor shelf from guard worktop)
        box(-L/2 + PT, TD - PT, L/2 - PT, TD, HW, HT - TT, mat_panel_id)
        # Transaction counter top slab (overhangs front edge by 0.5" for visitor grip)
        oh = 0.5 / 12.0
        box(-L/2, -oh, L/2, TD, HT - TT, HT, mat_top_id)

        # ---- Pencil drawer face on the right pedestal (centered on its back panel) ----
        # Sized to fit within the right pedestal's back-panel width with margins.
        right_ped_x_lo = KW/2
        right_ped_x_hi = L/2 - PT
        ped_w          = right_ped_x_hi - right_ped_x_lo
        dw_w           = min(24.0 / 12.0, ped_w - 4.0 / 12.0)   # 24" or pedestal w less 2" each side
        dw_cx          = (right_ped_x_lo + right_ped_x_hi) / 2.0
        dw_h           =  3.0 / 12.0
        dw_inset       =  0.25 / 12.0
        box(dw_cx - dw_w/2, D, dw_cx + dw_w/2, D + dw_inset,
            HW - TT - dw_h - 0.5/12.0, HW - TT - 0.5/12.0, mat_panel_id)

        t.Commit()
        print("Done. Security desk built (active type: 8'-0\" standard lobby).")
        print("Origin is at front-center of desk at floor; visitor side is +Y=0, guard side is +Y=D.")
        print("Kneehole: {:.1f}\" wide x {:.1f}\" tall x {:.1f}\" deep, opens on guard side.".format(
            KW * 12.0, (HW - TT) * 12.0, (D - PT) * 12.0))
        print("For full parametric flex, Align (AL) front, back, end, and kneehole-side faces to ref planes and lock.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
