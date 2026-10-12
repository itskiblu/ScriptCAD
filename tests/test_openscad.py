# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Unit tests for ScriptCAD OpenSCAD engine, tokenizer, parser, and transpiler.
"""

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scriptcad as sc
from scriptcad.openscad import (
    is_openscad_code,
    transpile_openscad,
    run_openscad,
    tokenize,
    OpenSCADParser
)


class TestOpenSCADEngine(unittest.TestCase):
    """Test OpenSCAD script recognition, transpilation, and geometric execution."""

    def test_is_openscad_code(self):
        # OpenSCAD snippets
        scad_1 = "difference() { cube([10, 10, 10]); cylinder(r=2, h=12); }"
        scad_2 = "module hole() { cylinder(r=5, h=20); }\nhole();"
        scad_3 = "// OpenSCAD comment\nwidth = 20;\ncube(width);"

        self.assertTrue(is_openscad_code(scad_1))
        self.assertTrue(is_openscad_code(scad_2))
        self.assertTrue(is_openscad_code(scad_3))

        # Python snippets
        py_1 = "from scriptcad import *\nbox = Box(10, 10, 10)\nbox.show('M')"
        py_2 = "import math\nx = 20\ny = math.sin(x)"

        self.assertFalse(is_openscad_code(py_1))
        self.assertFalse(is_openscad_code(py_2))

    def test_transpile_primitives(self):
        scad = "cube([20, 30, 40], center=true);"
        py = transpile_openscad(scad)
        self.assertIn("Box(length=20, width=30, height=40, center=True)", py)
        self.assertIn('.show("OpenSCAD_Model")', py)

        scad_cyl = "cylinder(r=5, h=25, center=true);"
        py_cyl = transpile_openscad(scad_cyl)
        self.assertIn("Cylinder(r=5, h=25, center=True)", py_cyl)

        scad_sphere = "sphere(r=8);"
        py_sphere = transpile_openscad(scad_sphere)
        self.assertIn("Sphere(r=8)", py_sphere)

    def test_transpile_csg_and_transforms(self):
        scad = """
        difference() {
            cube([40, 40, 15], center=true);
            cylinder(r=8, h=25, center=true);
            translate([10, 0, 0])
                cylinder(r=2, h=20, center=true);
        }
        """
        py = transpile_openscad(scad)
        self.assertIn("Box(length=40, width=40, height=15, center=True)", py)
        self.assertIn("Cylinder(r=8, h=25, center=True)", py)
        self.assertIn(".at(10, 0, 0)", py)
        self.assertIn("-", py)

    def test_transpile_modules_and_loops(self):
        scad = """
        module standoff(x, y) {
            translate([x, y, 0]) cylinder(r=3, h=10, center=true);
        }

        difference() {
            cube([50, 50, 10], center=true);
            for (x = [-15, 15]) {
                standoff(x, 0);
            }
        }
        """
        py = transpile_openscad(scad)
        self.assertIn("def standoff(x, y):", py)
        self.assertIn("for x in [-15, 15]:", py)
        self.assertIn("standoff(x, 0)", py)

    def test_execution_in_freecad(self):
        scad = """
        difference() {
            cube([30, 30, 10], center=true);
            cylinder(r=5, h=20, center=true);
        }
        """
        py = transpile_openscad(scad, model_name="UnitTest_OpenSCAD")

        scope = {
            "__name__": "__main__",
            "App": getattr(sc, "App", None),
            "math": math
        }
        for attr in sc.__all__:
            scope[attr] = getattr(sc, attr)

        exec(py, scope)
        result = scope.get("result")
        self.assertIsNotNone(result)
        self.assertTrue(isinstance(result, sc.ShapeWrapper))
        self.assertTrue(result.is_valid)

        # Expected volume: (30*30*10) - (pi * 5^2 * 10) = 9000 - 785.398 = ~8214.6
        expected_vol = 9000.0 - (math.pi * 25.0 * 10.0)
        self.assertAlmostEqual(result.volume, expected_vol, delta=10.0)


if __name__ == "__main__":
    unittest.main()
