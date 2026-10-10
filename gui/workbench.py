"""
BlendCAD GUI Workbench Module:
Encapsulates workbench definition, commands, and dock manager as a clean Python module.
"""

import os
import sys
import FreeCAD as App
import FreeCADGui as Gui

WORKBENCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_PATH = os.path.join(WORKBENCH_DIR, "Resources", "icons", "BlendCAD_Workbench.svg").replace("\\", "/")

# Global dock widget instance
_blendcad_dock = None


def get_or_create_dock():
    """Retrieve or instantiate the BlendCAD scripting dock."""
    global _blendcad_dock
    from gui.editor_dock import BlendCADEditorDock
    from gui.qt_compat import Qt

    main_win = Gui.getMainWindow()
    if main_win is None:
        return None

    if _blendcad_dock is None:
        _blendcad_dock = BlendCADEditorDock(main_win)
        main_win.addDockWidget(Qt.RightDockWidgetArea, _blendcad_dock)
    return _blendcad_dock


class BlendCAD_ToggleEditorCommand:
    """FreeCAD Command to show/hide the BlendCAD scripting panel."""

    def GetResources(self):
        return {
            'Pixmap': ICON_PATH,
            'MenuText': 'BlendCAD Script Editor',
            'ToolTip': 'Toggle the Blender-style interactive script editor dock'
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


class BlendCAD_ClearDocCommand:
    """FreeCAD Command to clear active document."""

    def GetResources(self):
        return {
            'MenuText': 'Clear Active Document',
            'ToolTip': 'Quickly remove all objects from the active document'
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        from blendcad import clear_document
        clear_document()


# Base Workbench class (FreeCAD GUI provides Workbench / Gui.Workbench)
try:
    _BaseWB = Workbench
except NameError:
    _BaseWB = getattr(Gui, "Workbench", object)


class BlendCADWorkbench(_BaseWB):
    """The BlendCAD Workbench for FreeCAD."""

    MenuText = "BlendCAD"
    ToolTip = "Blender-style procedural CAD & 3D mesh art scripting"
    Icon = ICON_PATH

    def __init__(self):
        self.__class__.Icon = ICON_PATH
        self.__class__.MenuText = "BlendCAD"
        self.__class__.ToolTip = "Blender-style procedural CAD & 3D mesh art scripting"

    def Initialize(self):
        """Construct toolbars and menus for BlendCAD."""
        try:
            Gui.addCommand('BlendCAD_ToggleEditor', BlendCAD_ToggleEditorCommand())
            Gui.addCommand('BlendCAD_ClearDoc', BlendCAD_ClearDocCommand())
        except Exception:
            pass

        self.command_list = ['BlendCAD_ToggleEditor', 'BlendCAD_ClearDoc']
        self.appendToolbar("BlendCAD Tools", self.command_list)
        self.appendMenu("BlendCAD", self.command_list)

    def Activated(self):
        """Called automatically when switching to BlendCAD workbench."""
        try:
            dock = get_or_create_dock()
            if dock is not None:
                dock.show()
                dock.raise_()
        except Exception as e:
            App.Console.PrintError(f"[BlendCAD] Error opening dock on activation: {e}\n")

    def Deactivated(self):
        """Called when user switches away to another workbench."""
        pass

    def ContextMenu(self, recipient):
        self.appendContextMenu("BlendCAD", self.command_list)

    def GetClassName(self):
        return "Gui::PythonWorkbench"
