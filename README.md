# ScriptCAD: Procedural Solid Modeling & Mesh Art Scripting Workbench for FreeCAD

**ScriptCAD** brings a fluid, procedural scripting workflow and embedded code workspace directly into **FreeCAD's** precision solid-modeling CAD environment.

---

## Highlights

- **Embedded Scripting Workspace**: A dockable code editor inside FreeCAD featuring dark theme, line numbers, and Python syntax highlighting.
- **Fast Run Shortcuts**: Run your script anytime with **`Alt+P`** or **`Ctrl+Enter`**.
- **⚡ Live Sync Mode**: Tweak dimensions or formulas in code and see your CAD model update automatically as you type.
- **Fluent & Pythonic CAD Solids**: Avoid verbose OpenCASCADE boilerplate. Create solids, apply transforms, and chain booleans with ease.
- **Operator-Overloaded CSG**:
  - `a - b` : Boolean Cut (Difference)
  - `a + b` : Boolean Union (Fuse)
  - `a & b` : Boolean Intersection (Common)
- **Mesh Art & Solid Bridge**: Generate algorithmic meshes (math heightfields, noise surfaces, wave planes) and instantly convert them into watertight CAD B-Rep solids with `.to_solid()`.
- **Integrated Undo/Redo**: Every script execution is wrapped in FreeCAD's native transaction history (press `Ctrl+Z` to undo).
- **Built-in Presets**: 1-click recipe templates including heatsink radial fins, twisted organic lofts, electronics enclosures, and procedural wave surfaces.

---

## Installation & Setup

ScriptCAD is located at:
`C:\Users\brian\.gemini\antigravity-ide\scratch\BlendCAD`

It is linked directly to your FreeCAD 1.1 installation:
`%APPDATA%\FreeCAD\v1-1\Mod\ScriptCAD`

### To launch in FreeCAD:
1. Start **FreeCAD**.
2. In the workbench selector dropdown (at the top), choose **ScriptCAD**.
3. The **ScriptCAD Scripting** panel will dock automatically on the right.
4. Click **▶ Run (Alt+P)** to generate your first 3D object!

---

## API Quick Reference

### 1. Primitives
```python
from scriptcad import *

# Centered or corner-aligned primitives
box = Box(length=40, width=40, height=10, center=True)
cube = Cube(size=20, center=True)
cyl = Cylinder(r=5, h=30, center=True)
ball = Sphere(r=10)
cone = Cone(radius1=10, radius2=2, height=20)
donut = Torus(radius1=25, radius2=5)
```

### 2. Transforms & Method Chaining
```python
# Transform methods return a new ShapeWrapper for clean chaining:
part = (
    Box(10, 10, 10)
    .rotate_z(45)
    .translate(x=15, z=5)
    .fillet(radius=1.5)
    .color(0.2, 0.7, 0.9)
)
```

### 3. Clean CSG Booleans
```python
base = Box(50, 50, 15, center=True)
hole = Cylinder(r=10, h=30, center=True)
post = Cylinder(r=4, h=20, center=True).at(x=15, y=15, z=10)

# Subtract center hole and fuse mounting post:
result = (base - hole) + post
result.show("MountPlate")
```

### 4. Lofts & Revolutions
```python
# Organic twisted vase
p1 = Circle(10).at(z=0)
p2 = Circle(6).at(z=15)
p3 = Circle(12).at(z=30)

vase = Loft([p1, p2, p3], solid=True).color(0.9, 0.4, 0.2)
vase.show("Vase")
```

### 5. Procedural Mesh Art to CAD Solid
```python
# Create an artistic mathematical wave surface
mesh = MeshArt.ripple_plane(size=80.0, resolution=30, wave_height=5.0, frequency=0.2)

# Convert directly to an OpenCASCADE CAD Shell/Solid
solid = mesh.to_solid(make_solid=False)
solid.show("AlgorithmicWave", color=(0.1, 0.8, 0.7))
```

---

## Preset Templates Included in GUI

1. **01 - Welcome: CSG Cutout**: Mounting bracket with countersunk bolt holes and edge fillets.
2. **02 - Procedural Radial Fins**: Parametric heat sink / turbine rotor with polar array loops.
3. **03 - Twisted Organic Loft**: Twisted polygonal loft inspired by generative vase design.
4. **04 - Procedural Wave Surface**: Math-driven ripple surface converted to CAD.
5. **05 - Parametric Enclosure with Screws**: Hollowed electronic project box with internal screw bosses.
