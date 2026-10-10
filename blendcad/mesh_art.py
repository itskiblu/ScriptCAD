"""
BlendCAD Mesh Art Engine:
Procedural 3D mesh generation, math surfaces, noise displacement,
and seamless conversion into OpenCASCADE CAD solids.
"""

import math
from typing import List, Tuple, Callable, Optional, Union

try:
    import FreeCAD as App
    import Part
    import sys
    if App is not None:
        home = App.getHomePath()
        mesh_mod = home + "Mod/Mesh"
        if mesh_mod not in sys.path:
            sys.path.append(mesh_mod)
    import Mesh
except ImportError:
    App = None
    Part = None
    Mesh = None

from .core import ShapeWrapper


class MeshArt:
    """
    Blender-style mesh container storing vertices and faces.
    Provides procedural operations, mathematical heightfields/surfaces,
    and bridge to FreeCAD B-Rep solids.
    """

    def __init__(self, vertices: Optional[List[Tuple[float, float, float]]] = None,
                 faces: Optional[List[List[int]]] = None):
        self.vertices = [list(v) for v in (vertices or [])]
        self.faces = [list(f) for f in (faces or [])]

    # --- Procedural Generators ---

    @classmethod
    def grid(cls, nx: int = 20, ny: int = 20,
             sx: float = 100.0, sy: float = 100.0,
             center: bool = True) -> "MeshArt":
        """Generate a flat 2D quad/tri mesh grid on the XY plane."""
        vertices = []
        faces = []
        ox = -sx / 2.0 if center else 0.0
        oy = -sy / 2.0 if center else 0.0

        dx = sx / (nx - 1)
        dy = sy / (ny - 1)

        for j in range(ny):
            for i in range(nx):
                x = ox + i * dx
                y = oy + j * dy
                vertices.append([x, y, 0.0])

        for j in range(ny - 1):
            for i in range(nx - 1):
                v0 = j * nx + i
                v1 = j * nx + (i + 1)
                v2 = (j + 1) * nx + (i + 1)
                v3 = (j + 1) * nx + i
                # Triangulate
                faces.append([v0, v1, v2])
                faces.append([v0, v2, v3])

        return cls(vertices, faces)

    @classmethod
    def surface(cls, func: Callable[[float, float], Tuple[float, float, float]],
                u_range: Tuple[float, float] = (0.0, 1.0),
                v_range: Tuple[float, float] = (0.0, 1.0),
                nu: int = 30, nv: int = 30) -> "MeshArt":
        """
        Generate a parametric math surface from a function:
        `func(u, v) -> (x, y, z)`
        """
        u_min, u_max = u_range
        v_min, v_max = v_range
        du = (u_max - u_min) / (nu - 1)
        dv = (v_max - v_min) / (nv - 1)

        vertices = []
        for j in range(nv):
            v = v_min + j * dv
            for i in range(nu):
                u = u_min + i * du
                x, y, z = func(u, v)
                vertices.append([float(x), float(y), float(z)])

        faces = []
        for j in range(nv - 1):
            for i in range(nu - 1):
                v0 = j * nu + i
                v1 = j * nu + (i + 1)
                v2 = (j + 1) * nu + (i + 1)
                v3 = (j + 1) * nu + i
                faces.append([v0, v1, v2])
                faces.append([v0, v2, v3])

        return cls(vertices, faces)

    @classmethod
    def torus_mesh(cls, major_r: float = 20.0, minor_r: float = 6.0,
                   nu: int = 32, nv: int = 16) -> "MeshArt":
        """Parametric torus mesh."""
        def torus_func(u, v):
            x = (major_r + minor_r * math.cos(v)) * math.cos(u)
            y = (major_r + minor_r * math.cos(v)) * math.sin(u)
            z = minor_r * math.sin(v)
            return (x, y, z)

        return cls.surface(torus_func,
                           u_range=(0.0, 2 * math.pi),
                           v_range=(0.0, 2 * math.pi),
                           nu=nu, nv=nv)

    @classmethod
    def ripple_plane(cls, size: float = 100.0, resolution: int = 40,
                     wave_height: float = 4.0, frequency: float = 0.2) -> "MeshArt":
        """Artistic wave/ripple plane."""
        mesh = cls.grid(nx=resolution, ny=resolution, sx=size, sy=size, center=True)
        for v in mesh.vertices:
            r = math.hypot(v[0], v[1])
            v[2] = wave_height * math.sin(r * frequency)
        return mesh

    # --- Procedural Modifiers ---

    def displace(self, func: Callable[[float, float, float], Union[float, Tuple[float, float, float]]]) -> "MeshArt":
        """
        Displace vertices using a function.
        Function can return a float (Z offset) or (dx, dy, dz).
        """
        for v in self.vertices:
            res = func(v[0], v[1], v[2])
            if isinstance(res, (int, float)):
                v[2] += float(res)
            elif isinstance(res, (tuple, list)) and len(res) == 3:
                v[0] += float(res[0])
                v[1] += float(res[1])
                v[2] += float(res[2])
        return self

    def noise(self, amplitude: float = 3.0, freq: float = 0.1) -> "MeshArt":
        """Apply procedural multi-harmonic sinusoidal noise to surface."""
        for v in self.vertices:
            x, y = v[0] * freq, v[1] * freq
            n = (math.sin(x) * math.cos(y) +
                 0.5 * math.sin(2.3 * x + 1.2) * math.cos(1.8 * y) +
                 0.25 * math.sin(4.1 * x - 2.1) * math.sin(3.7 * y))
            v[2] += amplitude * n
        return self

    # --- FreeCAD Engine Interop ---

    def to_freecad_mesh(self):
        """Build a native FreeCAD Mesh.Mesh object."""
        if Mesh is None:
            return None
        m = Mesh.Mesh()
        for f in self.faces:
            if len(f) == 3:
                p1, p2, p3 = self.vertices[f[0]], self.vertices[f[1]], self.vertices[f[2]]
                m.addFacet(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], p3[0], p3[1], p3[2])
            elif len(f) == 4:
                p1, p2, p3, p4 = [self.vertices[idx] for idx in f]
                m.addFacet(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], p3[0], p3[1], p3[2])
                m.addFacet(p1[0], p1[1], p1[2], p3[0], p3[1], p3[2], p4[0], p4[1], p4[2])
        return m

    def to_solid(self, tolerance: float = 0.05, make_solid: bool = True) -> ShapeWrapper:
        """
        Convert the polygonal mesh into an OpenCASCADE CAD Shell/Solid.
        Enables boolean operations (+, -, &) with regular CAD primitives!
        """
        if Part is None or Mesh is None:
            return ShapeWrapper()

        fc_mesh = self.to_freecad_mesh()
        shape = Part.Shape()
        shape.makeShapeFromMesh(fc_mesh.Topology, tolerance)

        if make_solid:
            try:
                solid = Part.makeSolid(shape)
                if solid.isValid() and solid.Volume > 0:
                    return ShapeWrapper(solid)
            except Exception:
                pass

        return ShapeWrapper(shape)

    def show(self, name: str = "ProceduralMesh",
             color: Tuple[float, float, float] = (0.9, 0.4, 0.1),
             as_solid: bool = True,
             doc=None):
        """
        Render this procedural mesh into FreeCAD.
        If as_solid=True, displays as a full CAD Shape.
        If as_solid=False, displays as a lightweight FreeCAD Mesh object.
        """
        if App is None:
            return None

        if doc is None:
            doc = App.ActiveDocument or App.newDocument("BlendCAD_Model")

        if as_solid:
            cad_solid = self.to_solid(make_solid=False)
            return cad_solid.show(name=name, color=color, doc=doc)
        else:
            fc_mesh = self.to_freecad_mesh()
            existing = doc.getObject(name)
            if existing and hasattr(existing, "Mesh"):
                obj = existing
            else:
                obj = doc.addObject("Mesh::Feature", name)
            obj.Mesh = fc_mesh

            try:
                import FreeCADGui as Gui
                if Gui.runMode() != "Cmd":
                    obj.ViewObject.ShapeColor = color
            except Exception:
                pass

            doc.recompute()
            return obj
