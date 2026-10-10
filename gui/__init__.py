from .qt_compat import PYSIDE_VERSION
from .highlighter import PythonHighlighter
from .editor_dock import ScriptCADEditorDock, BlendCADEditorDock

__all__ = ["PYSIDE_VERSION", "PythonHighlighter", "ScriptCADEditorDock", "BlendCADEditorDock"]
