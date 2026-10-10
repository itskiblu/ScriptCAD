"""
ScriptCAD High-Level Primitives:
Clean, parametric CAD solid constructors for procedural creation.
"""

from typing import List, Tuple, Optional
import math

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

from .core import ShapeWrapper


def Box(length: float = 10.0,
        width: float = 10.0,
        height: float = 10.0,
        center: bool = False) -> ShapeWrapper:
    """
    Construct a rectangular 3D Box.
    If center=True, centers the box at the origin (0, 0, 0) like Blender.
    """
    if Part is None:
        return ShapeWrapper()
    shape = Part.makeBox(length, width, height)
    wrapper = ShapeWrapper(shape)
    if center:
        wrapper = wrapper.translate(-length / 2.0, -width / 2.0, -height / 2.0)
    return wrapper


def Cube(size: float = 10.0, center: bool = False) -> ShapeWrapper:
    """Shortcut for Box(size, size, size, center=center)."""
    return Box(size, size, size, center=center)


def Cylinder(radius: float = 5.0,
             height: float = 10.0,
             r: Optional[float] = None,
             h: Optional[float] = None,
             center: bool = False) -> ShapeWrapper:
    """
    Construct a Cylinder.
    Supports radius or r, height or h.
    If center=True, centers along the Z axis.
    """
    if Part is None:
        return ShapeWrapper()
    rad = r if r is not None else radius
    hgt = h if h is not None else height
    shape = Part.makeCylinder(rad, hgt)
    wrapper = ShapeWrapper(shape)
    if center:
        wrapper = wrapper.translate(0, 0, -hgt / 2.0)
    return wrapper


def Sphere(radius: float = 5.0, r: Optional[float] = None) -> ShapeWrapper:
    """Construct a solid Sphere centered at (0, 0, 0)."""
    if Part is None:
        return ShapeWrapper()
    rad = r if r is not None else radius
    shape = Part.makeSphere(rad)
    return ShapeWrapper(shape)


def Cone(radius1: float = 5.0,
         radius2: float = 0.0,
         height: float = 10.0,
         center: bool = False) -> ShapeWrapper:
    """Construct a Cone or truncated cone."""
    if Part is None:
        return ShapeWrapper()
    shape = Part.makeCone(radius1, radius2, height)
    wrapper = ShapeWrapper(shape)
    if center:
        wrapper = wrapper.translate(0, 0, -height / 2.0)
    return wrapper


def Torus(radius1: float = 10.0,
          radius2: float = 2.0) -> ShapeWrapper:
    """
    Construct a Torus (donut).
    radius1: Major radius (distance from center of tube to center of torus).
    radius2: Minor radius (radius of the tube).
    """
    if Part is None:
        return ShapeWrapper()
    shape = Part.makeTorus(radius1, radius2)
    return ShapeWrapper(shape)


def Plane(length: float = 10.0,
          width: float = 10.0,
          center: bool = False) -> ShapeWrapper:
    """Construct a 2D planar rectangular Face on the XY plane."""
    if Part is None:
        return ShapeWrapper()
    shape = Part.makePlane(length, width)
    wrapper = ShapeWrapper(shape)
    if center:
        wrapper = wrapper.translate(-length / 2.0, -width / 2.0, 0)
    return wrapper


def Circle(radius: float = 5.0, filled: bool = True) -> ShapeWrapper:
    """Construct a 2D Circle wire or filled face on XY plane."""
    if Part is None:
        return ShapeWrapper()
    circ = Part.makeCircle(radius)
    if filled:
        face = Part.Face(Part.Wire(circ))
        return ShapeWrapper(face)
    return ShapeWrapper(circ)


def Polygon(points: List[Tuple[float, float, float]], filled: bool = True) -> ShapeWrapper:
    """
    Construct a planar polygon from a sequence of (x, y, z) points.
    Automatically closes the polygon.
    """
    if Part is None or len(points) < 3:
        return ShapeWrapper()
    vectors = [App.Vector(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in points]
    if vectors[0] != vectors[-1]:
        vectors.append(vectors[0])
    polygon_wire = Part.makePolygon(vectors)
    if filled:
        try:
            face = Part.Face(polygon_wire)
            return ShapeWrapper(face)
        except Exception:
            pass
    return ShapeWrapper(polygon_wire)


def Loft(profiles: List[ShapeWrapper], solid: bool = True, ruled: bool = False) -> ShapeWrapper:
    """
    Loft through a list of wire or face profiles to create organic / aerodynamic solids.
    """
    if Part is None or len(profiles) < 2:
        return ShapeWrapper()
    wires = []
    for p in profiles:
        s = p.shape
        if hasattr(s, "Wires") and s.Wires:
            wires.append(s.Wires[0])
        elif s.ShapeType == "Wire":
            wires.append(s)
        else:
            wires.append(Part.Wire(s.Edges))
    loft_shape = Part.makeLoft(wires, solid, ruled)
    return ShapeWrapper(loft_shape)


def Extrude(profile: ShapeWrapper,
            distance: float = 10.0,
            direction: Tuple[float, float, float] = (0, 0, 1)) -> ShapeWrapper:
    """
    Extrude a 2D wire or face along a direction vector.
    """
    if Part is None:
        return ShapeWrapper()
    dir_vec = App.Vector(*direction).normalize() * distance
    extruded = profile.shape.extrude(dir_vec)
    return ShapeWrapper(extruded)


def Revolve(profile: ShapeWrapper,
            axis: Tuple[float, float, float] = (0, 0, 1),
            angle: float = 360.0,
            center: Tuple[float, float, float] = (0, 0, 0)) -> ShapeWrapper:
    """
    Revolve a 2D wire or face around an axis.
    """
    if Part is None:
        return ShapeWrapper()
    base_pt = App.Vector(*center)
    dir_vec = App.Vector(*axis)
    revolved = profile.shape.revolve(base_pt, dir_vec, angle)
    return ShapeWrapper(revolved)
