"""
ScriptCAD GUI Workbench Module:
Encapsulates workbench definition, commands, and dock manager as a clean Python module.
"""

import os
import sys
import FreeCAD as App
import FreeCADGui as Gui

WORKBENCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(WORKBENCH_DIR, "Resources", "icons", "ScriptCAD_Workbench.svg").replace("\\", "/")

# Global dock widget instance
_scriptcad_dock = None


def get_or_create_dock():
    """Retrieve or instantiate the ScriptCAD scripting dock."""
    global _scriptcad_dock
    from gui.editor_dock import ScriptCADEditorDock
    from gui.qt_compat import Qt

    main_win = Gui.getMainWindow()
    if main_win is None:
        return None

    if _scriptcad_dock is None:
        _scriptcad_dock = ScriptCADEditorDock(main_win)
        main_win.addDockWidget(Qt.RightDockWidgetArea, _scriptcad_dock)
    return _scriptcad_dock


class ScriptCAD_ToggleEditorCommand:
    """FreeCAD Command to show/hide the ScriptCAD scripting panel."""

    def GetResources(self):
        return {
            'Pixmap': ICON_PATH,
            'MenuText': 'ScriptCAD Script Editor',
            'ToolTip': 'Toggle the interactive ScriptCAD script editor dock'
        }

    def IsActive(self):
        return True

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            if dock.isVisible():
                dock.hide()
            else:
                dock.show()
                dock.raise_()


class ScriptCAD_ClearDocCommand:
    """FreeCAD Command to clear active document."""

    def GetResources(self):
        return {
            'MenuText': 'Clear Active Document',
            'ToolTip': 'Quickly remove all objects from the active document'
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from scriptcad import clear_document
        clear_document()


class ScriptCADWorkbench:
    """The ScriptCAD Workbench for FreeCAD."""

    MenuText = "ScriptCAD"
    ToolTip = "Procedural solid modeling & mesh art scripting workbench"
    Icon = ICON_PATH

    def __init__(self):
        self.__class__.Icon = ICON_PATH
        self.__class__.MenuText = "ScriptCAD"
        self.__class__.ToolTip = "Procedural solid modeling & mesh art scripting workbench"
        self.command_list: list = []

    def appendToolbar(self, name: str, cmds: list):
        """FreeCAD GUI provides this at runtime; stub ensures headless safety."""
        pass

    def appendMenu(self, name: str, cmds: list):
        """FreeCAD GUI provides this at runtime; stub ensures headless safety."""
        pass

    def appendContextMenu(self, name: str, cmds: list):
        """FreeCAD GUI provides this at runtime; stub ensures headless safety."""
        pass

    def Initialize(self):
        """Construct toolbars and menus for ScriptCAD."""
        try:
            Gui.addCommand('ScriptCAD_ToggleEditor', ScriptCAD_ToggleEditorCommand())
            Gui.addCommand('ScriptCAD_ClearDoc', ScriptCAD_ClearDocCommand())
        except Exception:
            pass

        self.command_list = ['ScriptCAD_ToggleEditor', 'ScriptCAD_ClearDoc']
        self.appendToolbar("ScriptCAD Tools", self.command_list)
        self.appendMenu("ScriptCAD", self.command_list)

    def Activated(self):
        """Called automatically when switching to ScriptCAD workbench."""
        try:
            dock = get_or_create_dock()
            if dock is not None:
                dock.show()
                dock.raise_()
        except Exception as e:
            App.Console.PrintError(f"[ScriptCAD] Error opening dock on activation: {e}\n")

    def Deactivated(self):
        """Called when user switches away to another workbench."""
        pass

    def ContextMenu(self, recipient):
        self.appendContextMenu("ScriptCAD", self.command_list)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


# Backward-compatibility aliases
BlendCADWorkbench = ScriptCADWorkbench
BlendCAD_ToggleEditorCommand = ScriptCAD_ToggleEditorCommand
BlendCAD_ClearDocCommand = ScriptCAD_ClearDocCommand
