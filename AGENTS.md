# ScriptCAD Agent & LLM Guide

This repository contains **ScriptCAD**, a procedural solid modeling and mesh art workbench for FreeCAD.

If you are an AI assistant or coding agent asked to generate or modify Python scripts for ScriptCAD, refer to:
- **Comprehensive API & Generation Rules**: [llms.txt](llms.txt)
- **Core Engine Implementation**: [scriptcad/core.py](scriptcad/core.py)
- **CAD Primitives**: [scriptcad/primitives.py](scriptcad/primitives.py)
- **Mesh Art & Solidification**: [scriptcad/mesh_art.py](scriptcad/mesh_art.py)
- **Model Decompiler**: [scriptcad/decompiler.py](scriptcad/decompiler.py)
- **Preset Scripts**: [gui/editor_dock.py](gui/editor_dock.py) (lines 1268-1420)

## Quick Invariants for Agents
1. Every script starts with `from scriptcad import *`.
2. Visible parts must conclude with `.show("ObjectName")` (e.g., `part.color(0.2, 0.6, 0.9).show("Mount")`).
3. Use operator overloading for CSG booleans (`-` for cut, `+` for union, `&` for intersection).
4. Use method chaining for transforms (`.at(x, y, z)`, `.rotate_z(deg)`, `.fillet(r)`, `.shell(...)`).
5. Units are millimeters (`mm`) and angles are degrees (`°`).
6. Do NOT generate raw OpenCASCADE / standard FreeCAD boilerplate (`Part.makeBox`, `App.Placement`, `doc.addObject`).
