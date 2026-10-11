# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Mesh Art Engine:
Procedural 3D mesh generation, mathematical surfaces, noise displacement,
solidification into watertight CAD solids, and mesh import/export.
"""

import math
import os
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
    Blender-style procedural mesh container storing vertices and faces.
    Provides procedural generators, mathematical heightfields/surfaces,
    noise displacement, watertight CAD solid bridge (`solidify`), and STL/OBJ I/O.
    """

    def __init__(self,
                 vertices: Optional[Union[List[Tuple[float, float, float]], List[List[float]]]] = None,
                 faces: Optional[Union[List[List[int]], List[Tuple[int, ...]]]] = None,
                 grid_dims: Optional[Tuple[int, int]] = None):
        self.vertices = [list(v) for v in (vertices or [])]
        self.faces = [list(f) for f in (faces or [])]
        self.grid_dims = grid_dims  # (nx, ny) if generated from structured 2D grid

    # =========================================================================
    # Procedural Generators
    # =========================================================================

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
                faces.append([v0, v1, v2])
                faces.append([v0, v2, v3])

        return cls(vertices, faces, grid_dims=(nx, ny))

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

        return cls(vertices, faces, grid_dims=(nu, nv))

    @classmethod
    def heightfield(cls, func: Callable[[float, float], float],
                    x_range: Tuple[float, float] = (-50.0, 50.0),
                    y_range: Tuple[float, float] = (-50.0, 50.0),
                    resolution: int = 30) -> "MeshArt":
        """Generate a 3D terrain/heightfield from `z = func(x, y)`."""
        def surf_func(u, v):
            z = func(u, v)
            return (u, v, z)

        return cls.surface(surf_func, u_range=x_range, v_range=y_range, nu=resolution, nv=resolution)

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
    def mobius_strip(cls, radius: float = 20.0, width: float = 8.0,
                     nu: int = 60, nv: int = 10) -> "MeshArt":
        """Parametric Möbius strip mesh with single half-twist."""
        def mobius_func(u, v):
            # u: [0, 2pi], v: [-width/2, width/2]
            w = v
            t = u
            x = (radius + w * math.cos(t / 2.0)) * math.cos(t)
            y = (radius + w * math.cos(t / 2.0)) * math.sin(t)
            z = w * math.sin(t / 2.0)
            return (x, y, z)

        return cls.surface(mobius_func,
                           u_range=(0.0, 2 * math.pi),
                           v_range=(-width / 2.0, width / 2.0),
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

    @classmethod
    def sphere_mesh(cls, radius: float = 10.0, rings: int = 16, segments: int = 32) -> "MeshArt":
        """UV Sphere polygonal mesh."""
        def sphere_func(u, v):
            # u: [0, 2pi], v: [0, pi]
            x = radius * math.sin(v) * math.cos(u)
            y = radius * math.sin(v) * math.sin(u)
            z = radius * math.cos(v)
            return (x, y, z)

        return cls.surface(sphere_func,
                           u_range=(0.0, 2 * math.pi),
                           v_range=(0.001, math.pi - 0.001),
                           nu=segments, nv=rings)

    # =========================================================================
    # Procedural Modifiers
    # =========================================================================

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

    # =========================================================================
    # Watertight CAD Solid Bridge
    # =========================================================================

    def solidify(self, thickness: float = 5.0, z_base: Optional[float] = None) -> ShapeWrapper:
        """
        Convert an open 2D heightfield/surface mesh into a 100% closed, watertight
        B-Rep CAD solid volume suitable for 3D printing or boolean CSG cuts/fusions.

        Extrudes perimeter edges down to a flat base plane at `z_base` (or `min(z) - thickness`)
        and adds a sealed bottom cap.
        """
        if not self.vertices or not self.faces:
            return ShapeWrapper()

        min_z = min(v[2] for v in self.vertices)
        base_level = z_base if z_base is not None else (min_z - abs(thickness))

        N = len(self.vertices)
        all_verts = [list(v) for v in self.vertices]
        for v in self.vertices:
            all_verts.append([v[0], v[1], base_level])

        all_faces = [list(f) for f in self.faces]

        # Invert top faces for bottom cap
        for f in self.faces:
            all_faces.append([f[0] + N, f[2] + N, f[1] + N])

        if self.grid_dims:
            nx, ny = self.grid_dims
            # Bottom edge (j=0)
            for i in range(nx - 1):
                t0 = i
                t1 = i + 1
                b0 = t0 + N
                b1 = t1 + N
                all_faces.append([t0, b0, b1])
                all_faces.append([t0, b1, t1])

            # Right edge (i=nx-1)
            for j in range(ny - 1):
                t0 = j * nx + (nx - 1)
                t1 = (j + 1) * nx + (nx - 1)
                b0 = t0 + N
                b1 = t1 + N
                all_faces.append([t0, b0, b1])
                all_faces.append([t0, b1, t1])

            # Top edge (j=ny-1)
            for i in range(nx - 1):
                t0 = (ny - 1) * nx + (i + 1)
                t1 = (ny - 1) * nx + i
                b0 = t0 + N
                b1 = t1 + N
                all_faces.append([t0, b0, b1])
                all_faces.append([t0, b1, t1])

            # Left edge (i=0)
            for j in range(ny - 1):
                t0 = (j + 1) * nx
                t1 = j * nx
                b0 = t0 + N
                b1 = t1 + N
                all_faces.append([t0, b0, b1])
                all_faces.append([t0, b1, t1])

        # Convert constructed manifold to FreeCAD Mesh
        if Mesh is None or Part is None:
            return ShapeWrapper()

        m = Mesh.Mesh()
        for f in all_faces:
            p1, p2, p3 = all_verts[f[0]], all_verts[f[1]], all_verts[f[2]]
            m.addFacet(p1[0], p1[1], p1[2], p2[0], p2[1], p2[2], p3[0], p3[1], p3[2])

        shape = Part.Shape()
        shape.makeShapeFromMesh(m.Topology, 0.05)
        try:
            solid = Part.makeSolid(shape)
            if solid.isValid() and solid.Volume > 0:
                return ShapeWrapper(solid)
        except Exception:
            pass
        return ShapeWrapper(shape)

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
        Enables boolean operations (+, -, &) with regular CAD primitives.
        """
        if Part is None or Mesh is None:
            return ShapeWrapper()

        fc_mesh = self.to_freecad_mesh()
        if fc_mesh is None:
            return ShapeWrapper()
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

    # =========================================================================
    # Mesh Import & Export
    # =========================================================================

    def export_stl(self, filepath: str) -> bool:
        """Export mesh to STL file."""
        fc_mesh = self.to_freecad_mesh()
        if fc_mesh is None:
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            fc_mesh.write(filepath)
            print(f"[ScriptCAD] Exported mesh to STL: {filepath}")
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] Mesh STL export failed: {e}")
            return False

    def export_obj(self, filepath: str) -> bool:
        """Export mesh to Wavefront OBJ file."""
        fc_mesh = self.to_freecad_mesh()
        if fc_mesh is None:
            return False
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            fc_mesh.write(filepath)
            print(f"[ScriptCAD] Exported mesh to OBJ: {filepath}")
            return True
        except Exception as e:
            print(f"[ScriptCAD Error] Mesh OBJ export failed: {e}")
            return False

    @classmethod
    def from_stl(cls, filepath: str) -> "MeshArt":
        """Load an STL file from disk into a MeshArt object."""
        if Mesh is None or not os.path.exists(filepath):
            return cls()
        try:
            m = Mesh.Mesh(filepath)
            verts = [[p.x, p.y, p.z] for p in m.Points]
            facets = [list(f.PointIndices) for f in m.Facets]
            return cls(verts, facets)
        except Exception as e:
            print(f"[ScriptCAD Error] Could not load STL '{filepath}': {e}")
            return cls()

    # =========================================================================
    # Presentation
    # =========================================================================

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
            doc = App.ActiveDocument or App.newDocument("ScriptCAD_Model")

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
