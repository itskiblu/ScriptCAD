# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD GUI Workbench Module:
Encapsulates native FreeCAD workbench definition, commands, menus, toolbars,
and dock manager according to FreeCAD GUI standards.
"""

import os
import sys
import FreeCAD as App
import FreeCADGui as Gui


def translate(context: str, text: str, disambiguation: str = None) -> str:
    """Translate user-visible string according to FreeCAD Developer Handbook standards."""
    try:
        return App.Qt.translate(context, text, disambiguation)
    except Exception:
        return text


WORKBENCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_icon(name: str) -> str:
    """Return normalized absolute path to a workbench SVG icon."""
    return os.path.join(WORKBENCH_DIR, "Resources", "icons", name).replace("\\", "/")


ICON_WORKBENCH = get_icon("ScriptCAD_Workbench.svg")
ICON_RUN = get_icon("ScriptCAD_Run.svg")
ICON_NEW = get_icon("ScriptCAD_New.svg")
ICON_OPEN = get_icon("ScriptCAD_Open.svg")
ICON_SAVE = get_icon("ScriptCAD_Save.svg")
ICON_TO_BODY = get_icon("ScriptCAD_ToBody.svg")
ICON_EXPORT = get_icon("ScriptCAD_Export.svg")
ICON_CLEAR = get_icon("ScriptCAD_Clear.svg")

# Global dock widget reference
_scriptcad_dock = None


def get_or_create_dock():
    """Retrieve or instantiate the ScriptCAD scripting dock widget."""
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


# =============================================================================
# FreeCAD Native Commands
# =============================================================================

class ScriptCAD_ToggleEditorCommand:
    """FreeCAD Command to show/hide the ScriptCAD scripting dock."""

    def GetResources(self):
        return {
            'Pixmap': ICON_WORKBENCH,
            'MenuText': translate('ScriptCAD', 'Script Editor'),
            'ToolTip': translate('ScriptCAD', 'Toggles the interactive ScriptCAD code editor panel')
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


class ScriptCAD_RunCommand:
    """FreeCAD Command to execute the current script in the editor."""

    def GetResources(self):
        return {
            'Pixmap': ICON_RUN,
            'MenuText': translate('ScriptCAD', 'Run Script'),
            'ToolTip': translate('ScriptCAD', 'Executes the active script (Alt+P)'),
            'Accel': 'Alt+P'
        }

    def IsActive(self):
        dock = get_or_create_dock()
        return dock is not None and bool(dock.editor.toPlainText().strip())

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            if not dock.isVisible():
                dock.show()
                dock.raise_()
            dock.execute_script()


class ScriptCAD_NewCommand:
    """FreeCAD Command to create a new blank script."""

    def GetResources(self):
        return {
            'Pixmap': ICON_NEW,
            'MenuText': translate('ScriptCAD', 'New Script'),
            'ToolTip': translate('ScriptCAD', 'Creates a new blank script (Ctrl+N)'),
            'Accel': 'Ctrl+N'
        }

    def IsActive(self):
        return True

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            if not dock.isVisible():
                dock.show()
                dock.raise_()
            dock.new_script()


class ScriptCAD_OpenCommand:
    """FreeCAD Command to open an existing script file."""

    def GetResources(self):
        return {
            'Pixmap': ICON_OPEN,
            'MenuText': translate('ScriptCAD', 'Open Script...'),
            'ToolTip': translate('ScriptCAD', 'Opens a Python CAD script from disk (Ctrl+O)'),
            'Accel': 'Ctrl+O'
        }

    def IsActive(self):
        return True

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            if not dock.isVisible():
                dock.show()
                dock.raise_()
            dock.open_script()


class ScriptCAD_SaveCommand:
    """FreeCAD Command to save current script."""

    def GetResources(self):
        return {
            'Pixmap': ICON_SAVE,
            'MenuText': translate('ScriptCAD', 'Save Script'),
            'ToolTip': translate('ScriptCAD', 'Saves the active script to disk (Ctrl+S)'),
            'Accel': 'Ctrl+S'
        }

    def IsActive(self):
        dock = get_or_create_dock()
        return dock is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.save_script()


class ScriptCAD_SaveAsCommand:
    """FreeCAD Command to save current script to a new file."""

    def GetResources(self):
        return {
            'Pixmap': ICON_SAVE,
            'MenuText': translate('ScriptCAD', 'Save Script As...'),
            'ToolTip': translate('ScriptCAD', 'Saves the current script under a new filename')
        }

    def IsActive(self):
        dock = get_or_create_dock()
        return dock is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.save_script_as()


class ScriptCAD_ToBodyCommand:
    """FreeCAD Command to wrap selected/active Part solid into a PartDesign Body."""

    def GetResources(self):
        return {
            'Pixmap': ICON_TO_BODY,
            'MenuText': translate('ScriptCAD', 'Convert to PartDesign Body'),
            'ToolTip': translate('ScriptCAD', 'Wraps selected solid into an active PartDesign Body container')
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.convert_selection_to_body()
        else:
            import scriptcad
            scriptcad.convert_to_body()


class ScriptCAD_ExportSTEPCommand:
    """FreeCAD Command to export active solid to STEP file."""

    def GetResources(self):
        return {
            'Pixmap': ICON_EXPORT,
            'MenuText': translate('ScriptCAD', 'Export to STEP...'),
            'ToolTip': translate('ScriptCAD', 'Exports selected or active solid to a STEP CAD file (.step / .stp)')
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.export_model("step")


class ScriptCAD_ExportSTLCommand:
    """FreeCAD Command to export active solid to STL mesh."""

    def GetResources(self):
        return {
            'Pixmap': ICON_EXPORT,
            'MenuText': translate('ScriptCAD', 'Export to STL...'),
            'ToolTip': translate('ScriptCAD', 'Exports selected or active solid to an STL mesh file (.stl)')
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.export_model("stl")


class ScriptCAD_ExportOBJCommand:
    """FreeCAD Command to export active solid to OBJ mesh."""

    def GetResources(self):
        return {
            'Pixmap': ICON_EXPORT,
            'MenuText': translate('ScriptCAD', 'Export to OBJ...'),
            'ToolTip': translate('ScriptCAD', 'Exports selected or active solid to a Wavefront OBJ mesh file (.obj)')
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.export_model("obj")


class ScriptCAD_ClearDocCommand:
    """FreeCAD Command to clear active document."""

    def GetResources(self):
        return {
            'Pixmap': ICON_CLEAR,
            'MenuText': translate('ScriptCAD', 'Clear Active Document'),
            'ToolTip': translate('ScriptCAD', 'Removes all objects from the active document')
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        dock = get_or_create_dock()
        if dock is not None:
            dock.clear_document()
        else:
            from scriptcad import clear_document
            clear_document()


# =============================================================================
# FreeCAD Workbench Registration
# =============================================================================

try:
    _BaseWB = Workbench  # type: ignore[name-defined]
except NameError:
    _BaseWB = getattr(Gui, "Workbench", object)


ALL_COMMANDS = {
    'ScriptCAD_ToggleEditor': ScriptCAD_ToggleEditorCommand(),
    'ScriptCAD_Run': ScriptCAD_RunCommand(),
    'ScriptCAD_New': ScriptCAD_NewCommand(),
    'ScriptCAD_Open': ScriptCAD_OpenCommand(),
    'ScriptCAD_Save': ScriptCAD_SaveCommand(),
    'ScriptCAD_SaveAs': ScriptCAD_SaveAsCommand(),
    'ScriptCAD_ToBody': ScriptCAD_ToBodyCommand(),
    'ScriptCAD_ExportSTEP': ScriptCAD_ExportSTEPCommand(),
    'ScriptCAD_ExportSTL': ScriptCAD_ExportSTLCommand(),
    'ScriptCAD_ExportOBJ': ScriptCAD_ExportOBJCommand(),
    'ScriptCAD_ClearDoc': ScriptCAD_ClearDocCommand(),
}


def register_all_commands():
    """Register all ScriptCAD commands with FreeCAD GUI."""
    if hasattr(Gui, "addCommand"):
        for cmd_name, cmd_obj in ALL_COMMANDS.items():
            try:
                Gui.addCommand(cmd_name, cmd_obj)
            except Exception:
                pass


class ScriptCADWorkbench(_BaseWB):
    """The native ScriptCAD Workbench for FreeCAD."""

    MenuText = translate("ScriptCAD", "ScriptCAD")
    ToolTip = translate("ScriptCAD", "Procedural solid modeling & mesh art scripting workbench")
    Icon = ICON_WORKBENCH

    def __init__(self):
        self.__class__.Icon = ICON_WORKBENCH
        self.__class__.MenuText = translate("ScriptCAD", "ScriptCAD")
        self.__class__.ToolTip = translate("ScriptCAD", "Procedural solid modeling & mesh art scripting workbench")

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
        """Construct native FreeCAD toolbars and menus."""
        register_all_commands()

        # 1. ScriptCAD Scripting Toolbar
        self.appendToolbar("ScriptCAD Scripting", [
            'ScriptCAD_ToggleEditor',
            'ScriptCAD_Run'
        ])

        # 2. ScriptCAD File Toolbar
        self.appendToolbar("ScriptCAD File", [
            'ScriptCAD_New',
            'ScriptCAD_Open',
            'ScriptCAD_Save'
        ])

        # 3. ScriptCAD Solid & Export Toolbar
        self.appendToolbar("ScriptCAD Solid & Export", [
            'ScriptCAD_ToBody',
            'ScriptCAD_ExportSTEP',
            'ScriptCAD_ExportSTL',
            'ScriptCAD_ExportOBJ',
            'ScriptCAD_ClearDoc'
        ])

        # 4. Main Menu Bar entry
        self.appendMenu("ScriptCAD", [
            'ScriptCAD_ToggleEditor',
            'ScriptCAD_Run',
            'Separator',
            'ScriptCAD_New',
            'ScriptCAD_Open',
            'ScriptCAD_Save',
            'ScriptCAD_SaveAs',
            'Separator',
            'ScriptCAD_ToBody',
            'ScriptCAD_ExportSTEP',
            'ScriptCAD_ExportSTL',
            'ScriptCAD_ExportOBJ',
            'Separator',
            'ScriptCAD_ClearDoc'
        ])

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
        self.appendContextMenu("ScriptCAD", [
            'ScriptCAD_ToggleEditor',
            'ScriptCAD_Run',
            'ScriptCAD_ToBody',
            'ScriptCAD_ClearDoc'
        ])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


# Backward-compatibility aliases
BlendCADWorkbench = ScriptCADWorkbench
BlendCAD_ToggleEditorCommand = ScriptCAD_ToggleEditorCommand
BlendCAD_ClearDocCommand = ScriptCAD_ClearDocCommand
