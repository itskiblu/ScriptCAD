# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Unit tests for the ScriptCAD Model Decompiler engine.
Tests reverse-engineering of FreeCAD CSG primitives, booleans, transforms,
PartDesign bodies, and round-trip code execution.
"""

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import scriptcad as sc
from scriptcad.decompiler import decompile, ModelDecompiler

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None


class TestModelDecompiler(unittest.TestCase):
    """Test suite for decompile() and ModelDecompiler."""

    def setUp(self):
        if App is not None:
            self.doc = App.newDocument("UnitTest_Decompile")
        else:
            self.doc = None

    def tearDown(self):
        if App is not None and self.doc is not None:
            try:
                App.closeDocument(self.doc.Name)
            except Exception:
                pass

    def test_decompile_box_primitive(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "MyBox")
        b.Length = 30.0
        b.Width = 20.0
        b.Height = 10.0
        self.doc.recompute()

        code = decompile(b, doc=self.doc)
        self.assertIn("Box(length=30.0, width=20.0, height=10.0)", code)
        self.assertIn("my_box.show(\"MyBox\")", code)

    def test_decompile_cube_primitive(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        c = self.doc.addObject("Part::Box", "MyCube")
        c.Length = 15.0
        c.Width = 15.0
        c.Height = 15.0
        self.doc.recompute()

        code = decompile(c, doc=self.doc)
        self.assertIn("Cube(size=15.0)", code)

    def test_decompile_cylinder_primitive(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        cyl = self.doc.addObject("Part::Cylinder", "Pin")
        cyl.Radius = 4.5
        cyl.Height = 25.0
        self.doc.recompute()

        code = decompile(cyl, doc=self.doc)
        self.assertIn("Cylinder(radius=4.5, height=25.0)", code)

    def test_decompile_csg_cut(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "BaseBlock")
        b.Length = 40.0
        b.Width = 40.0
        b.Height = 20.0

        hole = self.doc.addObject("Part::Cylinder", "Hole")
        hole.Radius = 6.0
        hole.Height = 30.0
        hole.Placement.Base = App.Vector(20.0, 20.0, -5.0)

        cut = self.doc.addObject("Part::Cut", "PerforatedBlock")
        cut.Base = b
        cut.Tool = hole
        self.doc.recompute()

        code = decompile(cut, doc=self.doc)
        self.assertIn("base_block = Box(length=40.0, width=40.0, height=20.0)", code)
        self.assertIn("hole = Cylinder(radius=6.0, height=30.0).at(20.0, 20.0, -5.0)", code)
        self.assertIn("perforated_block = base_block - hole", code)

    def test_decompile_csg_fuse_and_common(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        b1 = self.doc.addObject("Part::Box", "PartA")
        b1.Length = 10.0
        b1.Width = 10.0
        b1.Height = 10.0

        b2 = self.doc.addObject("Part::Box", "PartB")
        b2.Length = 10.0
        b2.Width = 10.0
        b2.Height = 10.0
        b2.Placement.Base = App.Vector(5.0, 0.0, 0.0)

        fuse = self.doc.addObject("Part::Fuse", "UnionParts")
        fuse.Base = b1
        fuse.Tool = b2
        self.doc.recompute()

        code = decompile(fuse, doc=self.doc)
        self.assertIn("part_a + part_b", code)

        common = self.doc.addObject("Part::Common", "IntersectParts")
        common.Base = b1
        common.Tool = b2
        self.doc.recompute()

        code_comm = decompile(common, doc=self.doc)
        self.assertIn("part_a & part_b", code_comm)

    def test_decompile_transformed_object(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "RotatedBox")
        b.Length = 10.0
        b.Width = 10.0
        b.Height = 10.0
        b.Placement.Base = App.Vector(5.0, 10.0, 15.0)
        b.Placement.Rotation = App.Rotation(App.Vector(0, 0, 1), 45.0)
        self.doc.recompute()

        code = decompile(b, doc=self.doc)
        self.assertIn(".rotate_z(45.0)", code)
        self.assertIn(".at(5.0, 10.0, 15.0)", code)

    def test_decompile_fillet(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "Block")
        b.Length = 20.0
        b.Width = 20.0
        b.Height = 20.0
        self.doc.recompute()

        f = self.doc.addObject("Part::Fillet", "RoundedBlock")
        f.Base = b
        f.Edges = [(1, 2.5, 2.5)]
        self.doc.recompute()

        code = decompile(f, doc=self.doc)
        self.assertIn(".fillet(radius=2.5", code)

    def test_decompile_partdesign_pad(self):
        if App is None:
            self.skipTest("FreeCAD not available")

        body = self.doc.addObject("PartDesign::Body", "GearBody")
        sk = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        body.addObject(sk)
        sk.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 12.0))
        self.doc.recompute()

        pad = self.doc.addObject("PartDesign::Pad", "PadFeature")
        pad.Profile = sk
        pad.Length = 18.0
        body.addObject(pad)
        self.doc.recompute()

        code = decompile(body, doc=self.doc)
        self.assertIn("Circle(radius=12.0", code)
        self.assertIn(".extrude(18.0)", code)

    def test_round_trip_execution_volume(self):
        """Verify that decompiled code executes and creates a matching solid."""
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "OriginalBox")
        b.Length = 25.0
        b.Width = 20.0
        b.Height = 15.0

        c = self.doc.addObject("Part::Cylinder", "OriginalCyl")
        c.Radius = 5.0
        c.Height = 20.0
        c.Placement.Base = App.Vector(12.5, 10.0, -2.0)

        cut = self.doc.addObject("Part::Cut", "OriginalCut")
        cut.Base = b
        cut.Tool = c
        self.doc.recompute()

        orig_vol = cut.Shape.Volume

        # Decompile to script
        script = decompile(cut, doc=self.doc)

        # Execute script in sandbox
        sandbox = {}
        exec(script, sandbox)

        # The sandbox should contain the final variable
        res = sandbox.get("original_cut")
        self.assertIsNotNone(res)
        self.assertTrue(isinstance(res, sc.ShapeWrapper))
        self.assertAlmostEqual(res.shape.Volume, orig_vol, delta=0.5)

    def test_prismatic_detection_dumb_solid(self):
        """Test reverse-engineering an unparameterized Part::Feature box."""
        if App is None or Part is None:
            self.skipTest("FreeCAD not available")

        # Create raw Part::Feature without Box properties
        feat = self.doc.addObject("Part::Feature", "DumbSolid")
        feat.Shape = Part.makeBox(35.0, 25.0, 15.0)
        self.doc.recompute()

        code = decompile(feat, doc=self.doc)
        self.assertIn("Box(length=35.0, width=25.0, height=15.0)", code)

    def test_prismatic_cylinder_detection(self):
        """Test reverse-engineering an unparameterized Part::Feature cylinder."""
        if App is None or Part is None:
            self.skipTest("FreeCAD not available")

        feat = self.doc.addObject("Part::Feature", "DumbCylinder")
        feat.Shape = Part.makeCylinder(7.0, 30.0)
        self.doc.recompute()

        code = decompile(feat, doc=self.doc)
        self.assertIn("Cylinder(radius=7.0, height=30.0)", code)

    def test_decompile_expression_engine(self):
        """Test extracting parametric variables from object expressions."""
        if App is None:
            self.skipTest("FreeCAD not available")

        b = self.doc.addObject("Part::Box", "ParamBox")
        b.Length = 50.0
        b.Width = 30.0
        b.Height = 10.0
        # Bind expression
        b.setExpression("Length", "custom_plate_length")
        self.doc.recompute()

        code = decompile(b, doc=self.doc)
        self.assertIn("custom_plate_length = 50.0", code)
        self.assertIn("Box(length=custom_plate_length, width=30.0, height=10.0)", code)

    def test_decompile_complex_partdesign_chain(self):
        """Test full feature tree chaining: Pad -> Fillet -> Pocket -> Chamfer."""
        if App is None or Part is None:
            self.skipTest("FreeCAD not available")

        body = self.doc.addObject("PartDesign::Body", "MultiFeatureBody")
        sk1 = self.doc.addObject("Sketcher::SketchObject", "BaseSketch")
        body.addObject(sk1)
        sk1.addGeometry(Part.LineSegment(App.Vector(-10, -10, 0), App.Vector(10, -10, 0)))
        sk1.addGeometry(Part.LineSegment(App.Vector(10, -10, 0), App.Vector(10, 10, 0)))
        sk1.addGeometry(Part.LineSegment(App.Vector(10, 10, 0), App.Vector(-10, 10, 0)))
        sk1.addGeometry(Part.LineSegment(App.Vector(-10, 10, 0), App.Vector(-10, -10, 0)))
        self.doc.recompute()

        pad = self.doc.addObject("PartDesign::Pad", "BasePad")
        pad.Profile = sk1
        pad.Length = 15.0
        body.addObject(pad)
        self.doc.recompute()

        fillet = self.doc.addObject("PartDesign::Fillet", "EdgeFillet")
        fillet.Base = (pad, ["Edge1"])
        fillet.Radius = 2.0
        body.addObject(fillet)
        self.doc.recompute()

        code = decompile(body, doc=self.doc)
        self.assertIn("multi_feature_body", code)
        self.assertIn(".fillet(radius=2.0", code)

    def test_decompile_whole_model_when_no_selection(self):
        """Test that passing None or [] automatically decompiles the entire model."""
        if App is None or Part is None:
            self.skipTest("FreeCAD not available")

        # Create a body in document
        body = self.doc.addObject("PartDesign::Body", "AutoWholeModelBody")
        sk = self.doc.addObject("Sketcher::SketchObject", "SquareSketch")
        body.addObject(sk)
        sk.addGeometry(Part.LineSegment(App.Vector(-5, -5, 0), App.Vector(5, -5, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(5, -5, 0), App.Vector(5, 5, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(5, 5, 0), App.Vector(-5, 5, 0)))
        sk.addGeometry(Part.LineSegment(App.Vector(-5, 5, 0), App.Vector(-5, -5, 0)))
        self.doc.recompute()

        pad = self.doc.addObject("PartDesign::Pad", "AutoPad")
        pad.Profile = sk
        pad.Length = 10.0
        body.addObject(pad)
        self.doc.recompute()

        # Call with None (simulates nothing selected in 3D view / tree)
        code_none = decompile(None, doc=self.doc)
        self.assertIn("entire 3D model", code_none)
        self.assertIn("auto_whole_model_body", code_none)
        self.assertIn('.show("AutoWholeModelBody")', code_none)

        # Call with empty list []
        code_empty = decompile([], doc=self.doc)
        self.assertIn("entire 3D model", code_empty)
        self.assertIn("auto_whole_model_body", code_empty)

    def test_decompile_whole_model_multi_body(self):
        """Test whole model decompilation with multiple top-level bodies in the document."""
        if App is None:
            self.skipTest("FreeCAD not available")

        b1 = self.doc.addObject("Part::Box", "MainChassis")
        b1.Length = 50.0
        b1.Width = 30.0
        b1.Height = 10.0

        b2 = self.doc.addObject("Part::Cylinder", "MountingPillar")
        b2.Radius = 5.0
        b2.Height = 20.0
        self.doc.recompute()

        code = decompile(None, doc=self.doc)
        self.assertIn("entire 3D model", code)
        self.assertIn("main_chassis", code)
        self.assertIn("mounting_pillar", code)
        self.assertIn('.show("MainChassis")', code)
        self.assertIn('.show("MountingPillar")', code)

    def test_decompile_real_wall_mount_model(self):
        """Test decompiling user's real-world Wall mount model if present and executing the code."""
        wall_mount_path = "C:/Users/brian/3D Objects/Wall mount.FCStd"
        if not os.path.exists(wall_mount_path) or App is None:
            self.skipTest("Wall mount.FCStd not present")

        doc = App.openDocument(wall_mount_path)
        try:
            # 1. Test decompiling specific Body object
            code = decompile(doc.Body, doc=doc)
            self.assertIn("body = Rectangle", code)
            self.assertIn("body -= Cylinder", code)
            self.assertIn("body += Rectangle", code)
            self.assertIn("body += Polygon", code)
            self.assertIn("body = body.fillet", code)
            self.assertIn("body = body.chamfer", code)
            self.assertIn('.show("Body")', code)

            # 2. Test decompiling when NO object is selected (whole model)
            code_whole = decompile(None, doc=doc)
            self.assertIn("entire 3D model", code_whole)
            self.assertIn("body = Rectangle", code_whole)
            self.assertIn('.show("Body")', code_whole)

            # 3. Test round-trip execution of the decompiled script in a temp document
            temp_doc = App.newDocument("TempExecutionDoc")
            try:
                exec_globals = {name: getattr(sc, name) for name in dir(sc) if not name.startswith("_")}
                exec_locals = {}
                exec(code, exec_globals, exec_locals)
                self.assertIn("body", exec_locals)
                res_body = exec_locals["body"]

                target_vol = doc.getObject("Fillet008").Shape.Volume
                self.assertAlmostEqual(res_body.shape.Volume, target_vol, places=2)
                bb = res_body.shape.BoundBox
                self.assertAlmostEqual(bb.XMin, -7.5, places=1)
                self.assertAlmostEqual(bb.XMax, 7.5, places=1)
                self.assertAlmostEqual(bb.YMin, -15.0, places=1)
                self.assertAlmostEqual(bb.YMax, 15.0, places=1)
                self.assertAlmostEqual(bb.ZMin, 0.0, places=1)
                self.assertAlmostEqual(bb.ZMax, 30.0, places=1)
            finally:
                App.closeDocument(temp_doc.Name)
        finally:
            App.closeDocument(doc.Name)


if __name__ == "__main__":
    unittest.main()


