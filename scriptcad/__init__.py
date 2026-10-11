# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD: Procedural Solid Modeling & Mesh Art Scripting Engine for FreeCAD.
"""

import math
try:
    import FreeCAD as App
    Vector = App.Vector
except ImportError:
    App = None
    Vector = None

from .core import (
    ShapeWrapper,
    set_partdesign_mode,
    convert_to_body,
    union,
    difference,
    intersection,
    import_step,
    import_brep
)
from .primitives import (
    Box, Cube, Cylinder, Sphere, Cone, Torus, Wedge, Pipe, Tube,
    Plane, Rectangle, Circle, Arc, Ellipse, Polygon, Spline, Slot, Text,
    Loft, Extrude, Revolve, Sweep, Helix, Spring, HelixSolid
)
from .mesh_art import MeshArt


def clear_document(doc=None):
    """Delete all objects from the active document."""
    if App is None:
        return
    if doc is None:
        doc = App.ActiveDocument
    if doc is None:
        return
    names = [getattr(obj, "Name", None) for obj in doc.Objects]
    for name in names:
        if name and doc.getObject(name) is not None:
            try:
                doc.removeObject(name)
            except Exception:
                pass
    doc.recompute()


def active_document(name: str = "ScriptCAD_Project"):
    """Get or create the active FreeCAD document."""
    if App is None:
        return None
    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument(name)
    return doc


__all__ = [
    "ShapeWrapper",
    "set_partdesign_mode",
    "convert_to_body",
    "union", "difference", "intersection",
    "import_step", "import_brep",
    "Box", "Cube", "Cylinder", "Sphere", "Cone", "Torus", "Wedge", "Pipe", "Tube",
    "Plane", "Rectangle", "Circle", "Arc", "Ellipse", "Polygon", "Spline", "Slot", "Text",
    "Loft", "Extrude", "Revolve", "Sweep", "Helix", "Spring", "HelixSolid",
    "MeshArt",
    "clear_document",
    "active_document",
    "Vector",
    "math"
]
