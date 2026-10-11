# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Core Engine: Fluent ShapeWrapper with procedural ergonomics,
transform chaining, operator-overloaded CSG booleans, shelling, arrays,
and direct multi-format export/import for FreeCAD.
"""

import math
import os
from typing import Union, Tuple, List, Optional, Any, Callable

try:
    import FreeCAD as App
    import Part
    import Mesh
except ImportError:
    App = None
    Part = None
    Mesh = None

# Global flag to control automatic PartDesign Body generation
_DEFAULT_AS_BODY = True


def set_partdesign_mode(enabled: bool = True):
    """Enable or disable automatic wrapping of solids into PartDesign Bodies."""
    global _DEFAULT_AS_BODY
    _DEFAULT_AS_BODY = enabled


def convert_to_body(obj_or_name=None, doc=None):
    """
    Convert an existing Part::Feature in the document to an active PartDesign::Body.
    If obj_or_name is omitted, converts the current FreeCAD selection or latest object.
    """
    if App is None:
        return None
    if doc is None:
        doc = App.ActiveDocument
    if doc is None:
        return None

    target_obj = None
    if obj_or_name is None:
        try:
            import FreeCADGui as Gui
            sel = Gui.Selection.getSelection()
            if sel:
                target_obj = sel[0]
        except Exception:
            pass

        if target_obj is None and doc.Objects:
            for o in reversed(doc.Objects):
                if getattr(o, "TypeId", "") == "Part::Feature":
                    target_obj = o
                    break
    elif isinstance(obj_or_name, str):
        target_obj = doc.getObject(obj_or_name)
    else:
        target_obj = obj_or_name

    if target_obj is None or not hasattr(target_obj, "Shape"):
        return None

    body_name = f"{target_obj.Name}_Body"
    body = doc.getObject(body_name) or doc.addObject("PartDesign::Body", body_name)
    body.BaseFeature = target_obj
    target_obj.Visibility = False
    doc.recompute()

    _activate_body_in_gui(body)
    return body


def _activate_body_in_gui(body):
    """Set the given PartDesign::Body as the active body in FreeCAD GUI."""
    try:
        import FreeCADGui as Gui
        if Gui.runMode() == "Cmd":
            return

        # 1. Direct C++ PartDesign activation
        try:
            import PartDesignGui
            if hasattr(PartDesignGui, "setActiveBody"):
                PartDesignGui.setActiveBody(body)
        except Exception:
            pass

        # 2. View 3D active object activation
        active_view = None
        if hasattr(Gui, "activeView") and callable(Gui.activeView):
            active_view = Gui.activeView()
        elif hasattr(Gui, "ActiveDocument") and Gui.ActiveDocument and hasattr(Gui.ActiveDocument, "ActiveView"):
            active_view = Gui.ActiveDocument.ActiveView

        if active_view and hasattr(active_view, "setActiveObject"):
            active_view.setActiveObject("pdbody", body)

        if hasattr(Gui, "Selection"):
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(body)
    except Exception:
        pass


class ShapeWrapper:
    """
    Wraps an OpenCASCADE Part.Shape to provide:
    - Operator overloading: `a - b` (Cut), `a + b` (Union), `a & b` (Intersection)
    - Fluent method chaining: `box.rotate_z(45).at(10, 0, 5).fillet(1.0).shell(2.0)`
    - Array modifiers: `.linear_array()`, `.polar_array()`
    - Export helpers: `.export_stl()`, `.export_step()`, `.export_obj()`
    - Blender-style quick display: `shape.show("MyObject")`
    """

    def __init__(self, shape: Any = None):
        if isinstance(shape, ShapeWrapper):
            self._shape = shape.shape.copy() if shape.shape is not None else None
        elif shape is not None:
            self._shape = shape
        else:
            if Part is not None:
                self._shape = Part.Shape()
            else:
                self._shape = None
        self._name = None
        self._color = None
        self._transparency = 0

    @property
    def shape(self):
        """The underlying FreeCAD Part.Shape."""
        return self._shape

    @property
    def volume(self) -> float:
        try:
            return self._shape.Volume if (self._shape and self._shape.isValid()) else 0.0
        except Exception:
            return 0.0

    @property
    def area(self) -> float:
        try:
            return self._shape.Area if (self._shape and self._shape.isValid()) else 0.0
        except Exception:
            return 0.0

    @property
    def bounding_box(self):
        try:
            return self._shape.BoundBox if self._shape else None
        except Exception:
            return None

    @property
    def center_of_mass(self):
        try:
            return self._shape.CenterOfMass if (self._shape and self._shape.isValid()) else None
        except Exception:
            return None

    @property
    def is_valid(self) -> bool:
        try:
            return self._shape.isValid() if self._shape else False
        except Exception:
            return False

    # --- CSG Operator Overloading (Blender Art Style) ---

    def __sub__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """Boolean Difference / Cut: `body - tool`"""
        if self._shape is None:
            return self
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        if other_shape is None:
            return self
        cut_shape = self._shape.cut(other_shape)
        try:
            cut_shape = cut_shape.removeSplitter()
        except Exception:
            pass
        return ShapeWrapper(cut_shape)

    def __add__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """Boolean Union / Fuse: `body + tool`"""
        if self._shape is None:
            return other if isinstance(other, ShapeWrapper) else ShapeWrapper(other)
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        if other_shape is None:
            return self
        fused = self._shape.fuse(other_shape)
        try:
            fused = fused.removeSplitter()
        except Exception:
            pass
        return ShapeWrapper(fused)

    def __and__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """Boolean Intersection / Common: `body & tool`"""
        if self._shape is None:
            return self
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        if other_shape is None:
            return self
        return ShapeWrapper(self._shape.common(other_shape))

    def __isub__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """In-place Boolean Cut: `body -= tool`"""
        return self.__sub__(other)

    def __iadd__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """In-place Boolean Union: `body += tool`"""
        return self.__add__(other)

    def __iand__(self, other: Union["ShapeWrapper", Any]) -> "ShapeWrapper":
        """In-place Boolean Intersection: `body &= tool`"""
        return self.__and__(other)

    # --- Fluent Transforms & Placement ---

    def translate(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> "ShapeWrapper":
        """Translate the shape along X, Y, Z axes."""
        if Part is None or App is None or self._shape is None:
            return self
        vec = App.Vector(x, y, z)
        copied = self._shape.copy()
        copied.translate(vec)
        return ShapeWrapper(copied)

    def at(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> "ShapeWrapper":
        """Alias for translate(). Moves shape to specified translation offset."""
        return self.translate(x, y, z)

    def rotate(self, axis: Tuple[float, float, float] = (0, 0, 1),
               angle: float = 0.0,
               center: Tuple[float, float, float] = (0, 0, 0)) -> "ShapeWrapper":
        """Rotate the shape around an arbitrary axis by degrees."""
        if Part is None or App is None or self._shape is None:
            return self
        base_pt = App.Vector(*center)
        rot_axis = App.Vector(*axis)
        copied = self._shape.copy()
        copied.rotate(base_pt, rot_axis, angle)
        return ShapeWrapper(copied)

    def rotate_x(self, angle_deg: float) -> "ShapeWrapper":
        """Rotate around X axis by angle in degrees."""
        return self.rotate(axis=(1, 0, 0), angle=angle_deg)

    def rotate_y(self, angle_deg: float) -> "ShapeWrapper":
        """Rotate around Y axis by angle in degrees."""
        return self.rotate(axis=(0, 1, 0), angle=angle_deg)

    def rotate_z(self, angle_deg: float) -> "ShapeWrapper":
        """Rotate around Z axis by angle in degrees."""
        return self.rotate(axis=(0, 0, 1), angle=angle_deg)

    def scale(self, factor: float, center: Tuple[float, float, float] = (0, 0, 0)) -> "ShapeWrapper":
        """Uniformly scale the shape."""
        if Part is None or App is None or self._shape is None:
            return self
        copied = self._shape.copy()
        base_pt = App.Vector(*center)
        copied.scale(factor, base_pt)
        return ShapeWrapper(copied)

    def mirror(self, plane: str = "XY") -> "ShapeWrapper":
        """Mirror shape across 'XY', 'XZ', or 'YZ' plane."""
        if Part is None or App is None or self._shape is None:
            return self
        copied = self._shape.copy()
        norm_map = {
            "XY": (0, 0, 1),
            "XZ": (0, 1, 0),
            "YZ": (1, 0, 0)
        }
        nx, ny, nz = norm_map.get(plane.upper(), (0, 0, 1))
        copied.mirror(App.Vector(0, 0, 0), App.Vector(nx, ny, nz))
        return ShapeWrapper(copied)

    def extrude(self, distance: float = 10.0,
                direction: Optional[Tuple[float, float, float]] = None) -> "ShapeWrapper":
        """Extrude a 2D wire or face into a 3D solid along a direction vector or face normal."""
        if Part is None or App is None or self._shape is None:
            return self
        shape = self._shape
        if hasattr(shape, "ShapeType") and shape.ShapeType == "Wire":
            try:
                shape = Part.Face(shape)
            except Exception:
                pass
        elif hasattr(shape, "Wires") and len(getattr(shape, "Faces", [])) == 0 and shape.Wires:
            try:
                shape = Part.Face(shape.Wires[0])
            except Exception:
                pass

        if direction is not None:
            dir_vec = App.Vector(*direction).normalize() * distance
        else:
            if hasattr(shape, "Faces") and shape.Faces:
                try:
                    norm = shape.Faces[0].normalAt(0, 0)
                    dir_vec = norm.normalize() * distance
                except Exception:
                    dir_vec = App.Vector(0, 0, 1) * distance
            else:
                dir_vec = App.Vector(0, 0, 1) * distance

        return ShapeWrapper(shape.extrude(dir_vec))

    def revolve(self, axis: Tuple[float, float, float] = (0, 0, 1),
                angle: float = 360.0,
                center: Tuple[float, float, float] = (0, 0, 0)) -> "ShapeWrapper":
        """Revolve a 2D wire or face around an axis into a 3D solid."""
        if Part is None or App is None or self._shape is None:
            return self
        base_pt = App.Vector(*center)
        dir_vec = App.Vector(*axis)
        return ShapeWrapper(self._shape.revolve(base_pt, dir_vec, angle))

    # --- CAD Engineering Operations ---

    def shell(self,
              thickness: float = 1.5,
              open_faces: Optional[Union[str, List[int], List[Any]]] = "top",
              tolerance: float = 1e-3) -> "ShapeWrapper":
        """
        Hollow out this solid with a uniform wall thickness.
        open_faces:
          - "top" / ">Z": leave the top face open (e.g. cup, enclosure, vase)
          - "bottom" / "<Z": leave bottom open
          - "front" / ">Y", "back" / "<Y", "right" / ">X", "left" / "<X"
          - None / "none": fully enclosed hollow interior
          - List of face index integers or Face objects.
        """
        if self._shape is None or not hasattr(self._shape, "Faces") or not self._shape.Faces:
            return self

        faces_to_open = []
        if isinstance(open_faces, str):
            code = open_faces.lower().strip()
            if code in ("top", ">z"):
                faces_to_open = [max(self._shape.Faces, key=lambda f: f.CenterOfMass.z)]
            elif code in ("bottom", "<z"):
                faces_to_open = [min(self._shape.Faces, key=lambda f: f.CenterOfMass.z)]
            elif code in ("front", ">y"):
                faces_to_open = [max(self._shape.Faces, key=lambda f: f.CenterOfMass.y)]
            elif code in ("back", "<y"):
                faces_to_open = [min(self._shape.Faces, key=lambda f: f.CenterOfMass.y)]
            elif code in ("right", ">x"):
                faces_to_open = [max(self._shape.Faces, key=lambda f: f.CenterOfMass.x)]
            elif code in ("left", "<x"):
                faces_to_open = [min(self._shape.Faces, key=lambda f: f.CenterOfMass.x)]
            elif code in ("none", "closed"):
                faces_to_open = []
        elif isinstance(open_faces, list):
            for item in open_faces:
                if isinstance(item, int) and 0 <= item < len(self._shape.Faces):
                    faces_to_open.append(self._shape.Faces[item])
                elif hasattr(item, "ShapeType") and item.ShapeType == "Face":
                    faces_to_open.append(item)

        try:
            # Negative thickness hollows inwards
            offset_val = -abs(thickness)
            shelled = self._shape.makeThickness(faces_to_open, offset_val, tolerance)
            return ShapeWrapper(shelled)
        except Exception as e:
            print(f"[ScriptCAD Warning] Shell operation failed: {e}")
            return self

    def hollow(self, thickness: float = 1.5, open_faces: Optional[Union[str, List[int]]] = "top") -> "ShapeWrapper":
        """Alias for shell(). Hollowing out solid bodies."""
        return self.shell(thickness=thickness, open_faces=open_faces)

    def fillet(self, radius: float, edge_indices: Optional[List[int]] = None) -> "ShapeWrapper":
        """
        Fillet / round edges.
        If edge_indices is None, rounds all edges.
        """
        if self._shape is None or not self._shape.Edges:
            return self

        if edge_indices is None:
            target_edges = self._shape.Edges
        else:
            target_edges = [self._shape.Edges[i] for i in edge_indices if i < len(self._shape.Edges)]

        try:
            res = self._shape.makeFillet(radius, target_edges)
            return ShapeWrapper(res)
        except Exception as e:
            print(f"[ScriptCAD Warning] Fillet failed: {e}")
            return self

    def chamfer(self, distance: float, edge_indices: Optional[List[int]] = None) -> "ShapeWrapper":
        """Chamfer / bevel edges."""
        if self._shape is None or not self._shape.Edges:
            return self

        if edge_indices is None:
            target_edges = self._shape.Edges
        else:
            target_edges = [self._shape.Edges[i] for i in edge_indices if i < len(self._shape.Edges)]

        try:
            res = self._shape.makeChamfer(distance, target_edges)
            return ShapeWrapper(res)
        except Exception as e:
            print(f"[ScriptCAD Warning] Chamfer failed: {e}")
            return self

    # --- Array & Pattern Helpers ---

    def linear_array(self,
                     count: int = 3,
                     step: Tuple[float, float, float] = (15.0, 0.0, 0.0),
                     union: bool = True) -> "ShapeWrapper":
        """
        Duplicate the shape linearly along a step vector.
        If union=True, fuses all copies into a single solid.
        """
        if count <= 1 or self._shape is None:
            return self

        copies = [self]
        dx, dy, dz = step
        for i in range(1, count):
            copies.append(self.translate(dx * i, dy * i, dz * i))

        if union:
            result = copies[0]
            for c in copies[1:]:
                result = result + c
            return result
        return copies

    def polar_array(self,
                    count: int = 6,
                    total_angle: float = 360.0,
                    axis: Tuple[float, float, float] = (0, 0, 1),
                    center: Tuple[float, float, float] = (0, 0, 0),
                    union: bool = True) -> "ShapeWrapper":
        """
        Duplicate the shape around an axis (radial pattern).
        If union=True, fuses all copies into a single solid.
        """
        if count <= 1 or self._shape is None:
            return self

        angle_step = float(total_angle) / count
        copies = [self]
        for i in range(1, count):
            copies.append(self.rotate(axis=axis, angle=angle_step * i, center=center))

        if union:
            result = copies[0]
            for c in copies[1:]:
                result = result + c
            return result
        return copies

    # --- Inspection & Feature Filtering ---

    def faces(self, selector: Optional[str] = None) -> List[Any]:
        """Return faces, optionally filtered by direction (e.g. '>Z', '<Z', '>X', '>Y')."""
        if not self._shape or not hasattr(self._shape, "Faces"):
            return []
        f_list = list(self._shape.Faces)
        if not selector:
            return f_list

        sel = selector.upper().strip()
        if sel in (">Z", "TOP"):
            return [max(f_list, key=lambda f: f.CenterOfMass.z)]
        elif sel in ("<Z", "BOTTOM"):
            return [min(f_list, key=lambda f: f.CenterOfMass.z)]
        elif sel in (">X", "RIGHT"):
            return [max(f_list, key=lambda f: f.CenterOfMass.x)]
        elif sel in ("<X", "LEFT"):
            return [min(f_list, key=lambda f: f.CenterOfMass.x)]
        elif sel in (">Y", "FRONT"):
            return [max(f_list, key=lambda f: f.CenterOfMass.y)]
        elif sel in ("<Y", "BACK"):
            return [min(f_list, key=lambda f: f.CenterOfMass.y)]
        return f_list

    def edges(self, selector: Optional[str] = None) -> List[Any]:
        """Return edges, optionally filtered by '|Z' (vertical) or 'CIRCULAR'."""
        if not self._shape or not hasattr(self._shape, "Edges"):
            return []
        e_list = list(self._shape.Edges)
        if not selector:
            return e_list

        sel = selector.upper().strip()
        if sel in ("|Z", "VERTICAL"):
            # Edges whose tangents are along Z
            results = []
            for e in e_list:
                try:
                    bb = e.BoundBox
                    if bb.XLength < 1e-3 and bb.YLength < 1e-3 and bb.ZLength > 1e-3:
                        results.append(e)
                except Exception:
                    pass
            return results
        elif sel in ("CIRCULAR", "CURVED"):
            return [e for e in e_list if hasattr(e, "Curve") and "Circle" in str(type(e.Curve))]
        return e_list

    # --- Direct Export Helpers ---

    def export_step(self, filepath: str) -> bool:
        """Export solid as an ISO standard STEP (.step / .stp) file."""
        if Part is None or self._shape is None:
            return False
        try:
            norm_path = os.path.abspath(filepath).replace("\\", "/")
            os.makedirs(os.path.dirname(norm_path), exist_ok=True)
            if hasattr(self._shape, "exportStep"):
                self._shape.exportStep(norm_path)
            else:
                Part.export([self._shape], norm_path)
            print(f"[ScriptCAD] Successfully exported STEP to: {norm_path}")
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] STEP export failed: {e}")
            return False

    def export_stl(self, filepath: str, deflection: float = 0.05) -> bool:
        """Export solid as 3D printable STL file."""
        if self._shape is None:
            return False
        try:
            import Mesh
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            pts, facets = self._shape.tessellate(deflection)
            m = Mesh.Mesh()
            for f in facets:
                p1, p2, p3 = pts[f[0]], pts[f[1]], pts[f[2]]
                m.addFacet(p1.x, p1.y, p1.z, p2.x, p2.y, p2.z, p3.x, p3.y, p3.z)
            m.write(filepath)
            print(f"[ScriptCAD] Successfully exported STL to: {filepath}")
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] STL export failed: {e}")
            return False

    def export_obj(self, filepath: str, deflection: float = 0.05) -> bool:
        """Export solid as Wavefront OBJ file."""
        if self._shape is None:
            return False
        try:
            import Mesh
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            pts, facets = self._shape.tessellate(deflection)
            m = Mesh.Mesh()
            for f in facets:
                p1, p2, p3 = pts[f[0]], pts[f[1]], pts[f[2]]
                m.addFacet(p1.x, p1.y, p1.z, p2.x, p2.y, p2.z, p3.x, p3.y, p3.z)
            m.write(filepath)
            print(f"[ScriptCAD] Successfully exported OBJ to: {filepath}")
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] OBJ export failed: {e}")
            return False

    def export_brep(self, filepath: str) -> bool:
        """Export native OpenCASCADE BREP file."""
        if self._shape is None:
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            self._shape.exportBrep(filepath)
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] BREP export failed: {e}")
            return False

    # --- Presentation & Display ---

    def color(self, r: float, g: float, b: float, a: float = 1.0) -> "ShapeWrapper":
        """Assign RGBA color tuple (values 0.0 to 1.0)."""
        self._color = (r, g, b)
        self._transparency = int((1.0 - a) * 100)
        return self

    def show(self, name: str = "Object",
             color: Optional[Tuple[float, float, float]] = None,
             transparency: Optional[int] = None,
             doc=None,
             as_body: bool = True):
        """
        Instantiate or update this shape in the active FreeCAD document.
        Defaults to generating an active PartDesign::Body so it can be edited
        directly in both Part Design and Part workbenches.
        """
        if App is None:
            print(f"[ScriptCAD] show({name}) called outside FreeCAD.")
            return None

        if doc is None:
            doc = App.ActiveDocument
            if doc is None:
                doc = App.newDocument("ScriptCAD_Model")

        # 1. PartDesign Body Mode (Default)
        if as_body or _DEFAULT_AS_BODY:
            body = doc.getObject(name)
            if body is not None and getattr(body, "TypeId", "") != "PartDesign::Body":
                body = doc.getObject(f"{name}_Body")

            # Check if there is an empty uninitialized Body in the document to adopt
            if body is None:
                for o in doc.Objects:
                    if getattr(o, "TypeId", "") == "PartDesign::Body":
                        if not getattr(o, "BaseFeature", None) and len(getattr(o, "Group", [])) == 0:
                            body = o
                            body.Label = name
                            break

            # Create clean new PartDesign Body
            if body is None:
                body = doc.addObject("PartDesign::Body", name)

            # Attach or update geometry
            if body.BaseFeature and hasattr(body.BaseFeature, "Shape"):
                body.BaseFeature.Shape = self._shape
            else:
                geom_name = f"{body.Name}_Geometry"
                feat = doc.getObject(geom_name) or doc.addObject("Part::Feature", geom_name)
                feat.Shape = self._shape
                feat.Visibility = False
                body.BaseFeature = feat

            # Appearance
            try:
                import FreeCADGui as Gui
                if Gui.runMode() != "Cmd":
                    col = color or self._color
                    if col and hasattr(body, "ViewObject") and body.ViewObject:
                        body.ViewObject.ShapeColor = col
                    trans = transparency if transparency is not None else self._transparency
                    if trans and hasattr(body, "ViewObject") and body.ViewObject:
                        body.ViewObject.Transparency = trans
            except Exception:
                pass

            doc.recompute()
            _activate_body_in_gui(body)
            return body

        # 2. Raw Part::Feature Mode (when as_body=False explicitly)
        existing = doc.getObject(name)
        if existing and hasattr(existing, "Shape"):
            obj = existing
        else:
            obj = doc.addObject("Part::Feature", name)

        obj.Shape = self._shape

        try:
            import FreeCADGui as Gui
            if Gui.runMode() != "Cmd":
                view_obj = obj.ViewObject
                col = color or self._color
                if col:
                    view_obj.ShapeColor = col
                trans = transparency if transparency is not None else self._transparency
                if trans:
                    view_obj.Transparency = trans
        except Exception:
            pass

        doc.recompute()
        return obj

    def to_body(self, name: str = "ScriptCAD_Body", doc=None):
        """Directly instantiate this solid as an active PartDesign::Body container."""
        return self.show(name=name, doc=doc, as_body=True)

    def __repr__(self):
        vol = round(self.volume, 2)
        return f"<ScriptCAD ShapeWrapper(volume={vol})>"


# --- Functional CSG & Top-Level Utility Functions ---

def union(*shapes: Union[ShapeWrapper, Any]) -> ShapeWrapper:
    """Boolean fuse / union of multiple shapes."""
    if not shapes:
        return ShapeWrapper()
    res = shapes[0] if isinstance(shapes[0], ShapeWrapper) else ShapeWrapper(shapes[0])
    for s in shapes[1:]:
        res = res + s
    return res


def difference(base: Union[ShapeWrapper, Any], *tools: Union[ShapeWrapper, Any]) -> ShapeWrapper:
    """Boolean difference / cut: subtract all tools from base."""
    res = base if isinstance(base, ShapeWrapper) else ShapeWrapper(base)
    for t in tools:
        res = res - t
    return res


def intersection(*shapes: Union[ShapeWrapper, Any]) -> ShapeWrapper:
    """Boolean common / intersection across all given shapes."""
    if not shapes:
        return ShapeWrapper()
    res = shapes[0] if isinstance(shapes[0], ShapeWrapper) else ShapeWrapper(shapes[0])
    for s in shapes[1:]:
        res = res & s
    return res


def import_step(filepath: str) -> ShapeWrapper:
    """Import a STEP file from disk into a ScriptCAD ShapeWrapper."""
    if not os.path.exists(filepath):
        return ShapeWrapper()
    try:
        import Import
        norm_path = os.path.abspath(filepath).replace("\\", "/")
        if len(norm_path) > 1 and norm_path[1] == ":":
            norm_path = norm_path[0].upper() + norm_path[1:]
        if App:
            doc = App.newDocument("ScriptCAD_ImportTemp")
            Import.insert(norm_path, doc.Name)
            doc.recompute()
            shapes = [o.Shape.copy() for o in doc.Objects if hasattr(o, "Shape")]
            doc_name = doc.Name
            App.closeDocument(doc_name)
            if shapes:
                if len(shapes) == 1:
                    return ShapeWrapper(shapes[0])
                else:
                    return union(*[ShapeWrapper(s) for s in shapes])
        return ShapeWrapper()
    except Exception as e:
        print(f"[ScriptCAD Error] Could not import STEP file '{filepath}': {e}")
        return ShapeWrapper()


def import_brep(filepath: str) -> ShapeWrapper:
    """Import an OpenCASCADE BREP file from disk."""
    if Part is None or not os.path.exists(filepath):
        return ShapeWrapper()
    try:
        sh = Part.Shape()
        sh.read(filepath)
        return ShapeWrapper(sh)
    except Exception as e:
        print(f"[ScriptCAD Error] Could not import BREP file '{filepath}': {e}")
        return ShapeWrapper()
