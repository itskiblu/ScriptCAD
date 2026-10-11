# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Model Decompiler Engine:
Reverse-engineers manual FreeCAD 3D models, Part primitives, CSG booleans,
PartDesign feature trees, and sketches into clean, readable, procedural ScriptCAD code.
"""

import math
import re
from typing import Dict, List, Tuple, Set, Optional, Any, Union

try:
    import FreeCAD as App
    import Part
    import FreeCADGui as Gui
except ImportError:
    try:
        import FreeCAD as App
        import Part
        Gui = None
    except ImportError:
        App = None
        Part = None
        Gui = None


def sanitize_var_name(name: str) -> str:
    """Convert an object Name or Label into a clean, PEP 8 Python variable identifier."""
    # Replace non-alphanumeric chars with underscore
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean:
        clean = "obj"
    # Ensure it doesn't start with a number
    if clean[0].isdigit():
        clean = "item_" + clean
    # Convert PascalCase / CamelCase to snake_case if appropriate
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", clean).lower()
    snake = re.sub(r"_+", "_", snake).strip("_")
    # Reserve keywords
    if snake in ("def", "class", "import", "from", "for", "while", "if", "else", "elif",
                 "return", "pass", "break", "continue", "in", "is", "as", "and", "or", "not"):
        snake = snake + "_var"
    return snake or "obj"


def round_val(val: float, decimals: int = 4) -> float:
    """Round floating-point values to clean up floating point artifacts."""
    val = round(val, decimals)
    if abs(val) < 10 ** (-decimals):
        return 0.0
    # If it's an integer value, return integer-like float or int
    if val.is_integer():
        return float(int(val))
    return val


def format_num(val: Union[float, int]) -> str:
    """Format a number cleanly for Python code (e.g. 10.0, 5.5)."""
    r = round_val(float(val))
    if r.is_integer():
        return f"{int(r)}.0"
    return str(r)


def fold_chained_transforms(expr: str) -> str:
    """
    Simplify chained CAD transforms, folding multiple .at(...) calls into a single call
    and stripping redundant zero transformations.
    """
    at_pattern = re.compile(
        r"\.at\(([-0-9\.]+),\s*([-0-9\.]+),\s*([-0-9\.]+)\)\.at\(([-0-9\.]+),\s*([-0-9\.]+),\s*([-0-9\.]+)\)"
    )
    for _ in range(5):
        m = at_pattern.search(expr)
        if not m:
            break
        x1, y1, z1, x2, y2, z2 = map(float, m.groups())
        nx = round_val(x1 + x2, 4)
        ny = round_val(y1 + y2, 4)
        nz = round_val(z1 + z2, 4)
        rep = "" if abs(nx) < 1e-4 and abs(ny) < 1e-4 and abs(nz) < 1e-4 else f".at({format_num(nx)}, {format_num(ny)}, {format_num(nz)})"
        expr = expr[:m.start()] + rep + expr[m.end():]

    expr = re.sub(r"\.at\(0(?:\.0)?, 0(?:\.0)?, 0(?:\.0)?\)", "", expr)
    return expr


class ModelDecompiler:
    """
    Decompiles FreeCAD Document Objects into human-readable procedural ScriptCAD scripts.
    Supports:
    - CSG Primitives: Box, Cylinder, Sphere, Cone, Torus, Wedge, Plane, Circle
    - CSG Booleans: Cut (a - b), Fuse (a + b), Common (a & b), Compound
    - Part Operations: Fillet, Chamfer, Extrusion, Revolution, Mirror, Shell
    - PartDesign Features: Body, Pad, Pocket, Hole, LinearPattern, PolarPattern
    - Sketcher Objects: Circles, Rectangles, Polygon profiles
    - Spatial Transformations: Placements, Translations, Rotations (Euler)
    - Prismatic Detection: Reverse-engineers dumb/unparameterized solids
    - Parametric Expressions: Extracts variables from Spreadsheets / ExpressionEngine
    """

    def __init__(self, doc=None, include_header: bool = True, round_digits: int = 4):
        self.doc = doc or (App.ActiveDocument if App else None)
        self.include_header = include_header
        self.round_digits = round_digits
        self.visited: Set[str] = set()
        self.name_map: Dict[str, str] = {}
        self.used_var_names: Set[str] = set()
        self.lines: List[str] = []
        self.params: Dict[str, Any] = {}

    def get_var_name(self, obj) -> str:
        """Allocate a unique, readable variable name for a FreeCAD object."""
        obj_key = getattr(obj, "Name", str(id(obj)))
        if obj_key in self.name_map:
            return self.name_map[obj_key]

        raw_label = getattr(obj, "Label", "") or getattr(obj, "Name", "model")
        base_name = sanitize_var_name(raw_label)

        candidate = base_name
        counter = 1
        while candidate in self.used_var_names:
            counter += 1
            candidate = f"{base_name}_{counter}"

        self.used_var_names.add(candidate)
        self.name_map[obj_key] = candidate
        return candidate

    def extract_placement_calls(self, obj) -> str:
        """
        Decompose an object's Placement into chained .rotate(...) and .at(...) calls.
        """
        if not hasattr(obj, "Placement") or obj.Placement is None:
            return ""

        placement = obj.Placement
        base = placement.Base
        rot = placement.Rotation

        calls = []

        # Check rotations
        if abs(rot.Angle) > 1e-4:
            axis = rot.Axis
            angle_deg = round_val(math.degrees(rot.Angle), self.round_digits)

            # 1. Single pure axis rotation
            if abs(axis.x) < 1e-4 and abs(axis.y) < 1e-4 and abs(axis.z - 1.0) < 1e-4:
                calls.append(f".rotate_z({format_num(angle_deg)})")
            elif abs(axis.x) < 1e-4 and abs(axis.y) < 1e-4 and abs(axis.z + 1.0) < 1e-4:
                calls.append(f".rotate_z({format_num(-angle_deg)})")
            elif abs(axis.x) < 1e-4 and abs(axis.y - 1.0) < 1e-4 and abs(axis.z) < 1e-4:
                calls.append(f".rotate_y({format_num(angle_deg)})")
            elif abs(axis.x) < 1e-4 and abs(axis.y + 1.0) < 1e-4 and abs(axis.z) < 1e-4:
                calls.append(f".rotate_y({format_num(-angle_deg)})")
            elif abs(axis.x - 1.0) < 1e-4 and abs(axis.y) < 1e-4 and abs(axis.z) < 1e-4:
                calls.append(f".rotate_x({format_num(angle_deg)})")
            elif abs(axis.x + 1.0) < 1e-4 and abs(axis.y) < 1e-4 and abs(axis.z) < 1e-4:
                calls.append(f".rotate_x({format_num(-angle_deg)})")
            else:
                # 2. Check if decomposable into standard pairs of axis rotations (e.g. rotate_x then rotate_z)
                decomposed = False
                if App is not None:
                    standard_angles = [-180.0, -135.0, -90.0, -45.0, 45.0, 90.0, 135.0, 180.0]
                    axes_order = [
                        ("x", App.Vector(1, 0, 0), "z", App.Vector(0, 0, 1)),
                        ("x", App.Vector(1, 0, 0), "y", App.Vector(0, 1, 0)),
                        ("y", App.Vector(0, 1, 0), "z", App.Vector(0, 0, 1)),
                        ("y", App.Vector(0, 1, 0), "x", App.Vector(1, 0, 0)),
                        ("z", App.Vector(0, 0, 1), "x", App.Vector(1, 0, 0)),
                        ("z", App.Vector(0, 0, 1), "y", App.Vector(0, 1, 0)),
                    ]
                    for name1, v1, name2, v2 in axes_order:
                        for a1 in standard_angles:
                            r1 = App.Rotation(v1, a1)
                            for a2 in standard_angles:
                                r2 = App.Rotation(v2, a2)
                                comb = r2 * r1
                                if comb.isSame(rot, 1e-3):
                                    calls.append(f".rotate_{name1}({format_num(a1)})")
                                    calls.append(f".rotate_{name2}({format_num(a2)})")
                                    decomposed = True
                                    break
                            if decomposed:
                                break
                        if decomposed:
                            break

                if not decomposed:
                    ax = format_num(axis.x)
                    ay = format_num(axis.y)
                    az = format_num(axis.z)
                    calls.append(f".rotate(({ax}, {ay}, {az}), {format_num(angle_deg)})")

        # Check translation
        bx = round_val(base.x, self.round_digits)
        by = round_val(base.y, self.round_digits)
        bz = round_val(base.z, self.round_digits)

        if abs(bx) > 1e-4 or abs(by) > 1e-4 or abs(bz) > 1e-4:
            calls.append(f".at({format_num(bx)}, {format_num(by)}, {format_num(bz)})")

        return "".join(calls)

    def extract_param_or_val(self, obj, prop_name: str, default: float = 0.0) -> str:
        """Extract property value, checking for spreadsheet expression bindings."""
        if not hasattr(obj, prop_name):
            return format_num(default)

        # Check ExpressionEngine for parameter bindings
        if hasattr(obj, "ExpressionEngine") and obj.ExpressionEngine:
            for prop, expr in obj.ExpressionEngine:
                if prop == prop_name and expr:
                    # Clean expression e.g. <<Spreadsheet>>.box_len -> box_len
                    clean_expr = expr.split(".")[-1].replace("<<", "").replace(">>", "").strip()
                    var_name = sanitize_var_name(clean_expr)
                    val = float(getattr(getattr(obj, prop_name), "Value", getattr(obj, prop_name, default)))
                    self.params[var_name] = round_val(val, self.round_digits)
                    return var_name

        raw_val = getattr(obj, prop_name)
        val = getattr(raw_val, "Value", raw_val)
        try:
            return format_num(float(val))
        except (ValueError, TypeError):
            return format_num(default)

    def decompile_sketch(self, sketch) -> Tuple[str, str]:
        """
        Decompile a Sketcher::SketchObject into a 2D profile representation.
        Returns (var_name, code_line).
        """
        var_name = self.get_var_name(sketch)
        shape = getattr(sketch, "Shape", None)
        inv_place = sketch.Placement.inverse() if hasattr(sketch, "Placement") and sketch.Placement else None

        if shape and hasattr(shape, "Wires") and shape.Wires:
            wire = shape.Wires[0]
            edges = getattr(wire, "Edges", [])

            # Case 1: Single Circular Wire
            if len(edges) == 1 and ("Circle" in type(getattr(edges[0], "Curve", None)).__name__
                                    or getattr(edges[0].Curve, "TypeId", "") in ("Part::GeomCircle", "GeomCircle")):
                curve = edges[0].Curve
                rad = round_val(curve.Radius, self.round_digits)
                if inv_place:
                    local_center = inv_place.multVec(curve.Center)
                else:
                    local_center = curve.Center
                cx = round_val(local_center.x, self.round_digits)
                cy = round_val(local_center.y, self.round_digits)
                line = f"{var_name} = Circle(radius={format_num(rad)})"
                if abs(cx) > 1e-4 or abs(cy) > 1e-4:
                    line += f".at({format_num(cx)}, {format_num(cy)}, 0.0)"
                return var_name, line

            # Case 2: Rectangular Wire or Arbitrary Polygon
            raw_verts = getattr(wire, "OrderedVertexes", getattr(wire, "Vertexes", []))
            if raw_verts:
                local_pts = []
                for v in raw_verts:
                    pt = inv_place.multVec(v.Point) if inv_place else v.Point
                    local_pts.append((round_val(pt.x, self.round_digits), round_val(pt.y, self.round_digits)))

                # Remove duplicate closing/consecutive points
                clean_pts = []
                for p in local_pts:
                    if not clean_pts or abs(clean_pts[-1][0] - p[0]) > 1e-4 or abs(clean_pts[-1][1] - p[1]) > 1e-4:
                        clean_pts.append(p)
                if len(clean_pts) >= 4 and abs(clean_pts[0][0] - clean_pts[-1][0]) < 1e-4 and abs(clean_pts[0][1] - clean_pts[-1][1]) < 1e-4:
                    clean_pts = clean_pts[:-1]

                # Check if rectangular: 4 points, bounding box aligns with edges
                if len(clean_pts) == 4 and len(edges) == 4:
                    xs = [p[0] for p in clean_pts]
                    ys = [p[1] for p in clean_pts]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    w = round_val(max_x - min_x, self.round_digits)
                    h = round_val(max_y - min_y, self.round_digits)
                    # Check if all 4 corners align with bounding box
                    box_corners = {(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)}
                    pts_set = {(p[0], p[1]) for p in clean_pts}
                    if pts_set == box_corners or len(set(xs)) == 2 and len(set(ys)) == 2:
                        cx = round_val((max_x + min_x) / 2.0, self.round_digits)
                        cy = round_val((max_y + min_y) / 2.0, self.round_digits)
                        if abs(cx) < 1e-4 and abs(cy) < 1e-4:
                            line = f"{var_name} = Rectangle(width={format_num(w)}, height={format_num(h)}, center=True)"
                        else:
                            line = f"{var_name} = Rectangle(width={format_num(w)}, height={format_num(h)})"
                            offset_x = round_val(min_x, self.round_digits)
                            offset_y = round_val(min_y, self.round_digits)
                            if abs(offset_x) > 1e-4 or abs(offset_y) > 1e-4:
                                line += f".at({format_num(offset_x)}, {format_num(offset_y)}, 0.0)"
                        return var_name, line

                # Case 3: Polygon / closed wire points
                if len(clean_pts) >= 3:
                    # Enforce counter-clockwise winding (right-hand normal along +Z in sketch local coordinates)
                    area2d = 0.5 * sum(
                        clean_pts[k][0] * clean_pts[(k + 1) % len(clean_pts)][1] -
                        clean_pts[(k + 1) % len(clean_pts)][0] * clean_pts[k][1]
                        for k in range(len(clean_pts))
                    )
                    if area2d < 0:
                        clean_pts = list(reversed(clean_pts))

                    pts_str = ", ".join(f"({format_num(x)}, {format_num(y)})" for x, y in clean_pts)
                    line = f"{var_name} = Polygon([{pts_str}])"
                    return var_name, line

        # Fallback default plane
        line = f"{var_name} = Plane(length=10.0, width=10.0)"
        return var_name, line

    def detect_prismatic_solid(self, obj) -> Optional[Tuple[str, str]]:
        """
        Reverse-engineer unparameterized 'dumb' Part::Features via B-Rep analysis.
        Detects Boxes, Cylinders, and Spheres.
        """
        shape = getattr(obj, "Shape", None)
        if shape is None or not hasattr(shape, "Faces") or not shape.Faces:
            return None

        var_name = self.get_var_name(obj)
        faces = shape.Faces
        solids = getattr(shape, "Solids", [])
        num_faces = len(faces)
        bb = shape.BoundBox

        # 1. Prismatic Box Detection: 6 faces, all planar, orthogonal
        if num_faces == 6 and len(solids) == 1:
            all_planar = all(getattr(f.Surface, "TypeId", "") in ("Part::GeomPlane", "GeomPlane")
                             or "Plane" in type(f.Surface).__name__ for f in faces)
            if all_planar:
                vol = shape.Volume
                bb_vol = bb.XLength * bb.YLength * bb.ZLength
                if abs(vol - bb_vol) < 0.05 * (vol or 1.0):
                    dx = round_val(bb.XLength, self.round_digits)
                    dy = round_val(bb.YLength, self.round_digits)
                    dz = round_val(bb.ZLength, self.round_digits)
                    line = f"{var_name} = Box(length={format_num(dx)}, width={format_num(dy)}, height={format_num(dz)})"
                    # Add translation if not at origin
                    if abs(bb.XMin) > 1e-4 or abs(bb.YMin) > 1e-4 or abs(bb.ZMin) > 1e-4:
                        line += f".at({format_num(bb.XMin)}, {format_num(bb.YMin)}, {format_num(bb.ZMin)})"
                    return var_name, line

        # 2. Prismatic Cylinder Detection: 3 faces (1 cylinder surface + 2 planar discs)
        if num_faces == 3 and len(solids) == 1:
            cyl_faces = [f for f in faces if "Cylinder" in type(f.Surface).__name__
                         or "Cylinder" in getattr(f.Surface, "TypeId", "")]
            if len(cyl_faces) == 1:
                cyl_surf = cyl_faces[0].Surface
                radius = round_val(getattr(cyl_surf, "Radius", bb.XLength / 2.0), self.round_digits)
                height = round_val(bb.ZLength, self.round_digits)
                line = f"{var_name} = Cylinder(radius={format_num(radius)}, height={format_num(height)})"
                cx = round_val((bb.XMin + bb.XMax) / 2.0, self.round_digits)
                cy = round_val((bb.YMin + bb.YMax) / 2.0, self.round_digits)
                cz = round_val(bb.ZMin, self.round_digits)
                if abs(cx) > 1e-4 or abs(cy) > 1e-4 or abs(cz) > 1e-4:
                    line += f".at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})"
                return var_name, line

        # 3. Sphere Detection: 1 spherical surface
        if num_faces == 1 and len(solids) == 1:
            if "Sphere" in type(faces[0].Surface).__name__ or "Sphere" in getattr(faces[0].Surface, "TypeId", ""):
                r = round_val(getattr(faces[0].Surface, "Radius", bb.XLength / 2.0), self.round_digits)
                line = f"{var_name} = Sphere(radius={format_num(r)})"
                cm = shape.CenterOfMass
                if abs(cm.x) > 1e-4 or abs(cm.y) > 1e-4 or abs(cm.z) > 1e-4:
                    line += f".at({format_num(cm.x)}, {format_num(cm.y)}, {format_num(cm.z)})"
                return var_name, line

        return None

    def get_sketch_expr(self, sketch) -> Tuple[str, bool]:
        """
        Decompile a sketch into an inline RHS expression with folded transforms.
        Returns (sketch_expression, is_simple).
        """
        if isinstance(sketch, (tuple, list)) and sketch:
            sketch = sketch[0]
        if sketch is None:
            return "Plane(length=10.0, width=10.0)", True

        _, line = self.decompile_sketch(sketch)
        trans = self.extract_placement_calls(sketch)
        rhs = line.split(" = ", 1)[1] if " = " in line else line
        full = fold_chained_transforms(f"{rhs}{trans}")
        return full, True

    def extract_fillet_data(self, feat) -> Tuple[str, List[int]]:
        """Extract radius and edge index list from a Part/PartDesign fillet."""
        rad_str = "1.0"
        edges_prop = getattr(feat, "Edges", [])
        if hasattr(feat, "Radius"):
            rad_str = self.extract_param_or_val(feat, "Radius", 1.0)
        elif edges_prop:
            for item in edges_prop:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    rad_str = format_num(float(item[1]))
                    break

        edge_indices = []
        if edges_prop:
            for item in edges_prop:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    edge_indices.append(item[0] - 1)
        base_tuple = getattr(feat, "Base", None)
        if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
            for sub in base_tuple[1]:
                if isinstance(sub, str) and "Edge" in sub:
                    num_part = re.findall(r"\d+", sub)
                    if num_part:
                        edge_indices.append(int(num_part[0]) - 1)
        return rad_str, edge_indices

    def extract_chamfer_data(self, feat) -> Tuple[str, List[int]]:
        """Extract chamfer size and edge index list from a Part/PartDesign chamfer."""
        dist_str = "1.0"
        edges_prop = getattr(feat, "Edges", [])
        if hasattr(feat, "Size"):
            dist_str = self.extract_param_or_val(feat, "Size", 1.0)
        elif hasattr(feat, "ChamferSize"):
            dist_str = self.extract_param_or_val(feat, "ChamferSize", 1.0)
        elif edges_prop:
            for item in edges_prop:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    dist_str = format_num(float(item[1]))
                    break

        edge_indices = []
        if edges_prop:
            for item in edges_prop:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    edge_indices.append(item[0] - 1)
        base_tuple = getattr(feat, "Base", None)
        if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
            for sub in base_tuple[1]:
                if isinstance(sub, str) and "Edge" in sub:
                    num_part = re.findall(r"\d+", sub)
                    if num_part:
                        edge_indices.append(int(num_part[0]) - 1)
        return dist_str, edge_indices

    def find_matching_edge_indices(self, sim_shape, fc_base_obj, sub_names: List[str]) -> List[int]:
        """
        Match FreeCAD edges (from feat.Base) to the corresponding edge indices
        in the active simulated ScriptCAD ShapeWrapper or Part.Shape.
        """
        if sim_shape is None:
            return []
        raw_shape = sim_shape.shape if hasattr(sim_shape, "shape") else sim_shape
        if raw_shape is None or not hasattr(raw_shape, "Edges") or not raw_shape.Edges:
            return []

        matched = []
        for sub in sub_names:
            if not hasattr(fc_base_obj, "Shape") or not fc_base_obj.Shape:
                continue
            try:
                fc_edge = fc_base_obj.Shape.getElement(sub)
            except Exception:
                continue
            if fc_edge is None or not hasattr(fc_edge, "CenterOfMass"):
                continue

            fc_com = fc_edge.CenterOfMass
            fc_len = fc_edge.Length
            best_idx = None
            best_dist = 1e9

            for idx, e in enumerate(raw_shape.Edges):
                dist = (e.CenterOfMass - fc_com).Length
                if dist < 1e-2 and abs(e.Length - fc_len) < 1e-2:
                    best_idx = idx
                    break
                elif dist < best_dist and dist < 0.05 and abs(e.Length - fc_len) < 0.1:
                    best_dist = dist
                    best_idx = idx

            if best_idx is not None and best_idx not in matched:
                matched.append(best_idx)

        return sorted(matched)

    def detect_cylindrical_pocket_expr(self, feat, prof_obj) -> Optional[str]:
        """
        Detect if a PartDesign::Pocket profile is a single circle, and decompile it
        into a clean, idiomatic Cylinder(...) subtraction rather than an extruded circle face.
        """
        if isinstance(prof_obj, (tuple, list)) and prof_obj:
            prof_obj = prof_obj[0]
        if not prof_obj or not hasattr(prof_obj, "Shape") or not prof_obj.Shape.Wires:
            return None
        edges = prof_obj.Shape.Wires[0].Edges
        if len(edges) != 1 or "Circle" not in type(edges[0].Curve).__name__:
            return None
        curve = edges[0].Curve
        rad = round_val(curve.Radius, self.round_digits)
        length = float(getattr(getattr(feat, "Length", None), "Value", getattr(feat, "Length", 10.0)))
        length = round_val(abs(length), self.round_digits)
        dir_vec = getattr(feat, "Direction", App.Vector(0, 0, -1) if App else None)
        if dir_vec is None:
            return None
        c = curve.Center
        cx = round_val(c.x, self.round_digits)
        cy = round_val(c.y, self.round_digits)
        cz = round_val(c.z, self.round_digits)

        rad_str = format_num(rad)
        len_str = format_num(length)

        # Downward along -Z
        if abs(dir_vec.x) < 1e-3 and abs(dir_vec.y) < 1e-3 and abs(dir_vec.z - (-1.0)) < 1e-3:
            bz = round_val(c.z - length, self.round_digits)
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).at({format_num(cx)}, {format_num(cy)}, {format_num(bz)})")
        # Horizontal along -Y
        elif abs(dir_vec.x) < 1e-3 and abs(dir_vec.y - (-1.0)) < 1e-3 and abs(dir_vec.z) < 1e-3:
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).rotate_x(90.0).at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})")
        # Horizontal along +Y
        elif abs(dir_vec.x) < 1e-3 and abs(dir_vec.y - 1.0) < 1e-3 and abs(dir_vec.z) < 1e-3:
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).rotate_x(-90.0).at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})")
        # Horizontal along +X
        elif abs(dir_vec.x - 1.0) < 1e-3 and abs(dir_vec.y) < 1e-3 and abs(dir_vec.z) < 1e-3:
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).rotate_y(90.0).at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})")
        # Horizontal along -X
        elif abs(dir_vec.x - (-1.0)) < 1e-3 and abs(dir_vec.y) < 1e-3 and abs(dir_vec.z) < 1e-3:
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).rotate_y(-90.0).at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})")
        # Upward along +Z
        elif abs(dir_vec.x) < 1e-3 and abs(dir_vec.y) < 1e-3 and abs(dir_vec.z - 1.0) < 1e-3:
            return fold_chained_transforms(f"Cylinder(radius={rad_str}, height={len_str}).at({format_num(cx)}, {format_num(cy)}, {format_num(cz)})")

        return None

    def get_circle_radius_val(self, prof_obj) -> str:
        """Extract circle radius string if profile is circular."""
        if not prof_obj or not hasattr(prof_obj, "Shape") or not prof_obj.Shape.Wires:
            return ""
        edges = prof_obj.Shape.Wires[0].Edges
        if len(edges) == 1 and "Circle" in type(edges[0].Curve).__name__:
            return format_num(round_val(edges[0].Curve.Radius, self.round_digits))
        return ""

    def get_human_feature_comment(self, feat, default_desc: str = "") -> str:
        """Format a clean, natural descriptive comment for a CAD operation."""
        label = getattr(feat, "Label", "") or getattr(feat, "Name", "")
        if label and not re.match(r"^(Pad|Pocket|Fillet|Chamfer|Hole|Body)\d*$", label, re.IGNORECASE):
            return f"# {label}"
        if default_desc:
            return f"# {default_desc}"
        return f"# {label}"

    def get_body_feature_chain(self, body_or_tip) -> List[Any]:
        """
        Extract the linear DAG of PartDesign features from base to tip.
        """
        tip = getattr(body_or_tip, "Tip", body_or_tip)
        chain = []
        curr = tip
        visited = set()
        while curr is not None and getattr(curr, "Name", "") not in visited:
            visited.add(curr.Name)
            type_id = getattr(curr, "TypeId", "")
            if type_id not in ("Sketcher::SketchObject", "App::Origin", "App::Line", "App::Plane", "App::Point"):
                chain.append(curr)

            base_feat = getattr(curr, "BaseFeature", None)
            if not base_feat and hasattr(curr, "Base"):
                base_prop = curr.Base
                if isinstance(base_prop, (tuple, list)) and base_prop:
                    base_feat = base_prop[0]
                elif hasattr(base_prop, "TypeId"):
                    base_feat = base_prop
            curr = base_feat

        chain.reverse()
        return chain

    def decompile_primitive_expr(self, obj) -> str:
        """Decompile a primitive shape into its standalone constructor call."""
        type_id = getattr(obj, "TypeId", "")
        trans = self.extract_placement_calls(obj)
        if type_id == "Part::Box":
            length = self.extract_param_or_val(obj, "Length", 10.0)
            width = self.extract_param_or_val(obj, "Width", 10.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            if length == width == height:
                return fold_chained_transforms(f"Cube(size={length}){trans}")
            return fold_chained_transforms(f"Box(length={length}, width={width}, height={height}){trans}")
        elif type_id == "Part::Cylinder":
            radius = self.extract_param_or_val(obj, "Radius", 2.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            return fold_chained_transforms(f"Cylinder(radius={radius}, height={height}){trans}")
        elif type_id == "Part::Sphere":
            radius = self.extract_param_or_val(obj, "Radius", 5.0)
            return fold_chained_transforms(f"Sphere(radius={radius}){trans}")
        elif type_id == "Part::Cone":
            r1 = self.extract_param_or_val(obj, "Radius1", 2.0)
            r2 = self.extract_param_or_val(obj, "Radius2", 4.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            return fold_chained_transforms(f"Cone(radius1={r1}, radius2={r2}, height={height}){trans}")

        prismatic = self.detect_prismatic_solid(obj)
        if prismatic is not None:
            _, line = prismatic
            rhs = line.split(" = ", 1)[1] if " = " in line else line
            return fold_chained_transforms(f"{rhs}{trans}")
        return fold_chained_transforms(f"Box(10.0, 10.0, 10.0){trans}")

    def decompile_partdesign_body(self, body) -> str:
        """
        Decompiles a PartDesign::Body into clean, standard, sequential Python code
        with an evolving model variable, accurate extrusion directions, and
        geometrically resolved edge indices for fillets and chamfers.
        """
        body_name = getattr(body, "Name", "")
        if body_name in self.name_map:
            return self.name_map[body_name]

        model_var = self.get_var_name(body)
        self.visited.add(body_name)
        self.name_map[body_name] = model_var

        chain = self.get_body_feature_chain(body)
        if not chain:
            self.lines.append(f"{model_var} = Box(10.0, 10.0, 10.0)")
            return model_var

        # Mark all member features in the chain as visited
        for feat in chain:
            self.visited.add(feat.Name)
            self.name_map[feat.Name] = model_var

        # Simulated shape execution environment for geometric edge matching
        sim_env: Dict[str, Any] = {}
        try:
            import scriptcad
            for name in dir(scriptcad):
                if not name.startswith("_"):
                    sim_env[name] = getattr(scriptcad, name)
        except Exception:
            pass

        sim_body: Optional[Any] = None

        def eval_sim(expr_code: str) -> Optional[Any]:
            try:
                eval_locals = dict(sim_env)
                if sim_body is not None:
                    eval_locals[model_var] = sim_body
                return eval(expr_code, {"__builtins__": None}, eval_locals)
            except Exception:
                return None

        # 1. Base Feature
        base_feat = chain[0]
        base_type = getattr(base_feat, "TypeId", "")

        if base_type == "PartDesign::Pad":
            profile = getattr(base_feat, "Profile", None)
            sketch_expr, _ = self.get_sketch_expr(profile)
            length_str = self.extract_param_or_val(base_feat, "Length", 10.0)
            if getattr(base_feat, "Reversed", False):
                length_str = f"-{length_str}"
            trans = self.extract_placement_calls(base_feat)
            base_expr = fold_chained_transforms(f"{sketch_expr}.extrude({length_str}){trans}")
            comment = self.get_human_feature_comment(base_feat, "Base plate")
            self.lines.append(f"{comment}")
            self.lines.append(f"{model_var} = {base_expr}")
            sim_body = eval_sim(base_expr)
        elif base_type == "PartDesign::Revolution":
            profile = getattr(base_feat, "Profile", None)
            sketch_expr, _ = self.get_sketch_expr(profile)
            angle_str = self.extract_param_or_val(base_feat, "Angle", 360.0)
            trans = self.extract_placement_calls(base_feat)
            base_expr = fold_chained_transforms(f"{sketch_expr}.revolve(angle={angle_str}){trans}")
            comment = self.get_human_feature_comment(base_feat, "Revolved body")
            self.lines.append(f"{comment}")
            self.lines.append(f"{model_var} = {base_expr}")
            sim_body = eval_sim(base_expr)
        else:
            prim_expr = self.decompile_primitive_expr(base_feat)
            comment = self.get_human_feature_comment(base_feat, "Base feature")
            self.lines.append(f"{comment}")
            self.lines.append(f"{model_var} = {prim_expr}")
            sim_body = eval_sim(prim_expr)

        # 2. Sequential Features
        i = 1
        n = len(chain)
        while i < n:
            feat = chain[i]
            feat_type = getattr(feat, "TypeId", "")

            # Group consecutive Fillets with matching radius
            if feat_type in ("PartDesign::Fillet", "Part::Fillet"):
                start_i = i
                rad_str, fallback_edges = self.extract_fillet_data(feat)
                fillet_group = [feat]
                while i + 1 < n and getattr(chain[i + 1], "TypeId", "") in ("PartDesign::Fillet", "Part::Fillet"):
                    next_rad, _ = self.extract_fillet_data(chain[i + 1])
                    if next_rad == rad_str:
                        fillet_group.append(chain[i + 1])
                        i += 1
                    else:
                        break

                matched_edges = []
                if sim_body is not None:
                    for f_item in fillet_group:
                        base_tuple = getattr(f_item, "Base", None)
                        if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
                            base_obj = base_tuple[0]
                            sub_names = [s for s in base_tuple[1] if isinstance(s, str) and "Edge" in s]
                            matched_edges.extend(self.find_matching_edge_indices(sim_body, base_obj, sub_names))

                matched_edges = sorted(list(set(matched_edges)))
                final_edges = matched_edges if matched_edges else fallback_edges

                base_shape = sim_body.shape if sim_body else getattr(feat, "Shape", None)
                tot = len(base_shape.Edges) if base_shape and hasattr(base_shape, "Edges") else 0

                prev_feat = chain[start_i - 1] if start_i > 0 else None
                prev_prof = getattr(prev_feat, "Profile", None) if prev_feat else None
                prev_expr, _ = self.get_sketch_expr(prev_prof) if prev_prof else ("", False)

                if start_i == 1:
                    default_desc = "Base corner fillets"
                elif "Polygon" in prev_expr:
                    default_desc = "Gusset transition fillets"
                elif "Rectangle" in prev_expr:
                    default_desc = "Upright corner fillets"
                elif len(final_edges) == 1:
                    default_desc = "Joint seam fillet"
                elif float(rad_str) >= 2.0:
                    default_desc = "Corner fillets"
                else:
                    default_desc = "Edge fillets"

                comment = self.get_human_feature_comment(feat, default_desc)
                self.lines.append(f"\n{comment}")
                if not final_edges or (tot > 0 and len(final_edges) >= tot):
                    self.lines.append(f"{model_var} = {model_var}.fillet(radius={rad_str})")
                    if sim_body is not None:
                        try:
                            sim_body = sim_body.fillet(radius=float(rad_str))
                        except Exception:
                            pass
                else:
                    self.lines.append(f"{model_var} = {model_var}.fillet(radius={rad_str}, edge_indices={final_edges})")
                    if sim_body is not None:
                        try:
                            sim_body = sim_body.fillet(radius=float(rad_str), edge_indices=final_edges)
                        except Exception:
                            pass
                i += 1
                continue

            # Group consecutive Chamfers with matching distance
            elif feat_type in ("PartDesign::Chamfer", "Part::Chamfer"):
                dist_str, fallback_edges = self.extract_chamfer_data(feat)
                chamfer_group = [feat]
                while i + 1 < n and getattr(chain[i + 1], "TypeId", "") in ("PartDesign::Chamfer", "Part::Chamfer"):
                    next_dist, _ = self.extract_chamfer_data(chain[i + 1])
                    if next_dist == dist_str:
                        chamfer_group.append(chain[i + 1])
                        i += 1
                    else:
                        break

                matched_edges = []
                if sim_body is not None:
                    for c_item in chamfer_group:
                        base_tuple = getattr(c_item, "Base", None)
                        if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
                            base_obj = base_tuple[0]
                            sub_names = [s for s in base_tuple[1] if isinstance(s, str) and "Edge" in s]
                            matched_edges.extend(self.find_matching_edge_indices(sim_body, base_obj, sub_names))

                matched_edges = sorted(list(set(matched_edges)))
                final_edges = matched_edges if matched_edges else fallback_edges

                base_shape = sim_body.shape if sim_body else getattr(feat, "Shape", None)
                tot = len(base_shape.Edges) if base_shape and hasattr(base_shape, "Edges") else 0

                is_hole_chamfer = False
                if sim_body is not None and final_edges:
                    try:
                        e = sim_body.shape.Edges[final_edges[0]]
                        if "Circle" in type(e.Curve).__name__:
                            is_hole_chamfer = True
                    except Exception:
                        pass
                default_desc = "Mounting hole chamfers" if is_hole_chamfer else "Edge chamfers"
                comment = self.get_human_feature_comment(feat, default_desc)
                self.lines.append(f"\n{comment}")

                if not final_edges or (tot > 0 and len(final_edges) >= tot):
                    self.lines.append(f"{model_var} = {model_var}.chamfer(distance={dist_str})")
                    if sim_body is not None:
                        try:
                            sim_body = sim_body.chamfer(distance=float(dist_str))
                        except Exception:
                            pass
                else:
                    self.lines.append(f"{model_var} = {model_var}.chamfer(distance={dist_str}, edge_indices={final_edges})")
                    if sim_body is not None:
                        try:
                            sim_body = sim_body.chamfer(distance=float(dist_str), edge_indices=final_edges)
                        except Exception:
                            pass
                i += 1
                continue

            # Subtractive Pocket: model -= tool
            elif feat_type == "PartDesign::Pocket":
                profile = getattr(feat, "Profile", None)
                prof_obj = profile[0] if isinstance(profile, (tuple, list)) and profile else profile
                cyl_expr = self.detect_cylindrical_pocket_expr(feat, prof_obj)
                if cyl_expr:
                    dir_vec = getattr(feat, "Direction", None)
                    if dir_vec and abs(dir_vec.z) > 0.5:
                        default_comment = "Base mounting hole"
                    else:
                        default_comment = "Upright mounting hole"
                    comment = self.get_human_feature_comment(feat, default_comment)
                    self.lines.append(f"\n{comment}")
                    self.lines.append(f"{model_var} -= {cyl_expr}")
                    if sim_body is not None:
                        tool_shape = eval_sim(cyl_expr)
                        if tool_shape is not None:
                            sim_body = sim_body - tool_shape
                    i += 1
                    continue

                sketch_expr, _ = self.get_sketch_expr(profile)
                length_str = self.extract_param_or_val(feat, "Length", 10.0)
                try:
                    length_val = float(length_str)
                except ValueError:
                    length_val = 10.0

                sketch_shape = getattr(prof_obj, "Shape", None)
                sketch_norm = None
                if sketch_shape and hasattr(sketch_shape, "Faces") and sketch_shape.Faces:
                    try:
                        sketch_norm = sketch_shape.Faces[0].normalAt(0, 0)
                    except Exception:
                        pass
                if sketch_norm is None and hasattr(prof_obj, "Placement") and prof_obj.Placement:
                    sketch_norm = prof_obj.Placement.Rotation.multVec(App.Vector(0, 0, 1))

                feat_dir = getattr(feat, "Direction", None)
                is_reversed = getattr(feat, "Reversed", False)
                if feat_dir and sketch_norm and feat_dir.dot(sketch_norm) < -0.1:
                    length_str = format_num(-abs(length_val))
                elif is_reversed:
                    length_str = format_num(abs(length_val))
                else:
                    length_str = format_num(-abs(length_val))

                trans = self.extract_placement_calls(feat)
                tool_expr = fold_chained_transforms(f"{sketch_expr}.extrude({length_str}){trans}")
                comment = self.get_human_feature_comment(feat, "Recess cutout")
                self.lines.append(f"\n{comment}")
                self.lines.append(f"{model_var} -= {tool_expr}")
                if sim_body is not None:
                    tool_shape = eval_sim(tool_expr)
                    if tool_shape is not None:
                        sim_body = sim_body - tool_shape
                i += 1
                continue

            # Subtractive Hole: model -= Cylinder(...)
            elif feat_type == "PartDesign::Hole":
                dia = float(getattr(getattr(feat, "Diameter", None), "Value", getattr(feat, "Diameter", 6.0)))
                depth = float(getattr(getattr(feat, "Depth", None), "Value", getattr(feat, "Depth", 10.0)))
                trans = self.extract_placement_calls(feat)
                tool_expr = fold_chained_transforms(f"Cylinder(radius={format_num(dia / 2.0)}, height={format_num(depth)}){trans}")
                comment = self.get_human_feature_comment(feat, "Mounting hole")
                self.lines.append(f"\n{comment}")
                self.lines.append(f"{model_var} -= {tool_expr}")
                if sim_body is not None:
                    tool_shape = eval_sim(tool_expr)
                    if tool_shape is not None:
                        sim_body = sim_body - tool_shape
                i += 1
                continue

            # Additive Pad: model += tool
            elif feat_type == "PartDesign::Pad":
                profile = getattr(feat, "Profile", None)
                sketch_expr, is_simple = self.get_sketch_expr(profile)
                length_str = self.extract_param_or_val(feat, "Length", 10.0)
                try:
                    length_val = float(length_str)
                except ValueError:
                    length_val = 10.0

                prof_obj = profile[0] if isinstance(profile, (tuple, list)) and profile else profile
                sketch_shape = getattr(prof_obj, "Shape", None)
                sketch_norm = None
                if sketch_shape and hasattr(sketch_shape, "Faces") and sketch_shape.Faces:
                    try:
                        sketch_norm = sketch_shape.Faces[0].normalAt(0, 0)
                    except Exception:
                        pass
                if sketch_norm is None and hasattr(prof_obj, "Placement") and prof_obj.Placement:
                    sketch_norm = prof_obj.Placement.Rotation.multVec(App.Vector(0, 0, 1))

                feat_dir = getattr(feat, "Direction", None)
                is_reversed = getattr(feat, "Reversed", False)
                if feat_dir and sketch_norm and feat_dir.dot(sketch_norm) < -0.1:
                    length_val = -length_val
                if is_reversed:
                    length_val = -length_val
                length_str = format_num(length_val)

                trans = self.extract_placement_calls(feat)
                if "Polygon" in sketch_expr:
                    default_desc = "Side gusset / rib"
                elif "Rectangle" in sketch_expr:
                    default_desc = "Upright support wall" if i <= 4 else "Support wall"
                else:
                    default_desc = "Extruded feature"
                comment = self.get_human_feature_comment(feat, default_desc)
                self.lines.append(f"\n{comment}")

                tool_expr = fold_chained_transforms(f"{sketch_expr}.extrude({length_str}){trans}")
                self.lines.append(f"{model_var} += {tool_expr}")
                if sim_body is not None:
                    tool_shape = eval_sim(tool_expr)
                    if tool_shape is not None:
                        sim_body = sim_body + tool_shape
                i += 1
                continue

            # Patterns
            elif feat_type == "PartDesign::LinearPattern":
                occurrences = int(getattr(feat, "Occurrences", 3))
                length = float(getattr(feat, "Length", 30.0))
                step = length / max(1, occurrences - 1)
                self.lines.append(f"\n# Linear pattern")
                self.lines.append(f"{model_var} = {model_var}.linear_array(count={occurrences}, step=({format_num(step)}, 0.0, 0.0))")
                if sim_body is not None:
                    try:
                        sim_body = sim_body.linear_array(count=occurrences, step=(step, 0.0, 0.0))
                    except Exception:
                        pass
                i += 1
                continue

            elif feat_type == "PartDesign::PolarPattern":
                occurrences = int(getattr(feat, "Occurrences", 4))
                angle = float(getattr(feat, "Angle", 360.0))
                self.lines.append(f"\n# Polar pattern")
                self.lines.append(f"{model_var} = {model_var}.polar_array(count={occurrences}, total_angle={format_num(angle)})")
                if sim_body is not None:
                    try:
                        sim_body = sim_body.polar_array(count=occurrences, total_angle=angle)
                    except Exception:
                        pass
                i += 1
                continue

            # Fallback for unrecognized features
            self.decompile_object(feat)
            i += 1

        return model_var

    def decompile_object(self, obj) -> str:
        """
        Recursively decompiles a FreeCAD object and its dependencies,
        returning the variable name assigned to the object.
        """
        if obj is None:
            return ""

        if isinstance(obj, (tuple, list)):
            if not obj:
                return ""
            obj = obj[0]
            if obj is None:
                return ""

        obj_name = getattr(obj, "Name", "")
        if obj_name in self.visited:
            return self.name_map.get(obj_name, "")

        type_id = getattr(obj, "TypeId", "")

        # 0. Intercept PartDesign::Body or features belonging to a PartDesign::Body
        if type_id == "PartDesign::Body":
            return self.decompile_partdesign_body(obj)

        if hasattr(obj, "InList"):
            parent_body = None
            for p in obj.InList:
                if getattr(p, "TypeId", "") == "PartDesign::Body":
                    parent_body = p
                    break
            if parent_body is not None and type_id not in (
                "Sketcher::SketchObject", "App::Origin", "App::Line", "App::Plane", "App::Point"
            ):
                return self.decompile_partdesign_body(parent_body)

        self.visited.add(obj_name)
        var_name = self.get_var_name(obj)
        transforms = self.extract_placement_calls(obj)

        # ---------------------------------------------------------------------
        # 1. Part Primitives
        # ---------------------------------------------------------------------
        if type_id == "Part::Box":
            length = self.extract_param_or_val(obj, "Length", 10.0)
            width = self.extract_param_or_val(obj, "Width", 10.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            if length == width == height:
                self.lines.append(f"{var_name} = Cube(size={length}){transforms}")
            else:
                self.lines.append(f"{var_name} = Box(length={length}, width={width}, height={height}){transforms}")
            return var_name

        elif type_id == "Part::Cylinder":
            radius = self.extract_param_or_val(obj, "Radius", 5.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            self.lines.append(f"{var_name} = Cylinder(radius={radius}, height={height}){transforms}")
            return var_name

        elif type_id == "Part::Sphere":
            radius = self.extract_param_or_val(obj, "Radius", 5.0)
            self.lines.append(f"{var_name} = Sphere(radius={radius}){transforms}")
            return var_name

        elif type_id == "Part::Cone":
            r1 = self.extract_param_or_val(obj, "Radius1", 5.0)
            r2 = self.extract_param_or_val(obj, "Radius2", 0.0)
            height = self.extract_param_or_val(obj, "Height", 10.0)
            self.lines.append(f"{var_name} = Cone(r1={r1}, r2={r2}, height={height}){transforms}")
            return var_name

        elif type_id == "Part::Torus":
            r1 = self.extract_param_or_val(obj, "Radius1", 10.0)
            r2 = self.extract_param_or_val(obj, "Radius2", 2.0)
            self.lines.append(f"{var_name} = Torus(r1={r1}, r2={r2}){transforms}")
            return var_name

        elif type_id == "Part::Plane":
            length = self.extract_param_or_val(obj, "Length", 10.0)
            width = self.extract_param_or_val(obj, "Width", 10.0)
            self.lines.append(f"{var_name} = Plane(length={length}, width={width}){transforms}")
            return var_name

        elif type_id == "Part::Circle":
            radius = self.extract_param_or_val(obj, "Radius", 5.0)
            self.lines.append(f"{var_name} = Circle(radius={radius}){transforms}")
            return var_name

        # ---------------------------------------------------------------------
        # 2. CSG Booleans
        # ---------------------------------------------------------------------
        elif type_id == "Part::Cut":
            base_var = self.decompile_object(getattr(obj, "Base", None))
            tool_var = self.decompile_object(getattr(obj, "Tool", None))
            self.lines.append(f"{var_name} = {base_var} - {tool_var}{transforms}")
            return var_name

        elif type_id in ("Part::Fuse", "Part::MultiFuse"):
            children = getattr(obj, "Shapes", None) or [getattr(obj, "Base", None), getattr(obj, "Tool", None)]
            child_vars = [self.decompile_object(c) for c in children if c is not None]
            if len(child_vars) == 1:
                self.lines.append(f"{var_name} = {child_vars[0]}{transforms}")
            else:
                expr = " + ".join(child_vars)
                self.lines.append(f"{var_name} = {expr}{transforms}")
            return var_name

        elif type_id in ("Part::Common", "Part::MultiCommon"):
            children = getattr(obj, "Shapes", None) or [getattr(obj, "Base", None), getattr(obj, "Tool", None)]
            child_vars = [self.decompile_object(c) for c in children if c is not None]
            if len(child_vars) == 1:
                self.lines.append(f"{var_name} = {child_vars[0]}{transforms}")
            else:
                expr = " & ".join(child_vars)
                self.lines.append(f"{var_name} = {expr}{transforms}")
            return var_name

        # ---------------------------------------------------------------------
        # 3. Fillets, Chamfers & Shells
        # ---------------------------------------------------------------------
        elif type_id in ("Part::Fillet", "PartDesign::Fillet"):
            base_feat = getattr(obj, "BaseFeature", None)
            if not base_feat:
                base_prop = getattr(obj, "Base", None)
                if isinstance(base_prop, (tuple, list)) and base_prop:
                    base_feat = base_prop[0]
                else:
                    base_feat = base_prop

            base_var = self.decompile_object(base_feat)

            # Extract radius
            rad_str = "1.0"
            edges_prop = getattr(obj, "Edges", [])
            if hasattr(obj, "Radius"):
                rad_str = self.extract_param_or_val(obj, "Radius", 1.0)
            elif edges_prop:
                for item in edges_prop:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        rad_str = format_num(float(item[1]))
                        break

            # Extract edge indices
            edge_indices = []
            if edges_prop:
                for item in edges_prop:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        edge_indices.append(item[0] - 1)
            base_tuple = getattr(obj, "Base", None)
            if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
                for sub in base_tuple[1]:
                    if isinstance(sub, str) and "Edge" in sub:
                        num_part = re.findall(r"\d+", sub)
                        if num_part:
                            edge_indices.append(int(num_part[0]) - 1)

            base_shape = getattr(base_feat, "Shape", None)
            total_edges = len(base_shape.Edges) if base_shape and hasattr(base_shape, "Edges") else 0
            if not edge_indices or (total_edges > 0 and len(edge_indices) >= total_edges):
                self.lines.append(f"{var_name} = {base_var}.fillet(radius={rad_str}){transforms}")
            else:
                self.lines.append(f"{var_name} = {base_var}.fillet(radius={rad_str}, edge_indices={edge_indices}){transforms}")
            return var_name

        elif type_id in ("Part::Chamfer", "PartDesign::Chamfer"):
            base_feat = getattr(obj, "BaseFeature", None)
            if not base_feat:
                base_prop = getattr(obj, "Base", None)
                if isinstance(base_prop, (tuple, list)) and base_prop:
                    base_feat = base_prop[0]
                else:
                    base_feat = base_prop

            base_var = self.decompile_object(base_feat)

            dist_str = "1.0"
            edges_prop = getattr(obj, "Edges", [])
            if hasattr(obj, "Size"):
                dist_str = self.extract_param_or_val(obj, "Size", 1.0)
            elif hasattr(obj, "ChamferSize"):
                dist_str = self.extract_param_or_val(obj, "ChamferSize", 1.0)
            elif edges_prop:
                for item in edges_prop:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        dist_str = format_num(float(item[1]))
                        break

            edge_indices = []
            edges_prop = getattr(obj, "Edges", [])
            if edges_prop:
                for item in edges_prop:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        edge_indices.append(item[0] - 1)
            base_tuple = getattr(obj, "Base", None)
            if isinstance(base_tuple, (tuple, list)) and len(base_tuple) >= 2:
                for sub in base_tuple[1]:
                    if isinstance(sub, str) and "Edge" in sub:
                        num_part = re.findall(r"\d+", sub)
                        if num_part:
                            edge_indices.append(int(num_part[0]) - 1)

            base_shape = getattr(base_feat, "Shape", None)
            total_edges = len(base_shape.Edges) if base_shape and hasattr(base_shape, "Edges") else 0
            if not edge_indices or (total_edges > 0 and len(edge_indices) >= total_edges):
                self.lines.append(f"{var_name} = {base_var}.chamfer(distance={dist_str}){transforms}")
            else:
                self.lines.append(f"{var_name} = {base_var}.chamfer(distance={dist_str}, edge_indices={edge_indices}){transforms}")
            return var_name

        elif type_id in ("Part::Thickness", "Part::Offset"):
            base_var = self.decompile_object(getattr(obj, "Base", None))
            val = abs(float(getattr(obj, "Value", 1.5)))
            self.lines.append(f"{var_name} = {base_var}.shell(thickness={format_num(val)}){transforms}")
            return var_name

        elif type_id == "Part::Extrusion":
            base_var = self.decompile_object(getattr(obj, "Base", None))
            length = self.extract_param_or_val(obj, "LengthFwd", 10.0)
            self.lines.append(f"{var_name} = {base_var}.extrude(distance={length}){transforms}")
            return var_name

        elif type_id == "Part::Revolution":
            base_var = self.decompile_object(getattr(obj, "Base", None))
            angle = self.extract_param_or_val(obj, "Angle", 360.0)
            self.lines.append(f"{var_name} = {base_var}.revolve(angle={angle}){transforms}")
            return var_name

        # ---------------------------------------------------------------------
        # 4. PartDesign Features
        # ---------------------------------------------------------------------
        elif type_id == "PartDesign::Body":
            # Decompile features inside the body
            tip = getattr(obj, "Tip", None)
            if tip:
                return self.decompile_object(tip)
            elif hasattr(obj, "BaseFeature") and obj.BaseFeature:
                return self.decompile_object(obj.BaseFeature)

            group = getattr(obj, "Group", [])
            if group:
                last_var = ""
                for child in group:
                    if getattr(child, "TypeId", "") not in ("Sketcher::SketchObject", "App::Origin", "App::Line", "App::Plane", "App::Point"):
                        last_var = self.decompile_object(child)
                return last_var
            else:
                self.lines.append(f"{var_name} = Cube(10.0)")
                return var_name

        elif type_id == "PartDesign::Pad":
            profile = getattr(obj, "Profile", None)
            if isinstance(profile, (tuple, list)) and profile:
                profile = profile[0]
            prof_var = self.decompile_object(profile)
            length_str = self.extract_param_or_val(obj, "Length", 10.0)
            if getattr(obj, "Reversed", False):
                length_str = f"-{length_str}"

            base_feat = getattr(obj, "BaseFeature", None)
            if not base_feat and hasattr(obj, "Base") and isinstance(obj.Base, (tuple, list)) and obj.Base:
                base_feat = obj.Base[0]

            if base_feat:
                base_var = self.decompile_object(base_feat)
                tool_var = f"{var_name}_tool"
                self.lines.append(f"{tool_var} = {prof_var}.extrude(distance={length_str}){transforms}")
                self.lines.append(f"{var_name} = {base_var} + {tool_var}")
            else:
                self.lines.append(f"{var_name} = {prof_var}.extrude(distance={length_str}){transforms}")
            return var_name

        elif type_id == "PartDesign::Pocket":
            profile = getattr(obj, "Profile", None)
            if isinstance(profile, (tuple, list)) and profile:
                profile = profile[0]
            prof_var = self.decompile_object(profile)
            length_str = self.extract_param_or_val(obj, "Length", 10.0)

            tool_var = f"{var_name}_tool"
            self.lines.append(f"{tool_var} = {prof_var}.extrude(distance={length_str}){transforms}")

            base_feat = getattr(obj, "BaseFeature", None)
            if not base_feat and hasattr(obj, "Base") and isinstance(obj.Base, (tuple, list)) and obj.Base:
                base_feat = obj.Base[0]

            if not base_feat and hasattr(obj, "InList"):
                for parent in obj.InList:
                    if getattr(parent, "TypeId", "") == "PartDesign::Body":
                        idx = parent.Group.index(obj) if obj in parent.Group else -1
                        if idx > 0:
                            for prev in reversed(parent.Group[:idx]):
                                if getattr(prev, "TypeId", "") not in ("Sketcher::SketchObject", "App::Origin", "App::Line", "App::Plane", "App::Point"):
                                    base_feat = prev
                                    break

            if base_feat:
                base_var = self.decompile_object(base_feat)
                self.lines.append(f"{var_name} = {base_var} - {tool_var}")
            else:
                self.lines.append(f"{var_name} = {tool_var}")
            return var_name

        elif type_id == "PartDesign::Hole":
            diameter = float(getattr(getattr(obj, "Diameter", None), "Value", getattr(obj, "Diameter", 6.0)))
            radius = diameter / 2.0
            depth = float(getattr(getattr(obj, "Depth", None), "Value", getattr(obj, "Depth", 10.0)))
            tool_var = f"{var_name}_tool"
            self.lines.append(f"{tool_var} = Cylinder(radius={format_num(radius)}, height={format_num(depth)}){transforms}")

            base_feat = getattr(obj, "BaseFeature", None)
            if not base_feat and hasattr(obj, "Base") and isinstance(obj.Base, (tuple, list)) and obj.Base:
                base_feat = obj.Base[0]

            if base_feat:
                base_var = self.decompile_object(base_feat)
                self.lines.append(f"{var_name} = {base_var} - {tool_var}")
            else:
                self.lines.append(f"{var_name} = {tool_var}")
            return var_name

        elif type_id == "PartDesign::LinearPattern":
            feat = getattr(obj, "Originals", [getattr(obj, "Feature", None)])[0]
            feat_var = self.decompile_object(feat)
            occurrences = int(getattr(obj, "Occurrences", 3))
            length = float(getattr(obj, "Length", 30.0))
            step = length / max(1, occurrences - 1)
            self.lines.append(f"{var_name} = {feat_var}.linear_array(count={occurrences}, step=({format_num(step)}, 0.0, 0.0)){transforms}")
            return var_name

        elif type_id == "PartDesign::PolarPattern":
            feat = getattr(obj, "Originals", [getattr(obj, "Feature", None)])[0]
            feat_var = self.decompile_object(feat)
            occurrences = int(getattr(obj, "Occurrences", 4))
            angle = float(getattr(obj, "Angle", 360.0))
            self.lines.append(f"{var_name} = {feat_var}.polar_array(count={occurrences}, total_angle={format_num(angle)}){transforms}")
            return var_name

        # ---------------------------------------------------------------------
        # 5. Sketcher Objects
        # ---------------------------------------------------------------------
        elif type_id == "Sketcher::SketchObject":
            sketch_var, sketch_line = self.decompile_sketch(obj)
            self.lines.append(f"{sketch_line}{transforms}")
            return sketch_var

        # ---------------------------------------------------------------------
        # 6. Fallback & Prismatic Detection for Dumb / Generic Shapes
        # ---------------------------------------------------------------------
        prismatic = self.detect_prismatic_solid(obj)
        if prismatic is not None:
            p_var, p_line = prismatic
            self.lines.append(f"{p_line}{transforms}")
            return p_var

        # Fallback raw Brep info
        vol = round_val(getattr(getattr(obj, "Shape", None), "Volume", 0.0), 2)
        self.lines.append(f"# [Unrecognized CAD Object: {obj.Label} ({type_id}), Volume: {vol}]")
        self.lines.append(f"{var_name} = Box(10.0, 10.0, 10.0)  # Placeholder for {obj.Label}")
        return var_name

    def generate_script(self, target_obj_or_list=None, whole_model: bool = False) -> str:
        """
        Decompiles the provided object(s) or document root objects,
        generating complete, formatted, executable Python code.
        """
        self.visited.clear()
        self.name_map.clear()
        self.used_var_names.clear()
        self.lines.clear()
        self.params.clear()

        # Determine target objects
        targets = []
        is_whole_model = bool(whole_model)

        if whole_model:
            if self.doc:
                targets = get_document_models(self.doc)
        elif target_obj_or_list is None:
            # Try GUI selection first
            if Gui is not None:
                try:
                    sel = list(Gui.Selection.getSelection())
                    if sel:
                        targets = sel
                except Exception:
                    pass

            # If no selection, automatically find all top-level models in the document
            if not targets and self.doc:
                targets = get_document_models(self.doc)
                is_whole_model = True
        elif isinstance(target_obj_or_list, (list, tuple)):
            targets = [t for t in target_obj_or_list if t is not None]
            if not targets and self.doc:
                targets = get_document_models(self.doc)
                is_whole_model = True
        else:
            targets = [target_obj_or_list]

        if self.doc and not is_whole_model and targets:
            all_doc_models = get_document_models(self.doc)
            if all_doc_models and set(t.Name for t in targets) == set(m.Name for m in all_doc_models):
                is_whole_model = True

        if not targets:
            return "# No active 3D model found in the document to decompile."

        final_vars = []
        for t in targets:
            res_var = self.decompile_object(t)
            if res_var:
                final_vars.append((t, res_var))

        # Assemble full script
        out = []
        if self.include_header:
            out.append('"""')
            scope_desc = "entire 3D model" if is_whole_model else "3D model"
            model_titles = ", ".join(getattr(t, 'Label', t.Name) for t, _ in final_vars) or "Model"
            out.append(f"Procedural CAD Model: {model_titles}")
            out.append(f"Generated from {scope_desc}.")
            out.append('"""\n')
            out.append("from scriptcad import *")
            out.append("")

        # Insert extracted parametric variables if any
        if self.params:
            out.append("# Parameters")
            for p_name, p_val in sorted(self.params.items()):
                out.append(f"{p_name} = {p_val}")
            out.append("")

        out.extend(self.lines)
        out.append("")

        # Final show() call
        for t, v_name in final_vars:
            label = getattr(t, "Label", "Model")
            out.append(f'{v_name}.show("{label}")')

        return "\n".join(out)


def get_document_models(doc=None) -> List[Any]:
    """
    Find all top-level root 3D models in a FreeCAD document.
    Returns:
    - All PartDesign::Body containers that have geometry.
    - All standalone Part / CSG features that are not consumed as children by other shapes.
    - Any App::Part child models.
    """
    if doc is None:
        doc = App.ActiveDocument if App else None
    if doc is None or not hasattr(doc, "Objects") or not doc.Objects:
        return []

    models = []
    seen = set()
    body_feature_names = set()

    # 1. PartDesign Bodies
    for o in doc.Objects:
        if getattr(o, "TypeId", "") == "PartDesign::Body":
            if getattr(o, "Tip", None) or getattr(o, "Group", None) or hasattr(o, "Shape"):
                if o.Name not in seen:
                    seen.add(o.Name)
                    models.append(o)
            for feat in getattr(o, "Group", []):
                body_feature_names.add(getattr(feat, "Name", ""))

    # 2. Standalone Part features and solids not consumed by other shapes
    for o in doc.Objects:
        if o.Name in seen or o.Name in body_feature_names:
            continue
        type_id = getattr(o, "TypeId", "")
        # Ignore non-geometric construction elements and top-level container compounds
        if type_id in ("App::Origin", "App::Line", "App::Plane", "App::Point",
                       "Sketcher::SketchObject", "Spreadsheet::Sheet",
                       "App::DocumentObjectGroup", "App::Annotation", "App::Part"):
            continue

        if hasattr(o, "Shape") and o.Shape is not None and o.Shape.isValid():
            # Check if this shape is an input/child to another shape feature or body
            shape_consumers = [
                p for p in getattr(o, "InList", [])
                if (hasattr(p, "Shape") or getattr(p, "TypeId", "") == "PartDesign::Body")
                and getattr(p, "TypeId", "") not in ("App::DocumentObjectGroup", "App::Part")
            ]
            if not shape_consumers:
                seen.add(o.Name)
                models.append(o)

    # 3. Fallback: scan any object with a valid Shape if no models found
    if not models:
        for o in reversed(doc.Objects):
            if hasattr(o, "Shape") and o.Shape and o.Shape.isValid():
                models.append(o)
                break

    return models


def decompile(obj_or_list=None, doc=None, whole_model: bool = False) -> str:
    """
    Decompile a FreeCAD model object, selection, or document into ScriptCAD code.
    If obj_or_list is None (or empty list) or whole_model is True, automatically
    decompiles the entire model.
    """
    decompiler = ModelDecompiler(doc=doc)
    return decompiler.generate_script(obj_or_list, whole_model=whole_model)
