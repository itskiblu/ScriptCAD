"""
BlendCAD backward-compatibility alias module.
Redirects all imports to the renamed `scriptcad` package.
"""

from scriptcad import (
    ShapeWrapper,
    set_partdesign_mode,
    convert_to_body,
    Box, Cube, Cylinder, Sphere, Cone, Torus,
    Plane, Circle, Polygon, Loft, Extrude, Revolve,
    MeshArt,
    clear_document,
    active_document,
    Vector,
    math,
)

__all__ = [
    "ShapeWrapper",
    "set_partdesign_mode",
    "convert_to_body",
    "Box", "Cube", "Cylinder", "Sphere", "Cone", "Torus",
    "Plane", "Circle", "Polygon", "Loft", "Extrude", "Revolve",
    "MeshArt",
    "clear_document",
    "active_document",
    "Vector",
    "math",
]
