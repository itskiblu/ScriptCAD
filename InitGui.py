"""
ScriptCAD FreeCAD Workbench Registration:
Initializes the workbench, dockable script editor panel, commands, and toolbar.
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
        ScriptCAD_ToggleEditorCommand,
        ScriptCAD_ClearDocCommand,
        # Backward-compat aliases
        BlendCADWorkbench,
        BlendCAD_ToggleEditorCommand,
        BlendCAD_ClearDocCommand,
    )

    if hasattr(Gui, "addCommand"):
        Gui.addCommand("ScriptCAD_ToggleEditor", ScriptCAD_ToggleEditorCommand())
        Gui.addCommand("ScriptCAD_ClearDoc", ScriptCAD_ClearDocCommand())
        # Alias old command names for safety
        Gui.addCommand("BlendCAD_ToggleEditor", BlendCAD_ToggleEditorCommand())
        Gui.addCommand("BlendCAD_ClearDoc", BlendCAD_ClearDocCommand())

    if hasattr(Gui, "addWorkbench"):
        Gui.addWorkbench(ScriptCADWorkbench())
    else:
        print("[ScriptCAD] Module loaded. (Workbench will register in FreeCAD GUI)")
except Exception as e:
    App.Console.PrintError(f"[ScriptCAD] Error loading workbench in InitGui.py: {e}\n")
