---
name: revit-family-pushbutton
description: Use this skill when working in C:\pyRevitCustom (or any pyRevit *.extension folder) and the user asks to create, edit, or debug a Revit family generation script that runs as a pyRevit pushbutton. Triggers include any mention of .rfa families (door, window, casework, lighting fixture, furniture, generic model, etc.), the FamilyManager / FamilyCreate / FamilyItemFactory APIs, family templates (.rft), or pushbutton scaffolding under a *.extension folder. Do NOT use for project-level Revit scripting, Dynamo graphs, Forge / APS workflows, or pure C# Revit addins.
---

# Revit Family Generation via pyRevit Pushbutton

This skill is for writing IronPython scripts that build Revit family files (`.rfa`) by running as pyRevit ribbon-button commands. It covers the lessons that actually trip people up — naming gotchas, parametric locking limitations, sketch geometry rules, type vs instance parameters, visibility settings — the stuff that's hard to discover from API docs alone.

## When this skill applies

The user is working in `C:\pyRevitCustom\` (or another pyRevit custom-extensions folder), wants to write or modify a Python script that:
- Opens a `.rft` family template
- Uses the Revit API to build geometry, parameters, and types
- Runs by clicking a pyRevit ribbon button
- Saves out as a `.rfa` family file

This skill does NOT cover: project-level work, Dynamo, Revit addins in C#, IFC export, Forge/APS, or in-place families (the API doesn't support them).

## Mental model — read this first

A Revit family lives in two parallel structures:

1. **Geometric scaffolding** — reference planes (the "skeleton"), reference lines, sketch planes. Geometry locks to these via dimensions and Align operations. Parameters drive dimensions, dimensions move ref planes, locked geometry follows.
2. **Parameter system** — `FamilyManager` owns parameters and types. `FamilyParameter` is a definition (slot). `FamilyType` is a row of values. Parameter values live on the type, not the parameter.

Geometry is created via `doc.FamilyCreate` (a `FamilyItemFactory`), which has methods like `NewExtrusion`, `NewBlend`, `NewSweep`, `NewRevolution`, `NewSweptBlend`, `NewSymbolicCurve`, `NewModelCurve`, `NewAlignment`. Project-document scripts use `doc.Create` instead — different (smaller) method set. Always reach for `FamilyCreate` first in family work.

## Pushbutton folder structure

```
C:\pyRevitCustom\
└── MyTools.extension\           ← .extension is the registration unit
    └── Custom.tab\              ← becomes a ribbon tab
        └── Family.panel\        ← becomes a panel within the tab
            ├── BuildDoor.pushbutton\
            │   └── script.py
            └── BuildWindow.pushbutton\
                └── script.py
```

User adds `C:\pyRevitCustom` to pyRevit's Custom Extension Directories (pyRevit dropdown → Settings → Custom Extension Directories → Add Folder → Save and Reload). Adding new pushbuttons after that requires `pyRevit → Reload`. Editing an existing pushbutton's `script.py` does **not** require reload — next button click picks up changes.

**ALT-click on any pyRevit button to open its script folder in Explorer** — useful for inspecting community examples.

## Script header

```python
# -*- coding: utf-8 -*-
__title__ = 'Build\nFamily'   # \n wraps the label onto two ribbon lines
__doc__   = 'One-line tooltip describing what the button does.'

import clr
clr.AddReference('RevitAPI')
```

pyRevit injects `__revit__` as a global pointing to the `UIApplication`:

```python
doc   = __revit__.ActiveUIDocument.Document      # active document
uidoc = __revit__.ActiveUIDocument               # UI wrapper (selection, views)
app   = __revit__.Application                    # Application object
```

Always verify family doc is active:

```python
if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a family template (.rft).")
```

## IronPython vs CPython engine

pyRevit defaults to the IronPython 2.7 engine. CPython 3 (PythonNet) is also available but has different behavior. This skill assumes IronPython 2.7:

- `print` works as both statement and function
- `from __future__ import` is available but rarely needed for short scripts
- `List<T>` from `System.Collections.Generic` works directly via `clr`
- `with Transaction(...)` may be unreliable — use explicit Start/Commit/RollBack

To run a script under CPython instead, add `#! python3` as the first line. CPython is needed if you want `numpy`, `pandas`, or any C-extension packages. **For family creation, stay on IronPython** — the Revit API works more naturally with it, and `IFamilyLoadOptions` interfaces have known issues under CPython.

## Template selection

Family category is determined at template-load time and **cannot be changed** afterward (with rare exceptions). Pick the right `.rft` for the family type. Imperial templates live at:

```
C:\ProgramData\Autodesk\RVT 2024\Family Templates\English-Imperial\
```

(Replace `2024` with the user's Revit version.) Common templates:

| Family type | Template | Hosting |
|---|---|---|
| Door | `Door.rft` | wall-hosted |
| Window | `Window.rft` | wall-hosted |
| Casework | `Casework.rft` | non-hosted (or wall) |
| Furniture | `Furniture.rft` | non-hosted |
| Pendant / chandelier / recessed light | `Ceiling Based Lighting Fixture.rft` | ceiling-hosted |
| Wall sconce | `Wall Based Lighting Fixture.rft` | wall-hosted |
| Face-based light | `Generic Model face based.rft` then change category to Lighting Fixtures | face-based |
| Anything attaching to any face | `Generic Model face based.rft` | face-based |
| Plumbing fixture | `Plumbing Fixture.rft` | varies by template |
| Electrical fixture / equipment | `Electrical Fixture.rft` / `Electrical Equipment.rft` | varies |
| Mechanical equipment | `Mechanical Equipment.rft` | non-hosted |
| Detail component (2D only) | `Detail Component.rft` | annotation, view-specific |
| Generic | `Generic Model.rft` | non-hosted |

If imperial templates aren't installed, try `English\` or `Metric\` subfolders. Metric content is often a separate Autodesk download.

**In-place families are not supported by the API.** If the user asks for one, push back — they need to use the GUI or work around it via standard families loaded into the project.

## Internal units — ALWAYS feet, ALWAYS radians

The Revit API uses **decimal feet** internally regardless of project display units. Lengths in, lengths out — feet. Convert at the boundary:

```python
panel_thickness_ft = 1.75 / 12.0     # 1-3/4" panel
height_ft          = 2100.0 / 304.8  # metric: 2100mm → feet
```

**Angles are radians.** A 90° swing arc is `1.5708`, not `90`. Use `math.pi / 2`.

## The standard transaction wrapper

```python
t = Transaction(doc, "Build whatever")
t.Start()
try:
    # ... build geometry, set parameters ...
    t.Commit()
    print("Done.")
except Exception as ex:
    t.RollBack()
    print("FAILED: {}".format(ex))
```

Do NOT use `with Transaction(doc, "..."):` — IronPython 2.7 doesn't reliably support `Transaction` as a context manager. Stick with explicit Start/Commit/RollBack.

For complex operations involving multiple stages, consider `SubTransaction` for partial rollback within a larger transaction. Most family-build scripts don't need this.

## API gotchas — the important section

### 1. `CurveArrArray`, NOT `CurveArrayArray`

The collection-of-curve-arrays type used by `NewExtrusion`, `NewBlend`, `NewRevolution`, `NewSweep` is named with an abbreviation:

```python
from Autodesk.Revit.DB import CurveArray, CurveArrArray   # ✓ correct
from Autodesk.Revit.DB import CurveArray, CurveArrayArray # ✗ ImportError
```

There is no `CurveArrayArray` anywhere in `Autodesk.Revit.DB`. Other abbreviated names: `ElementArray`, `ReferenceArray`, `ModelCurveArray`. When in doubt, search revitapidocs.com for the actual class name.

### 2. `FamilyParameter` has no `.AsDouble()` / `.AsString()`

A `FamilyParameter` is a *definition*, not a value holder. Values live on the `FamilyType`. To read:

```python
ft = fm.CurrentType                   # the active FamilyType
wp = fm.get_Parameter("Width")        # FamilyParameter (definition)
W  = ft.AsDouble(wp)                  # FamilyType.AsDouble(FamilyParameter) → float
```

`ft.AsDouble(wp)` returns `None` if the type has no value set — handle that:

```python
def read_len(param_name, default):
    p = fm.get_Parameter(param_name)
    if p is None: return default
    v = ft.AsDouble(p)
    return v if v is not None else default
```

To set values, use `FamilyManager.Set()`, which sets on the current type:

```python
fm.Set(family_param, value)
```

`FamilyParameter.IsInstance` tells you if it's an instance or type parameter. `.IsReporting` tells you if it's a reporting parameter. `.CanAssignFormula` tells you if it accepts a formula. These are all read-only on the parameter; modifications happen through `FamilyManager` methods.

### 3. `CurrentType` may be None on a fresh template

Some templates ship without a default type. Always ensure one exists before reading or setting parameter values:

```python
ft = fm.CurrentType or fm.NewType("Standard")
fm.CurrentType = ft
```

Do this **before** any `fm.Set(...)` or `ft.AsDouble(...)` calls. Setting a value with no current type raises "There is no valid family type" — this also bites scripts that try to call `SetFormula` first thing.

### 4. Closed circular profiles need two half-arcs, not one 360° arc

`Arc.Create` with a full 2π sweep produces a curve Revit's sketch validator rejects. Build a closed loop from two half-arcs:

```python
def circle_loop(center, radius):
    """Closed circular CurveArray made of two half-arcs (Z-normal)."""
    cx, cy, cz = center.X, center.Y, center.Z
    p_right = XYZ(cx + radius, cy, cz)
    p_left  = XYZ(cx - radius, cy, cz)
    p_top   = XYZ(cx, cy + radius, cz)
    p_bot   = XYZ(cx, cy - radius, cz)
    arc1 = Arc.Create(p_right, p_left, p_top)   # top half
    arc2 = Arc.Create(p_left,  p_right, p_bot)  # bottom half
    ca = CurveArray()
    ca.Append(arc1); ca.Append(arc2)
    return ca
```

Same pattern for ellipses (use `Ellipse.CreateCurve` with start/end params, two halves). The official Revit API docs admit this: "The loop can be a unbound circle or ellipse, but its geometry will be split in two in order to satisfy requirements for sketches."

### 5. Extrusion direction follows sketch plane normal

`fc.NewExtrusion(isSolid, profile, sketchPlane, end)` extrudes from the sketch plane along its **normal**, by `end` units. To extrude in the opposite direction, set `end` negative. Cleaner pattern: build positive, then `MoveElement` afterward.

The `end` parameter must be **non-zero** — passing 0 raises an exception.

### 6. Reference planes have a front/back orientation

Each reference plane has a front face and a back face. Extrusions sketched on a ref plane go toward the front by default. The **front side is opposite the side where the reference plane's name label sits**. This affects `MoveElement` directions and can cause geometry to silently extrude into the wall behind it instead of into the room. If you flip the reference plane direction in the GUI, all geometry hosted on it flips too.

### 7. `FamilyCreate` vs `Create`

In a family document, use `doc.FamilyCreate` (a `FamilyItemFactory`) for `NewExtrusion`, `NewBlend`, `NewSweep`, `NewSymbolicCurve`, etc. `doc.Create` exists but has a different method set. Always reach for `FamilyCreate` first:

```python
fc = doc.FamilyCreate
extrusion = fc.NewExtrusion(True, profile, sketch_plane, 0.5)
```

For **profile-only sweeps**, you also need `doc.Application.Create.NewCurveLoopsProfile(curveArrArray)` to wrap the profile as a `SweepProfile` before passing to `NewSweep`. The `Application.Create` factory is separate from `FamilyCreate`.

### 8. SpecTypeId / GroupTypeId, not UnitType / BuiltInParameterGroup

Pre-2022 Revit used `UnitType.UT_Length` and `BuiltInParameterGroup.PG_GEOMETRY`. These are deprecated. Use:

```python
from Autodesk.Revit.DB import SpecTypeId, GroupTypeId
fm.AddParameter("My Length", GroupTypeId.Geometry, SpecTypeId.Length, False)
```

Common `SpecTypeId` values: `Length`, `Angle`, `Number`, `Area`, `Volume`, `Boolean.YesNo`. For string parameters use `SpecTypeId.String.Text`. For material reference parameters in 2022+, use `SpecTypeId.Reference.Material` (verify against your Revit version's API docs — these names shift).

Common `GroupTypeId` values: `Geometry`, `Constraints`, `Materials`, `IdentityData`, `Graphics`, `Electrical`, `Lighting`, `Mechanical`.

### 9. `AddParameter` — the boolean flag is instance-vs-type

```python
fm.AddParameter(name, group, spec, isInstance)
#                                       ^^^^^^^
#                                       True  = instance parameter
#                                       False = type parameter
```

Type parameters are shared across all instances of a type (changing it changes them all). Instance parameters are unique per placed instance (each door can have its own). For most family-build scripts, type parameters are correct — use `False`.

### 10. Sweep profile must be on the XY plane

`FamilyCreate.NewSweep` requires the profile to be sketched on the XY plane (Z = 0), even though the path can be in 3D. The API will silently transform it onto the path's plane. If you build a profile on a non-XY plane, you'll get `ArgumentException: One of the conditions for the inputs was not satisfied`. The path can be coplanar (set `pathPlane` to the path's plane) or 3D (pass `null` / `None` for the path plane and Revit infers it).

### 11. Materials are referenced by ElementId, not by name

To set a material on geometry, you set the `MATERIAL_ID_PARAM` (or `BuiltInParameter.MATERIAL_ID_PARAM` on individual extrusions). The parameter takes an `ElementId` of a `Material` element:

```python
from Autodesk.Revit.DB import BuiltInParameter, FilteredElementCollector, Material

mats = FilteredElementCollector(doc).OfClass(Material).ToElements()
oak = next((m for m in mats if m.Name == "Oak"), None)
if oak:
    p = extrusion.get_Parameter(BuiltInParameter.MATERIAL_ID_PARAM)
    p.Set(oak.Id)
```

To make material a *family parameter* (so the user can swap it from project), create a parameter of type `Material` (`SpecTypeId.Reference.Material` in 2022+) and use `fm.AssociateElementParameterToFamilyParameter` to link the element's material parameter to the family parameter.

### 12. Symbolic curves vs model curves

- `NewSymbolicCurve(curve, sketchPlane)` — view-specific 2D representation. Use for door swings, plan symbols, anything that should appear in plans/elevations but not in 3D.
- `NewModelCurve(curve, sketchPlane)` — 3D model line, visible in all views.
- `NewDetailCurve(view, curve)` — view-specific (drafting view only), used for 2D detail components.

Symbolic curves are perfect for plan-view representations of 3D objects (e.g., door swing arc).

## Reference planes and parametric locking — HONEST CAVEAT

Programmatically creating geometry that flexes correctly when parameters change is genuinely difficult via API. The reliable workflow:

1. Script builds geometry at the *current* parameter values
2. User manually aligns extrusion edges to reference planes using **Align tool** (`AL` keyboard shortcut) and clicks the padlock icon to lock

Attempting `Dimension.Create` to auto-lock works perhaps 80% of the time and fails silently the other 20%, depending on template and geometry specifics. **Default to instructing the user to lock manually** unless they explicitly ask for an auto-lock attempt.

If you do try auto-locking, the pattern is:

```python
# Get the geometric reference for the extrusion edge and the ref plane
edge_ref = extrusion.get_Geometry(...).Edges[0].Reference
plane_ref = ref_plane.GetReference()
# Create a dimension between them (zero-length, since they should be coincident)
dim = doc.FamilyCreate.NewAlignment(view, plane_ref, edge_ref)
```

This works only when the edge and ref plane are already geometrically aligned. If you create geometry off-axis and try to "pull" it onto a ref plane via a locked dimension, expect failures.

### Reference plane "Is Reference" property — important for usability

Reference planes have an `IsReference` property (`Strong`, `Weak`, `Left`, `Right`, `Top`, `Bottom`, `Front`, `Back`, `Center (Left/Right)`, `Center (Front/Back)`, `Not a Reference`). This controls:

- Whether users can dimension/align to the plane once the family is loaded
- Which plane represents the "Width", "Depth", "Height" sides of the family (for dimensioning conventions)
- How the family aligns when its type is swapped for another family's

For programmatically-created ref planes, set `IsReference` to `Strong` (`Autodesk.Revit.DB.ReferencePlane.IsReference = ...`) for major axes the user should snap to, and `Not a Reference` for internal construction planes the user shouldn't see.

### Reference plane naming

Set the `Name` property on ref planes (especially for "Width", "Depth", "Center (L/R)" etc.). Named planes appear in the dropdown when users place nested face-based families and in tooltips on hover. Unnamed planes still work for geometry but are harder to use later.

## Multiple family types

The `Door.rft` template ships with one type, but most production families have multiple (e.g., 30"x80", 32"x80", 36"x80"). To create:

```python
ft1 = fm.NewType("30\" x 80\"")
fm.CurrentType = ft1
fm.Set(width_param,  30.0/12.0)
fm.Set(height_param, 80.0/12.0)

ft2 = fm.NewType("36\" x 84\"")
fm.CurrentType = ft2
fm.Set(width_param,  36.0/12.0)
fm.Set(height_param, 84.0/12.0)
```

Iterate types: `for ft in fm.Types: ...`. Reorder via `fm.SortParameters(...)` or `fm.ReorderParameters(...)`. Rename via `fm.RenameType(ft, new_name)`.

For very large type sets (50+ types with many parameters), generate a **type catalog** (`.txt` file alongside the `.rfa`) instead of bloating the family file. Type catalogs are out of scope for this skill but worth flagging.

## Formulas

```python
fm.SetFormula(family_param, "Width / 2")
```

Gotchas:
- Must have a valid current type before `SetFormula` is called (same as Set).
- Parameter names with spaces or special characters need bracket-escaping in the formula string. `[Door Width]` not `Door Width`. `Keynote` (a built-in) sometimes needs `[Keynote]` even though it has no spaces.
- Formulas are validated immediately — expect `ArgumentException: It is an invalid formula string.` if the syntax doesn't parse.
- `if(condition, true_value, false_value)` is the conditional. Logical operators are `and`, `or`, `not` (lowercase, like Python).
- Yes/No parameter formulas use `1` / `0` or `true` / `false`.

## Visibility and detail levels

Each geometric element has `IS_VISIBLE_PARAM` (boolean) and a `FamilyElementVisibility` setting controlling which view types and detail levels show it.

```python
from Autodesk.Revit.DB import BuiltInParameter, FamilyElementVisibility, FamilyElementVisibilityType

# Toggle visibility of an extrusion entirely:
extrusion.get_Parameter(BuiltInParameter.IS_VISIBLE_PARAM).Set(0)  # 0 = hidden

# Fine-grained: only show in 3D views and Fine detail level
vis = FamilyElementVisibility(FamilyElementVisibilityType.Model)
vis.IsShownInPlanRCPCut = False
vis.IsShownInFine       = True
vis.IsShownInMedium     = False
vis.IsShownInCoarse     = False
extrusion.SetVisibility(vis)
```

Common pattern for production families: model the same object at three detail levels (Coarse = simplified box, Medium = simplified shape, Fine = full geometry). Each level has its own extrusion(s) with appropriate visibility settings.

## Subcategories

Subcategories let you control line weight, color, and material of specific parts of a family separately. To create one and assign geometry to it:

```python
from Autodesk.Revit.DB import BuiltInCategory, Category

main_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Furniture)
sub = doc.Settings.Categories.NewSubcategory(main_cat, "Cushion")
extrusion.Subcategory = sub
```

Subcategories also enable per-element material assignment via the subcategory's material slot.

## Standard scaffold script

```python
# -*- coding: utf-8 -*-
__title__ = 'Build\nFamily'
__doc__   = 'Builds a family in the active .rft template.'

import clr
import math
clr.AddReference('RevitAPI')

from Autodesk.Revit.DB import (
    Transaction, XYZ, Line, Arc, Plane, SketchPlane,
    CurveArray, CurveArrArray, ElementTransformUtils,
    SpecTypeId, GroupTypeId, FilteredElementCollector, View,
    BuiltInParameter
)

doc = __revit__.ActiveUIDocument.Document

if not doc.IsFamilyDocument:
    print("ERROR: Active doc must be a family template (.rft).")
else:
    fm = doc.FamilyManager
    fc = doc.FamilyCreate

    t = Transaction(doc, "Build family")
    t.Start()
    try:
        # 1. Ensure CurrentType exists
        ft = fm.CurrentType or fm.NewType("Standard")
        fm.CurrentType = ft

        # 2. Add parameters (False = type param, True = instance)
        def add_param(name, spec, group, is_instance=False):
            for p in fm.Parameters:
                if p.Definition.Name == name:
                    return p
            return fm.AddParameter(name, group, spec, is_instance)

        # Example: p_height = add_param("Height", SpecTypeId.Length, GroupTypeId.Geometry)
        # fm.Set(p_height, 7.0)   # 7'-0"

        # 3. Read existing template params via FamilyType
        def read_len(param_name, default):
            p = fm.get_Parameter(param_name)
            if p is None: return default
            v = ft.AsDouble(p)
            return v if v is not None else default

        # 4. Helper: closed circular loop (two half-arcs)
        def circle_loop(center, radius):
            cx, cy, cz = center.X, center.Y, center.Z
            p_right = XYZ(cx + radius, cy, cz); p_left = XYZ(cx - radius, cy, cz)
            p_top   = XYZ(cx, cy + radius, cz); p_bot  = XYZ(cx, cy - radius, cz)
            ca = CurveArray()
            ca.Append(Arc.Create(p_right, p_left, p_top))
            ca.Append(Arc.Create(p_left,  p_right, p_bot))
            return ca

        # 5. Helper: rectangular loop
        def rect_loop(x1, z1, x2, z2):
            pts = [XYZ(x1,0,z1), XYZ(x2,0,z1), XYZ(x2,0,z2), XYZ(x1,0,z2)]
            ca = CurveArray()
            for i in range(4):
                ca.Append(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
            return ca

        # 6. Build geometry
        # ... sketch planes, profiles, extrusions, blends, sweeps ...

        # 7. Optionally add symbolic lines for plan/elevation
        # plan_views = [v for v in FilteredElementCollector(doc).OfClass(View)
        #               if v.ViewType.ToString() == "FloorPlan" and not v.IsTemplate]

        t.Commit()
        print("Done. Now Align+lock edges to ref planes for full parametric flex.")
    except Exception as ex:
        t.RollBack()
        print("FAILED: {}".format(ex))
```

## Iteration workflow

1. Edit `script.py` (VS Code with `gtalarico/ironpython-stubs` for autocomplete).
2. Remind user that they should go to Revit, open the appropriate `.rft` template — make sure it's the active document.
3. Click the pushbutton. Output appears in pyRevit's output window.
4. If it errored: read the traceback, fix, click again. **No reload needed for script edits.**
5. If it succeeded: visually verify in **3D View** first (plan view will often look empty even on success because geometry is on a vertical plane and edge-on in plan). Then check **Elevations** and **Plan**.
6. Remind user to **File → Save As → Family → `name.rfa`** to persist.
7. To test in a project: open or create a project doc, drag the `.rfa` into the view, or use **Insert → Load Family**.

## Saving the family programmatically

If the script should save automatically:

```python
from Autodesk.Revit.DB import SaveAsOptions

opts = SaveAsOptions()
opts.OverwriteExistingFile = True
doc.SaveAs(r"C:\Path\To\Output\my_family.rfa", opts)
```

Note: `SaveAs` requires the document to NOT be the only open document if you want to close it afterward (Revit raises "The active document may not be closed from the API"). Workflow: have a project doc open in another tab, save the family, then `doc.Close(False)`.

## Loading a family into a project document

Done from a *project* document, not the family doc:

```python
class FamilyLoadOptions(IFamilyLoadOptions):
    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = True
        return True
    def OnSharedFamilyFound(self, sharedFamily, familyInUse, source, overwriteParameterValues):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = True
        return True

project_doc.LoadFamily(r"C:\Path\my_family.rfa", FamilyLoadOptions())
```

Under CPython this currently fails with `TypeError: interface takes exactly one argument` — a known issue. Use IronPython for any `IFamilyLoadOptions` work.

## Debugging common errors

| Error / Symptom | Likely cause |
|---|---|
| `ImportError: Cannot import name CurveArrayArray` | Wrong name. It's `CurveArrArray`. |
| `AttributeError: 'FamilyParameter' object has no attribute 'AsDouble'` | Use `family_type.AsDouble(family_param)` instead. |
| `There is no valid family type` | `CurrentType` is None. Create one with `fm.NewType("Standard")` first. |
| `InvalidOperationException: The sketch is not closed` | Curve loop has gaps or self-intersects. For circles, check you used two half-arcs. |
| `The given value for parameter is not within bounds` | Unit error — passing mm or inches where feet were expected. |
| `Family won't load into project` | Category mismatch. The `.rft` you started from determines category permanently. |
| Empty 3D view after success | Geometry is on a sketch plane perpendicular to your view. Check elevation views. |
| `It is an invalid formula string` | Parameter names in formula need bracket-escaping for spaces/specials: `[Door Width]`. |
| `One of the conditions for the inputs was not satisfied` (sweep) | Sweep profile not on XY plane. Build it on Z=0 even if path is elsewhere. |
| `ArgumentException: profile must lie in plane` (extrusion) | Profile curves aren't coplanar. Verify all points share the same Z (or whatever the sketch plane normal axis is). |
| Family loads but parameters don't flex geometry | Geometry not locked to ref planes. User must do Align+lock manually. |

## What this skill does NOT cover

- **In-place families** — the API doesn't support creating them. Push back.
- **Adaptive components** — different API surface (`AdaptiveComponentInstanceUtils`), different mental model. Out of scope.
- **MEP connectors** — `NewElectricalConnector`, `NewDuctConnector`, `NewPipeConnector` exist on `FamilyCreate` for MEP families but require deeper MEP API knowledge. If user needs a real working light fixture (with `LightSource` / photometric IES), this skill is incomplete — direct them to `Autodesk.Revit.DB.Lighting` namespace docs.
- **Type catalogs** (`.txt` files alongside `.rfa` for large type sets).
- **Shared parameters** — possible via `FamilyManager.AddParameter(externalDefinition, ...)` but adds shared-parameter-file management overhead.
- **Massing / conceptual design environment** — uses `NewExtrusionForm`, `NewLoftForm`, `NewSweptBlendForm` (different from `NewExtrusion`, `NewBlend`, `NewSweptBlend`). Out of scope.
- **Project-level scripting** (collecting elements, modifying placed instances, etc.).

## References

- API docs: https://www.revitapidocs.com (pick your Revit version in the dropdown)
- IronPython stubs for VS Code autocomplete: https://github.com/gtalarico/ironpython-stubs
- The Building Coder (Jeremy Tammik): https://thebuildingcoder.typepad.com/blog/family/ — invaluable for obscure family API patterns
- BIM Pure: https://www.bimpure.com/blog — practical family-building guides (UI side)
- pyRevit docs: https://pyrevit.readthedocs.io
- pyRevit forums for IronPython-specific issues: https://discourse.pyrevitlabs.io
- Revit API Forum (Autodesk): https://forums.autodesk.com/t5/revit-api-forum/bd-p/160

## Existing pushbuttons in this folder

When working on a new pushbutton, check the existing ones in this folder for working patterns — they're ground truth for what runs in this Revit version with this pyRevit install. Templates and scaffolds are starting points; existing scripts are evidence.