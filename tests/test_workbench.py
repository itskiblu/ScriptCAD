# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Unit tests for FreeCAD GUI Workbench and Command registration.
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestWorkbenchRegistration(unittest.TestCase):
    """Test Init.py, InitGui.py, and Workbench definitions."""

    def test_init_module_execution(self):
        import Init
        self.assertIn(REPO_ROOT, sys.path)

    def test_init_gui_module_and_workbench_class(self):
        import InitGui
        self.assertTrue(hasattr(InitGui, "ScriptCADWorkbench"))
        wb_cls = getattr(InitGui, "ScriptCADWorkbench")
        self.assertTrue(hasattr(wb_cls, "Icon"))
        self.assertTrue(hasattr(wb_cls, "MenuText"))
        self.assertTrue(hasattr(wb_cls, "ToolTip"))
        self.assertTrue(os.path.exists(wb_cls.Icon), f"Workbench icon not found: {wb_cls.Icon}")

    def test_all_gui_commands_defined(self):
        from gui.workbench import ALL_COMMANDS
        self.assertGreater(len(ALL_COMMANDS), 5)
        for cmd_name, cmd_obj in ALL_COMMANDS.items():
            self.assertTrue(hasattr(cmd_obj, "GetResources"), f"Command {cmd_name} missing GetResources")
            res = cmd_obj.GetResources()
            self.assertIn("Pixmap", res, f"Command {cmd_name} missing Pixmap")
            self.assertIn("MenuText", res, f"Command {cmd_name} missing MenuText")
            self.assertIn("ToolTip", res, f"Command {cmd_name} missing ToolTip")
            pixmap = res["Pixmap"]
            # Pixmap can be an absolute path or Qt resource (:/icons/...)
            if not pixmap.startswith(":/"):
                self.assertTrue(os.path.exists(pixmap), f"Pixmap for {cmd_name} not found: {pixmap}")


if __name__ == "__main__":
    unittest.main()
