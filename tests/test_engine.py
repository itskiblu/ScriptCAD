# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Unit tests for ScriptCAD procedural modeling engine and CSG booleans.
"""

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scriptcad as sc
import blendcad as bc


class TestScriptCADCore(unittest.TestCase):
    """Test procedural CAD primitives, boolean operations, and transforms."""

    def test_active_document_creation(self):
        doc = sc.active_document("UnitTest_ScriptCAD")
        self.assertIsNotNone(doc)
        self.assertTrue(hasattr(doc, "Name"))

    def test_primitives_volume(self):
        box = sc.Box(10, 20, 30)
        self.assertAlmostEqual(box.shape.Volume, 10 * 20 * 30, delta=1.0)

        cube = sc.Cube(10)
        self.assertAlmostEqual(cube.shape.Volume, 1000, delta=1.0)

        cyl = sc.Cylinder(r=5, h=20)
        expected_cyl = math.pi * 5 * 5 * 20
        self.assertAlmostEqual(cyl.shape.Volume, expected_cyl, delta=1.0)

        sph = sc.Sphere(r=5)
        expected_sph = (4.0 / 3.0) * math.pi * 5 * 5 * 5
        self.assertAlmostEqual(sph.shape.Volume, expected_sph, delta=1.0)

    def test_csg_boolean_cut(self):
        box = sc.Box(20, 20, 20, center=True)
        hole = sc.Cylinder(r=4, h=30, center=True)
        diff = box - hole
        expected_vol = (20 * 20 * 20) - (math.pi * 4 * 4 * 20)
        self.assertAlmostEqual(diff.shape.Volume, expected_vol, delta=10.0)

    def test_csg_boolean_fuse_and_common(self):
        b1 = sc.Box(10, 10, 10)
        b2 = sc.Box(10, 10, 10).translate(x=5)
        union = b1 + b2
        self.assertAlmostEqual(union.shape.Volume, 1500, delta=5.0)

        inter = b1 & b2
        self.assertAlmostEqual(inter.shape.Volume, 500, delta=5.0)

    def test_transforms_and_arrays(self):
        b = sc.Box(10, 10, 10).rotate_z(45).at(5, 5, 0)
        self.assertAlmostEqual(b.shape.Volume, 1000, delta=1.0)

        # Linear array
        arr = sc.Box(2, 2, 2).linear_array(count=3, step=(5, 0, 0))
        self.assertAlmostEqual(arr.shape.Volume, 24, delta=1.0)

    def test_mesh_art_ripple(self):
        mesh = sc.MeshArt.ripple_plane(size=20, resolution=10, wave_height=2.0)
        self.assertIsNotNone(mesh)
        self.assertTrue(len(mesh.vertices) > 0)
        solid = mesh.solidify(thickness=4.0)
        self.assertGreater(solid.shape.Volume, 0)

    def test_blendcad_backward_compatibility(self):
        self.assertEqual(bc.Box, sc.Box)
        self.assertEqual(bc.Cylinder, sc.Cylinder)
        self.assertEqual(bc.active_document, sc.active_document)
        self.assertEqual(bc.clear_document, sc.clear_document)


if __name__ == "__main__":
    unittest.main()
