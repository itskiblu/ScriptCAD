# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Cross-version PySide compatibility layer for ScriptCAD.
Supports PySide6 (FreeCAD 1.0+) and PySide2 (FreeCAD 0.20/0.21).
"""

from typing import Any

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal, Slot, QTimer, QRegularExpression
    from PySide6.QtGui import (
        QColor, QFont, QFontMetrics, QPainter, QSyntaxHighlighter,
        QTextCharFormat, QTextCursor, QTextFormat, QKeySequence, QShortcut, QIcon, QAction, QPalette,
        QTextDocument, QGuiApplication
    )
    from PySide6.QtWidgets import (
        QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
        QToolBar, QToolButton, QStatusBar, QMessageBox, QFileDialog, QSizePolicy, QLineEdit, QMenu, QStyle
    )
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        from PySide2.QtCore import Qt, QPoint, QRect, QSize, Signal, Slot, QTimer, QRegularExpression
        from PySide2.QtGui import (
            QColor, QFont, QFontMetrics, QPainter, QSyntaxHighlighter,
            QTextCharFormat, QTextCursor, QTextFormat, QKeySequence, QShortcut, QIcon, QPalette,
            QTextDocument, QGuiApplication
        )
        from PySide2.QtWidgets import (
            QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
            QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
            QToolBar, QToolButton, QStatusBar, QMessageBox, QFileDialog, QSizePolicy, QLineEdit, QMenu, QAction, QStyle
        )
        PYSIDE_VERSION = 2
    except ImportError:
        # Fallback for standalone tests without GUI
        class _DummyQt:
            def __getattr__(self, name: str) -> Any:
                return _DummyQt

            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                return self

        QtCore: Any = _DummyQt()
        QtGui: Any = _DummyQt()
        QtWidgets: Any = _DummyQt()

        Qt: Any = _DummyQt()
        QPoint: Any = _DummyQt
        QRect: Any = _DummyQt
        QSize: Any = _DummyQt
        Signal: Any = _DummyQt
        Slot: Any = _DummyQt
        QTimer: Any = _DummyQt
        QRegularExpression: Any = _DummyQt

        QColor: Any = _DummyQt
        QFont: Any = _DummyQt
        QFontMetrics: Any = _DummyQt
        QPainter: Any = _DummyQt
        QSyntaxHighlighter: Any = object
        QTextCharFormat: Any = _DummyQt
        QTextCursor: Any = _DummyQt
        QTextFormat: Any = _DummyQt
        QKeySequence: Any = _DummyQt
        QShortcut: Any = _DummyQt
        QIcon: Any = _DummyQt
        QAction: Any = _DummyQt
        QPalette: Any = _DummyQt

        QWidget: Any = object
        QDockWidget: Any = object
        QPlainTextEdit: Any = object
        QTextEdit: Any = object
        QPushButton: Any = _DummyQt
        QToolButton: Any = _DummyQt
        QVBoxLayout: Any = _DummyQt
        QHBoxLayout: Any = _DummyQt
        QLabel: Any = _DummyQt
        QComboBox: Any = _DummyQt
        QCheckBox: Any = _DummyQt
        QSplitter: Any = _DummyQt
        QToolBar: Any = _DummyQt
        QStatusBar: Any = _DummyQt
        QMessageBox: Any = _DummyQt
        QFileDialog: Any = _DummyQt
        QSizePolicy: Any = _DummyQt
        QLineEdit: Any = _DummyQt
        QMenu: Any = _DummyQt
        QStyle: Any = _DummyQt

        PYSIDE_VERSION = 0
