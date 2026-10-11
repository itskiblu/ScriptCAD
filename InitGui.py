# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD FreeCAD Workbench Registration:
Initializes the GUI workbench, commands, toolbars, and dock editor.
"""

import os
import sys
import FreeCAD as App
import FreeCADGui as Gui

# Ensure ScriptCAD module directory is in sys.path
_wb_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(App.getUserAppDataDir(), "Mod", "ScriptCAD")
if _wb_dir not in sys.path:
    sys.path.insert(0, _wb_dir)

try:
    from gui.workbench import (
        ScriptCADWorkbench,
        register_all_commands,
        # Backward-compatibility aliases
        BlendCADWorkbench,
        BlendCAD_ToggleEditorCommand,
        BlendCAD_ClearDocCommand,
    )

    # Register all native FreeCAD commands
    register_all_commands()

    # Legacy command aliases for backward compatibility
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("BlendCAD_ToggleEditor", BlendCAD_ToggleEditorCommand())
        Gui.addCommand("BlendCAD_ClearDoc", BlendCAD_ClearDocCommand())

    # Register workbench with FreeCAD GUI
    if hasattr(Gui, "addWorkbench"):
        Gui.addWorkbench(ScriptCADWorkbench())
        if hasattr(App, "Console"):
            App.Console.PrintLog("[ScriptCAD] Workbench successfully registered.\n")
    else:
        if hasattr(App, "Console"):
            App.Console.PrintMessage("[ScriptCAD] Module loaded.\n")
except Exception as e:
    if hasattr(App, "Console"):
        App.Console.PrintError(f"[ScriptCAD] Error loading workbench in InitGui.py: {e}\n")
    else:
        print(f"[ScriptCAD] Error loading workbench in InitGui.py: {e}")
