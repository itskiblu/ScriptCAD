# Changelog

All notable changes to **ScriptCAD** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-10

### Added
- Native FreeCAD GUI Workbench (`ScriptCADWorkbench`) registered with FreeCAD Addon Manager and GUI workbench switcher.
- Embedded dockable script editor panel (`ScriptCADEditorDock`) with native FreeCAD `QToolBar` controls.
- Single high-density, icon-first toolbar following FreeCAD top-bar design guidelines with borderless idle buttons and subtle hover highlights.
- FreeCAD Tango-style SVG vector icons for all workbench actions (`Resources/icons/`).
- High-contrast syntax highlighter (`PythonHighlighter`) tailored for 3D CAD modeling with mint primitives, warm gold chained methods, coral strings, and pastel mint numbers.
- Line number gutter with bold active line highlighting, slate gray numbering, and crisp vertical divider.
- Collapsible output console drawer maximized for vertical screen real estate, auto-expanding on execution errors.
- Real-time `⚡ Live Sync` mode with debounced auto-execution on typing pause.
- Automatic conversion and tagging for active `PartDesign::Body` containers.
- Fluent, operator-overloaded Constructive Solid Geometry (CSG) modeling engine:
  - Boolean Cut (`-`), Union (`+`), and Intersection (`&`).
  - Native 3D primitives: `Box`, `Cube`, `Cylinder`, `Sphere`, `Cone`, `Torus`, `Pipe`, `Wedge`.
  - 2D sketch/profile elements: `Slot`, `Circle`, `Arc`, `Ellipse`, `Rectangle`, `Spline`, `Text`.
  - Engineering modifiers: `.fillet()`, `.chamfer()`, `.shell()`, `.linear_array()`, `.polar_array()`.
  - Sweeps and coils: `Sweep()`, `Loft()`, `Spring()`, `Helix()`.
- Algorithmic 3D mesh art tools with watertight B-Rep solid conversion via `.solidify()`:
  - Parametric wave surfaces, math heightfields, and procedural geometry generators.
- Direct multi-format CAD model export to STEP (`.step`), STL (`.stl`), and Wavefront OBJ (`.obj`).
- 8 built-in procedural geometry recipes and presets accessible directly via toolbar dropdown.
- FreeCAD Document transaction management (`openTransaction`, `commitTransaction`, `abortTransaction`) for seamless `Ctrl+Z` undo/redo integration.
- Full PySide2 (Qt5) and PySide6 (Qt6) compatibility layer.
