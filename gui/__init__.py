# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

from .qt_compat import PYSIDE_VERSION
from .highlighter import PythonHighlighter
from .editor_dock import ScriptCADEditorDock, BlendCADEditorDock

__all__ = ["PYSIDE_VERSION", "PythonHighlighter", "ScriptCADEditorDock", "BlendCADEditorDock"]
