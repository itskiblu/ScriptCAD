# ScriptCAD: Procedural Solid Modeling & Mesh Art Scripting Workbench for FreeCAD

[![License: LGPL v2.1](https://img.shields.io/badge/License-LGPL%20v2.1-blue.svg)](LICENSE)
[![FreeCAD](https://img.shields.io/badge/FreeCAD-0.20%20--%201.1%2B-orange.svg)](https://www.freecad.org)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org)

**ScriptCAD** brings an intuitive, procedural scripting workflow and embedded live-code workspace directly into FreeCAD's precision solid-modeling CAD environment.

---

## Highlights

- **Native FreeCAD UI & Theming**: Conforms directly to FreeCAD 1.1 UI standards, adapting seamlessly to FreeCAD Dark, Light, and Classic themes.
- **Top-Bar Aligned Single-Row Toolbar**: High-density, icon-first toolbar ordered from most-used to least-used actions with borderless idle buttons and subtle hover states.
- **Embedded Scripting Workspace**: A dockable code editor inside FreeCAD with high-contrast line numbers, active line highlighting, cursor coordinates, and theme-adaptive Python syntax highlighting.
- **⚡ Live Sync Mode**: Tweak dimensions or formulas in code and see your CAD model update automatically as you type.
- **Fast Run Shortcuts**: Execute scripts anytime with **`Alt+P`** or **`Ctrl+Enter`**.
- **Collapsible Console Drawer**: Clean bottom drawer maximized for vertical screen real estate, auto-expanding if errors or exceptions occur (`Ctrl+` ` / `F8`).
- **FreeCAD Native Tango Icons**: Uses FreeCAD's native Qt resource icons (`:/icons/`) with standalone vector SVG fallbacks.
- **1-Click Multi-Format Export**: Export your generated model directly to **STEP** (`.step`), **STL** (`.stl`), or **OBJ** (`.obj`).
- **🔄 3D Model Decompiler & Script Generator**: 1-click reverse-engineering (**`Ctrl+Shift+D`**) of manual FreeCAD models, CSG primitives, boolean trees, and PartDesign bodies into clean, editable, procedural Python scripts.
- **PartDesign Body Integration**: Automatic or 1-click conversion into active `PartDesign::Body` containers for seamless parametric modeling workflows.
- **Fluent & Pythonic CAD Solids**: Avoid verbose OpenCASCADE boilerplate. Create solids, apply transforms, and chain booleans with ease:
  - `a - b` : Boolean Cut (Difference)
  - `a + b` : Boolean Union (Fuse)
  - `a & b` : Boolean Intersection (Common)
- **Advanced CAD Operations**:
  - `.shell(thickness, open_faces="top")` : Native OpenCASCADE hollowing.
  - `.linear_array(count, step)` : Linear pattern duplication.
  - `.polar_array(count, total_angle)` : Polar/radial array duplication.
  - `Sweep(profile, path)` : Sweep 2D profiles along arbitrary 3D B-Spline curves.
  - `Spring(pitch, height, radius, wire_radius)` / `Helix(...)` : Parametric helical coils.
  - `Slot(length, width, thickness)` : Mechanical stadium slots.
  - `Text("Label", size, thickness)` : 3D extruded and embossed text.
- **Watertight Solid Conversion**: Generate algorithmic meshes (math heightfields, noise surfaces, wave planes) and convert them directly into watertight, 3D-printable B-Rep solids with `.solidify(thickness)`.
- **Integrated Undo/Redo & Console Logging**: Script executions are wrapped in FreeCAD's native transaction history (`Ctrl+Z`), with logging echoed to FreeCAD's Report View and Python Console.
- **8 Built-in Presets**: 1-click recipe templates in the GUI dropdown covering CSG, radial arrays, organic lofts, solid waves, shells, sweeps, springs, and 3D text.

---

## Prerequisites & Compatibility

- **FreeCAD**: Version 0.20, 0.21, 1.0, 1.1, or later.
- **Python**: Python 3.8 or newer (bundled with FreeCAD).
- **GUI Framework**: PySide2 (Qt5) or PySide6 (Qt6) (bundled with FreeCAD).
- **External Dependencies**: None. Uses only standard FreeCAD libraries and Python standard modules (`math`, `re`, `time`, `io`).

---

## Installation

### Method 1: FreeCAD Addon Manager (Recommended)

#### Option A: Direct Search (When listed in Addon Index)
1. Open FreeCAD.
2. Navigate to **Tools → Addon Manager**.
3. Select the **Workbenches** tab.
4. Search for **ScriptCAD** and click **Install**.
5. Restart FreeCAD when prompted.

#### Option B: Add Custom Repository (Available immediately)
1. Open FreeCAD.
2. Open **Tools → Addon Manager**.
3. Click the **Configure... (Gear ⚙ icon)** at the bottom.
4. Under **Custom repositories**, click **+ Add repository**.
5. Enter `https://github.com/itskiblu/ScriptCAD` and branch `main`.
6. Click **Save**, search for **ScriptCAD**, and click **Install**!

---

### Method 2: Universal 1-Click Installer (`install.py`)
Clone or download this repository, open a terminal in the folder, and run:

```bash
# Developer / live-sync link mode (symlink / junction):
python install.py

# Or standalone copy mode (copies files directly into FreeCAD Mod):
python install.py --copy
```

`install.py` auto-detects FreeCAD 1.1, 1.0, and 0.2x directories on Windows, Linux, and macOS. To uninstall at any time:
```bash
python install.py --uninstall
```

---

### Method 3: Manual Installation (Git Clone or ZIP)
Clone or extract the repository directly into your FreeCAD `Mod` directory:

- **Windows**:
  ```powershell
  cd "$env:APPDATA\FreeCAD\v1-1\Mod"  # or "$env:APPDATA\FreeCAD\Mod"
  git clone https://github.com/itskiblu/ScriptCAD.git
  ```

- **Linux**:
  ```bash
  cd ~/.local/share/FreeCAD/Mod
  git clone https://github.com/itskiblu/ScriptCAD.git
  ```

- **macOS**:
  ```bash
  cd ~/Library/Application\ Support/FreeCAD/Mod
  git clone https://github.com/itskiblu/ScriptCAD.git
  ```

---

### Method 4: Offline ZIP Archive
1. Download `ScriptCAD-v1.0.0.zip` from [GitHub Releases](https://github.com/itskiblu/ScriptCAD/releases).
2. Extract the `ScriptCAD` folder into your FreeCAD `Mod` directory (or use **Addon Manager → Install from file...**).
3. Restart FreeCAD.


---

## Quickstart Guide

1. Start **FreeCAD**.
2. In the workbench selector dropdown, choose **ScriptCAD**.
3. The **ScriptCAD Scripting** editor will dock automatically on the right side of your 3D view.
4. Enter your script or pick a template from the **Templates (📜▾)** dropdown.
5. Click the green **Run (▶)** button or press **`Alt+P`** / **`Ctrl+Enter`** to execute!

### Example Script: Parametric CSG Bracket
```python
from scriptcad import *

# 1. Base solid
body = Box(length=40, width=40, height=15, center=True)

# 2. Subtract center bore
bore = Cylinder(r=8, h=25, center=True)
result = body - bore

# 3. Add 4 corner bolt countersinks
for x in [-14, 14]:
    for y in [-14, 14]:
        hole = Cylinder(r=2.5, h=20, center=True).at(x, y, 0)
        result -= hole

# 4. Apply edge fillet and display in FreeCAD 3D viewport
result.fillet(1.0).color(0.2, 0.6, 0.9).show("ParametricMount")
```

---

## API Reference

### 1. 3D & 2D Primitives
```python
from scriptcad import *

# 3D Solids
box = Box(length=40, width=40, height=10, center=True)
cube = Cube(size=20, center=True)
cyl = Cylinder(r=5, h=30, center=True)
ball = Sphere(r=10)
cone = Cone(radius1=10, radius2=2, height=20)
donut = Torus(radius1=25, radius2=5)
pipe = Pipe(outer_r=10, inner_r=8, height=30)
wedge = Wedge(10, 10, 10, 0, 0, 10, 10)

# 2D Profiles & Curves
slot = Slot(length=30, width=10, thickness=4)
circ = Circle(radius=8, filled=True)
arc = Arc(radius=10, start_angle=0, end_angle=180)
ellipse = Ellipse(r1=12, r2=6, filled=True)
rect = Rectangle(20, 15, center=True)
path = Spline([(0, 0, 0), (10, 0, 20), (25, 15, 35)])
label = Text("ScriptCAD", size=10, thickness=2, center=True)
```

### 2. Transforms & Method Chaining
```python
part = (
    Box(10, 10, 10)
    .rotate_z(45)
    .translate(x=15, z=5)
    .fillet(radius=1.5)
    .color(0.2, 0.7, 0.9)
)
```

### 3. Shelling & Array Duplication
```python
# Open-top enclosure with 2mm walls
enclosure = Box(60, 40, 25, center=True).fillet(2.0).shell(thickness=2.0, open_faces="top")

# Radial impeller fin pattern
fins = Box(15, 2, 20, center=True).at(x=12, y=0, z=0).polar_array(count=8)
```

### 4. Sweeps, Springs & Helices
```python
path = Spline([(0, 0, 0), (0, 0, 30), (20, 0, 60), (40, 0, 70)])
tube = Sweep(profile=Circle(radius=5, filled=False), path=path)

spring = Spring(pitch=6.0, height=40.0, radius=12.0, wire_radius=1.5)
```

### 5. Algorithmic Mesh Art to Watertight CAD Solid
```python
# Create algorithmic wave heightfield
mesh = MeshArt.ripple_plane(size=60.0, resolution=25, wave_height=4.0)

# Solidify into a watertight, manifold 3D-printable solid block
solid_wave = mesh.solidify(thickness=6.0)

# Cut mechanical mounting bore with CSG
final_part = solid_wave - Cylinder(r=5, h=30, center=True)
final_part.show("SolidWave")
```

### 6. Multi-Format Export
```python
part.export_step("output/part.step")
part.export_stl("output/part.stl")
part.export_obj("output/part.obj")
```

---

## AI & LLM Script Generation

ScriptCAD includes a dedicated machine-readable specification conforming to the [`llms.txt`](https://llmstxt.org/) standard at [`llms.txt`](llms.txt) (or [`AGENTS.md`](AGENTS.md)).

When asking an AI assistant (such as ChatGPT, Claude, Gemini, Cursor, or Copilot) to generate 3D models for ScriptCAD, instruct it with:

> *"Write a ScriptCAD Python script for [your part description]. Look up the ScriptCAD API specification at https://raw.githubusercontent.com/itskiblu/ScriptCAD/main/llms.txt before writing the code."*

### Key Prompt Rules for LLMs:
- **Always import**: `from scriptcad import *`
- **Render to Viewport**: Every script must conclude with `.show("ObjectName")` (e.g. `part.color(0.2, 0.6, 0.9).show("MyPart")`).
- **CSG Booleans**: Use Python operators (`a - b` for cut, `a + b` for fuse, `a & b` for common).
- **Transforms**: Use chained methods (`.at(x, y, z)`, `.rotate_z(deg)`, `.fillet(r)`, `.shell(t)`).
- **Units**: Millimeters (`mm`) and degrees (`°`).
- **No FreeCAD OCC Boilerplate**: Do not use `Part.makeBox()`, `App.Placement()`, or `doc.addObject()`.

---

## License

ScriptCAD is open-source software licensed under the **GNU Lesser General Public License v2.1 or later (LGPL-2.1-or-later)**.
See the [LICENSE](LICENSE) file for complete terms and conditions.

For release history and version notes, see [CHANGELOG.md](CHANGELOG.md).
