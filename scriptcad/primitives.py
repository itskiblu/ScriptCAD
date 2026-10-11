# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD High-Level Primitives:
Clean, parametric CAD solid constructors, 2D profiles, curves, sweeps,
helices, and 3D text for procedural creation.
"""

from typing import List, Tuple, Optional, Union, Any
import math
import os

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

from .core import ShapeWrapper


# =============================================================================
# 3D Solid Primitives
# =============================================================================

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


def Pipe(outer_r: float = 10.0,
         inner_r: float = 8.0,
         height: float = 20.0,
         r_outer: Optional[float] = None,
         r_inner: Optional[float] = None,
         h: Optional[float] = None,
         center: bool = False) -> ShapeWrapper:
    """
    Construct a hollow cylindrical Pipe / Tube.
    """
    if Part is None:
        return ShapeWrapper()
    ro = r_outer if r_outer is not None else outer_r
    ri = r_inner if r_inner is not None else inner_r
    hgt = h if h is not None else height

    if ri >= ro:
        raise ValueError("Pipe inner radius must be strictly less than outer radius.")

    outer = Cylinder(radius=ro, height=hgt, center=center)
    inner = Cylinder(radius=ri, height=hgt + 2.0, center=center)
    if not center:
        inner = inner.translate(0, 0, -1.0)
    return outer - inner


def Tube(outer_r: float = 10.0, inner_r: float = 8.0, height: float = 20.0, center: bool = False) -> ShapeWrapper:
    """Alias for Pipe."""
    return Pipe(outer_r=outer_r, inner_r=inner_r, height=height, center=center)


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


def Wedge(dx: float = 10.0,
          dy: float = 10.0,
          dz: float = 10.0,
          xmin: float = 0.0,
          zmin: float = 0.0,
          xmax: float = 10.0,
          zmax: float = 10.0) -> ShapeWrapper:
    """Construct a 3D Wedge shape."""
    if Part is None:
        return ShapeWrapper()
    shape = Part.makeWedge(dx, dy, dz, xmin, zmin, xmax, zmax)
    return ShapeWrapper(shape)


# =============================================================================
# 2D Planar Primitives & Curves
# =============================================================================

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


def Rectangle(length: Optional[float] = None,
              width: Optional[float] = None,
              height: Optional[float] = None,
              center: bool = False,
              filled: bool = True) -> ShapeWrapper:
    """Construct a 2D rectangle (wire or filled face). Supports length/width or width/height."""
    if length is None:
        l = width if width is not None else 10.0
        w = height if height is not None else 10.0
    else:
        l = length
        if height is not None and width is None:
            w = height
        else:
            w = width if width is not None else (height if height is not None else 10.0)

    return Plane(length=l, width=w, center=center) if filled else Polygon([
        (-l / 2 if center else 0, -w / 2 if center else 0, 0),
        (l / 2 if center else l, -w / 2 if center else 0, 0),
        (l / 2 if center else l, w / 2 if center else w, 0),
        (-l / 2 if center else 0, w / 2 if center else w, 0)
    ], filled=False)


def Circle(radius: float = 5.0, filled: bool = True) -> ShapeWrapper:
    """Construct a 2D Circle wire or filled face on XY plane."""
    if Part is None:
        return ShapeWrapper()
    circ = Part.makeCircle(radius)
    if filled:
        face = Part.Face(Part.Wire(circ))
        return ShapeWrapper(face)
    return ShapeWrapper(circ)


def Arc(radius: float = 5.0,
        start_angle: float = 0.0,
        end_angle: float = 180.0,
        center: Tuple[float, float, float] = (0, 0, 0)) -> ShapeWrapper:
    """
    Construct a 2D circular arc wire.
    Angles in degrees.
    """
    if Part is None or App is None:
        return ShapeWrapper()
    ctr = App.Vector(*center)
    normal = App.Vector(0, 0, 1)
    arc_edge = Part.makeCircle(radius, ctr, normal, start_angle, end_angle)
    return ShapeWrapper(arc_edge)


def Ellipse(r1: float = 10.0,
            r2: float = 5.0,
            center: bool = True,
            filled: bool = True) -> ShapeWrapper:
    """Construct an ellipse wire or filled face on the XY plane."""
    if Part is None or App is None:
        return ShapeWrapper()
    ctr = App.Vector(0, 0, 0)
    # Part.Ellipse(center, major_radius, minor_radius)
    major_r = max(r1, r2)
    minor_r = min(r1, r2)
    geom_ellipse = Part.Ellipse(ctr, major_r, minor_r)
    edge = geom_ellipse.toShape()
    if r1 < r2:
        # Rotate 90 deg if vertical
        edge.rotate(ctr, App.Vector(0, 0, 1), 90.0)
    if filled:
        face = Part.Face(Part.Wire(edge))
        return ShapeWrapper(face)
    return ShapeWrapper(edge)


def Polygon(points: List[Tuple[float, float, float]], filled: bool = True) -> ShapeWrapper:
    """
    Construct a planar polygon from a sequence of (x, y, z) points.
    Automatically closes the polygon.
    """
    if Part is None or App is None or len(points) < 3:
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


def Spline(points: List[Tuple[float, float, float]],
           closed: bool = False,
           filled: bool = False) -> ShapeWrapper:
    """
    Construct a smooth B-Spline curve interpolated through 3D points.
    """
    if Part is None or App is None or len(points) < 2:
        return ShapeWrapper()
    vectors = [App.Vector(p[0], p[1], p[2] if len(p) > 2 else 0.0) for p in points]
    if closed and vectors[0] != vectors[-1]:
        vectors.append(vectors[0])

    bspline = Part.BSplineCurve()
    bspline.interpolate(vectors)
    edge = bspline.toShape()
    wire = Part.Wire(edge)
    if filled and closed:
        try:
            face = Part.Face(wire)
            return ShapeWrapper(face)
        except Exception:
            pass
    return ShapeWrapper(wire)


def Slot(length: float = 20.0,
         width: float = 8.0,
         thickness: float = 0.0,
         center: bool = True) -> ShapeWrapper:
    """
    Construct a mechanical stadium / racetrack slot.
    If thickness > 0, returns a 3D solid. If thickness == 0, returns a 2D face.
    """
    if length <= width:
        # Falls back to cylinder or circle
        if thickness > 0:
            return Cylinder(radius=width / 2.0, height=thickness, center=center)
        return Circle(radius=width / 2.0, filled=True)

    r = width / 2.0
    dist = length - width

    if thickness > 0:
        c1 = Cylinder(radius=r, height=thickness, center=center).translate(-dist / 2.0, 0, 0)
        c2 = Cylinder(radius=r, height=thickness, center=center).translate(dist / 2.0, 0, 0)
        mid = Box(dist, width, thickness, center=center)
        res = (c1 + c2) + mid
        if not center:
            res = res.translate(length / 2.0, width / 2.0, 0)
        return res
    else:
        # 2D Face Slot
        c1 = Circle(radius=r, filled=True).translate(-dist / 2.0, 0, 0)
        c2 = Circle(radius=r, filled=True).translate(dist / 2.0, 0, 0)
        mid = Plane(length=dist, width=width, center=True)
        res = (c1 + c2) + mid
        if not center:
            res = res.translate(length / 2.0, width / 2.0, 0)
        return res


def Text(text: str = "CAD",
         size: float = 10.0,
         thickness: float = 2.0,
         font_file: Optional[str] = None,
         center: bool = False) -> ShapeWrapper:
    """
    Generate 3D extruded text / embossed letters.
    """
    if App is None or Part is None:
        return ShapeWrapper()

    # Locate default TrueType font if not provided
    if font_file is None or not os.path.exists(font_file):
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        font_file = None
        for c in candidates:
            if os.path.exists(c):
                font_file = c
                break

    if font_file is None:
        print("[ScriptCAD Warning] No system TTF font found for 3D Text.")
        return ShapeWrapper()

    try:
        import Draft
        doc = App.ActiveDocument or App.newDocument("ScriptCAD_Temp")
        ss = Draft.make_shapestring(text, font_file, size, 0.0)
        doc.recompute()
        shape = ss.Shape.copy()
        doc.removeObject(ss.Name)

        if thickness > 0:
            extruded = shape.extrude(App.Vector(0, 0, thickness))
            wrapper = ShapeWrapper(extruded)
        else:
            wrapper = ShapeWrapper(shape)

        if center:
            bb = wrapper.bounding_box
            if bb:
                cx = (bb.XMin + bb.XMax) / 2.0
                cy = (bb.YMin + bb.YMax) / 2.0
                wrapper = wrapper.translate(-cx, -cy, 0)

        return wrapper
    except Exception as e:
        print(f"[ScriptCAD Warning] 3D Text generation failed: {e}")
        return ShapeWrapper()


# =============================================================================
# Sweeps, Lofts & Helical Solids
# =============================================================================

def Helix(pitch: float = 5.0,
          height: float = 20.0,
          radius: float = 10.0,
          angle: float = 0.0) -> ShapeWrapper:
    """
    Construct a helical 3D path wire (useful as a path for sweeps, springs, and threads).
    """
    if Part is None:
        return ShapeWrapper()
    helix_wire = Part.makeHelix(pitch, height, radius, angle)
    return ShapeWrapper(helix_wire)


def Spring(pitch: float = 5.0,
           height: float = 25.0,
           radius: float = 10.0,
           wire_radius: float = 1.0) -> ShapeWrapper:
    """
    Construct a solid compression spring or coiled thread.
    """
    if Part is None or App is None:
        return ShapeWrapper()
    helix_wire = Part.makeHelix(pitch, height, radius)
    circle_prof = Part.Wire(Part.makeCircle(wire_radius, App.Vector(radius, 0, 0), App.Vector(0, 1, 0)))
    pipe = helix_wire.makePipeShell([circle_prof], True, True)
    return ShapeWrapper(pipe)


def HelixSolid(pitch: float = 5.0,
               height: float = 25.0,
               radius: float = 10.0,
               profile_radius: float = 1.0) -> ShapeWrapper:
    """Alias for Spring."""
    return Spring(pitch=pitch, height=height, radius=radius, wire_radius=profile_radius)


def Sweep(profile: ShapeWrapper,
          path: Union[ShapeWrapper, Any],
          solid: bool = True,
          frenet: bool = True) -> ShapeWrapper:
    """
    Sweep a 2D wire or face profile along an arbitrary 3D guide wire/spine.
    Ideal for curved pipes, wiring, handrails, and customized extrusions.
    """
    if Part is None:
        return ShapeWrapper()

    # Extract spine wire
    spine_shape = path.shape if isinstance(path, ShapeWrapper) else path
    if spine_shape is None:
        return ShapeWrapper()

    # Extract profile wire
    prof_shape = profile.shape if isinstance(profile, ShapeWrapper) else profile
    if prof_shape is None:
        return ShapeWrapper()

    if hasattr(prof_shape, "Wires") and prof_shape.Wires:
        prof_wire = prof_shape.Wires[0]
    elif prof_shape.ShapeType == "Wire":
        prof_wire = prof_shape
    else:
        prof_wire = Part.Wire(prof_shape.Edges)

    try:
        pipe_solid = spine_shape.makePipeShell([prof_wire], solid, frenet)
        return ShapeWrapper(pipe_solid)
    except Exception as e:
        print(f"[ScriptCAD Warning] Sweep failed: {e}")
        return ShapeWrapper()


def Loft(profiles: List[ShapeWrapper], solid: bool = True, ruled: bool = False) -> ShapeWrapper:
    """
    Loft through a list of wire or face profiles to create organic / aerodynamic solids.
    """
    if Part is None or len(profiles) < 2:
        return ShapeWrapper()
    wires = []
    for p in profiles:
        s = p.shape if isinstance(p, ShapeWrapper) else p
        if s is None:
            continue
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
    if Part is None or App is None or profile.shape is None:
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
    if Part is None or App is None or profile.shape is None:
        return ShapeWrapper()
    base_pt = App.Vector(*center)
    dir_vec = App.Vector(*axis)
    revolved = profile.shape.revolve(base_pt, dir_vec, angle)
    return ShapeWrapper(revolved)
