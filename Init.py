# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD FreeCAD Module Initialization:
Executed during FreeCAD's application startup phase (both GUI and console mode).
Ensures the scriptcad package is importable across FreeCAD.
"""

import os
import sys
import FreeCAD as App

_mod_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(App.getUserAppDataDir(), "Mod", "ScriptCAD")
if _mod_dir not in sys.path:
    sys.path.insert(0, _mod_dir)

if hasattr(App, "Console"):
    App.Console.PrintLog("[ScriptCAD] Core module initialized.\n")
