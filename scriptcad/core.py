"""
ScriptCAD Core Engine: Fluent ShapeWrapper with procedural ergonomics,
transform chaining, and operator-overloaded CSG booleans for FreeCAD.
"""

import math
from typing import Union, Tuple, List, Optional

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

# Global flag to control automatic PartDesign Body generation
_DEFAULT_AS_BODY = True


def set_partdesign_mode(enabled: bool = True):
    """Enable or disable automatic wrapping of solids into PartDesign Bodies."""
    global _DEFAULT_AS_BODY
    _DEFAULT_AS_BODY = bool(enabled)


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
    - Fluent method chaining: `box.rotate_z(45).at(10, 0, 5).fillet(1.0)`
    - Blender-style quick display: `shape.show("MyObject")`
    """

    def __init__(self, shape=None):
        if isinstance(shape, ShapeWrapper):
            self._shape = shape.shape.copy()
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
        return self._shape.Volume if self._shape else 0.0

    @property
    def area(self) -> float:
        return self._shape.Area if self._shape else 0.0

    @property
    def bounding_box(self):
        return self._shape.BoundBox if self._shape else None

    @property
    def center_of_mass(self):
        return self._shape.CenterOfMass if self._shape else None

    # --- CSG Operator Overloading (Blender Art Style) ---

    def __sub__(self, other: Union["ShapeWrapper", any]) -> "ShapeWrapper":
        """Boolean Difference / Cut: `body - tool`"""
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        return ShapeWrapper(self._shape.cut(other_shape))

    def __add__(self, other: Union["ShapeWrapper", any]) -> "ShapeWrapper":
        """Boolean Union / Fuse: `body + tool`"""
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        return ShapeWrapper(self._shape.fuse(other_shape))

    def __and__(self, other: Union["ShapeWrapper", any]) -> "ShapeWrapper":
        """Boolean Intersection / Common: `body & tool`"""
        other_shape = other.shape if isinstance(other, ShapeWrapper) else other
        return ShapeWrapper(self._shape.common(other_shape))

    # --- Fluent Transforms & Placement ---

    def translate(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> "ShapeWrapper":
        """Translate the shape along X, Y, Z axes."""
        if Part is None or App is None:
            return self
        vec = App.Vector(x, y, z)
        copied = self._shape.copy()
        copied.translate(vec)
        return ShapeWrapper(copied)

    def at(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> "ShapeWrapper":
        """Alias for translate(). Sets / moves object to position."""
        return self.translate(x, y, z)

    def rotate(self, axis: Tuple[float, float, float] = (0, 0, 1),
               angle: float = 0.0,
               center: Tuple[float, float, float] = (0, 0, 0)) -> "ShapeWrapper":
        """Rotate the shape around an arbitrary axis by degrees."""
        if Part is None or App is None:
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
        if Part is None or App is None:
            return self
        copied = self._shape.copy()
        base_pt = App.Vector(*center)
        copied.scale(factor, base_pt)
        return ShapeWrapper(copied)

    def mirror(self, plane: str = "XY") -> "ShapeWrapper":
        """
        Mirror shape across 'XY', 'XZ', or 'YZ' plane.
        """
        copied = self._shape.copy()
        norm_map = {
            "XY": (0, 0, 1),
            "XZ": (0, 1, 0),
            "YZ": (1, 0, 0)
        }
        nx, ny, nz = norm_map.get(plane.upper(), (0, 0, 1))
        copied.mirror(App.Vector(0, 0, 0), App.Vector(nx, ny, nz))
        return ShapeWrapper(copied)

    # --- CAD Engineering Operations ---

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
        """
        Chamfer / bevel edges.
        """
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
