"""
Cross-version PySide compatibility layer for BlendCAD.
Supports PySide6 (FreeCAD 1.0+) and PySide2 (FreeCAD 0.20/0.21).
"""

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal, Slot, QTimer
    from PySide6.QtGui import (
        QColor, QFont, QFontMetrics, QPainter, QSyntaxHighlighter,
        QTextCharFormat, QTextCursor, QTextFormat, QKeySequence, QShortcut, QIcon
    )
    from PySide6.QtWidgets import (
        QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
        QToolBar, QStatusBar, QMessageBox, QFileDialog, QSizePolicy
    )
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        from PySide2.QtCore import Qt, QPoint, QRect, QSize, Signal, Slot, QTimer
        from PySide2.QtGui import (
            QColor, QFont, QFontMetrics, QPainter, QSyntaxHighlighter,
            QTextCharFormat, QTextCursor, QTextFormat, QKeySequence, QShortcut, QIcon
        )
        from PySide2.QtWidgets import (
            QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
            QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
            QToolBar, QStatusBar, QMessageBox, QFileDialog, QSizePolicy
        )
        PYSIDE_VERSION = 2
    except ImportError:
        # Fallback for standalone tests without GUI
        QtCore = QtGui = QtWidgets = None
        PYSIDE_VERSION = 0
