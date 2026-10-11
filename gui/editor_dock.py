# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Interactive Scripting Dock:
Native FreeCAD dockable code editor with live sync, syntax highlighting,
line numbers, file management (New/Open/Save/Save As), in-editor find/replace,
font zoom, direct export (STEP/STL/OBJ), and instant execution.
Fully integrated with FreeCAD's native UI elements, theme palette, and preferences.
"""

import sys
import os
import time
import traceback
import io
from typing import Any, Optional
from contextlib import redirect_stdout, redirect_stderr

from .qt_compat import (
    QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
    QToolBar, QToolButton, QColor, QFont, QPainter, QRect, QSize, QTextFormat,
    Qt, QTimer, QKeySequence, QShortcut, QFileDialog, QMessageBox,
    QLineEdit, QMenu, QAction, QIcon, QSizePolicy, QPalette
)
from .highlighter import PythonHighlighter

try:
    import FreeCAD as App
    import FreeCADGui as Gui
except ImportError:
    App = None
    Gui = None


def translate(context: str, text: str, disambiguation: str = None) -> str:
    """Translate user-visible string according to FreeCAD Developer Handbook standards."""
    if App is not None and hasattr(App, "Qt") and hasattr(App.Qt, "translate"):
        try:
            return App.Qt.translate(context, text, disambiguation)
        except Exception:
            pass
    return text


WORKBENCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_icon_path(name: str) -> str:
    """Return normalized path to an icon in Resources/icons."""
    return os.path.join(WORKBENCH_DIR, "Resources", "icons", name).replace("\\", "/")


def get_workbench_icon(local_name: str, *freecad_names: str) -> str:
    """Return native FreeCAD icon resource path if registered in Qt, otherwise local SVG path."""
    for fn in freecad_names:
        if fn:
            res_path = f":/icons/{fn}" if not fn.startswith(":/") else fn
            if not QIcon(res_path).isNull():
                return res_path
    return get_icon_path(local_name)


ICON_RUN = get_workbench_icon("ScriptCAD_Run.svg", "media-playback-start.svg", "Std_DlgMacroExecuteDirect.svg")
ICON_LIVE = get_workbench_icon("ScriptCAD_Live.svg")
ICON_NEW = get_workbench_icon("ScriptCAD_New.svg", "document-new.svg")
ICON_OPEN = get_workbench_icon("ScriptCAD_Open.svg", "document-open.svg")
ICON_SAVE = get_workbench_icon("ScriptCAD_Save.svg", "document-save.svg")
ICON_TO_BODY = get_workbench_icon("ScriptCAD_ToBody.svg", "PartDesign_Body.svg")
ICON_EXPORT = get_workbench_icon("ScriptCAD_Export.svg", "Std_Export.svg")
ICON_CLEAR = get_workbench_icon("ScriptCAD_Clear.svg")
ICON_FIND = get_workbench_icon("ScriptCAD_Find.svg", "edit-find.svg", "zoom-fit-best.svg")
ICON_TEMPLATES = get_workbench_icon("ScriptCAD_Templates.svg", "MacroEditor.svg", "applications-python.svg")
ICON_CONSOLE = get_workbench_icon("ScriptCAD_Console.svg")
ICON_MENU_ARROW = get_icon_path("menu_arrow.svg")


def _get_editor_pref(key: str, default: Any) -> Any:
    """Read a setting from FreeCAD's user editor preferences."""
    if App is None:
        return default
    try:
        pref = App.ParamGet("User parameter:BaseApp/Preferences/Editor")
        if isinstance(default, str):
            val = pref.GetString(key, "")
            return val if val else default
        elif isinstance(default, int):
            val = pref.GetInt(key, 0)
            return val if val > 0 else default
        elif isinstance(default, bool):
            return pref.GetBool(key, default)
    except Exception:
        pass
    return default


def _get_pref_color(name: str) -> Optional[QColor]:
    """Retrieve syntax color from FreeCAD preferences if available."""
    if App is None:
        return None
    try:
        p = App.ParamGet("User parameter:BaseApp/Preferences/Editor")
        val = p.GetUnsigned(name, 0)
        if val > 0:
            r = (val >> 24) & 0xFF
            g = (val >> 16) & 0xFF
            b = (val >> 8) & 0xFF
            return QColor(r, g, b)
    except Exception:
        pass
    return None


class LineNumberArea(QWidget):
    """Gutter widget displaying line numbers for the CodeEditor."""

    def __init__(self, editor: 'CodeEditor'):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """
    High-performance code editor widget with line numbering,
    current-line highlight, tab replacement, Ctrl+Wheel zoom,
    and native FreeCAD theme integration.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.setup_appearance()
        self.update_line_number_area_width(0)

    def setup_appearance(self):
        """Configure font, tab width, and palette styling from FreeCAD."""
        font_family = _get_editor_pref("Family", "Cascadia Code")
        font_size = _get_editor_pref("FontSize", 11)
        tab_spaces = _get_editor_pref("TabSize", 4)

        font = QFont(font_family, font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # Tab stop width
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * tab_spaces)

        # Clean stylesheet respecting FreeCAD's active theme
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333333;
                border-radius: 4px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
            QPlainTextEdit:focus {
                border: 1px solid #007acc;
            }
        """)

    def wheelEvent(self, event):
        """Ctrl + MouseWheel to zoom in / out."""
        if event.modifiers() == Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoomIn(1)
            elif delta < 0:
                self.zoomOut(1)
            event.accept()
        else:
            super().wheelEvent(event)

    def line_number_area_width(self):
        digits = 1
        max_blocks = max(1, self.blockCount())
        while max_blocks >= 10:
            max_blocks //= 10
            digits += 1
        space = 18 + self.fontMetrics().horizontalAdvance('9') * digits
        return max(32, space)

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_paint_event(self, event):
        is_dark = self.palette().color(QPalette.Base).lightness() < 128
        gutter_bg = QColor("#1c1c1c") if is_dark else QColor("#f6f8fa")
        gutter_fg = QColor("#858585") if is_dark else QColor("#6e7681")
        active_fg = QColor("#ffffff") if is_dark else QColor("#1f2328")
        divider_color = QColor("#383838") if is_dark else QColor("#d0d7de")

        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), gutter_bg)

        # Crisp vertical separator line on the right edge
        painter.setPen(divider_color)
        painter.drawLine(self.line_number_area.width() - 1, event.rect().top(),
                         self.line_number_area.width() - 1, event.rect().bottom())

        curr_block_num = self.textCursor().blockNumber()

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        font = self.font()
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                if block_number == curr_block_num:
                    painter.setPen(active_fg)
                    bold_font = QFont(font)
                    bold_font.setBold(True)
                    painter.setFont(bold_font)
                    painter.drawText(0, top, self.line_number_area.width() - 8,
                                     self.fontMetrics().height(), Qt.AlignRight, number)
                    painter.setFont(font)
                else:
                    painter.setPen(gutter_fg)
                    painter.drawText(0, top, self.line_number_area.width() - 8,
                                     self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            is_dark = self.palette().color(QPalette.Base).lightness() < 128
            # Subtle, comfortable translucent current-line highlight
            line_color = QColor(255, 255, 255, 12) if is_dark else QColor(0, 0, 0, 10)

            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)
        self.line_number_area.update()

    def keyPressEvent(self, event):
        # Auto-indent on Enter / Return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = len(current_line) - len(current_line.lstrip(' '))
            super().keyPressEvent(event)
            if current_line.rstrip().endswith(':'):
                indentation += 4
            self.insertPlainText(' ' * indentation)
            return
        # Replace Tab key with 4 spaces
        elif event.key() == Qt.Key_Tab:
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)


class ScriptCADEditorDock(QDockWidget):
    """
    Main Dock Widget housing the ScriptCAD procedural modeling workspace.
    Adopts native FreeCAD QToolBar, FreeCAD theme palette, icons, and commands.
    """

    def __init__(self, parent=None):
        super().__init__("ScriptCAD Scripting", parent)
        self.setObjectName("ScriptCADScriptingDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.current_filepath: Optional[str] = None
        self.is_modified: bool = False

        # Live Sync debouncing timer
        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(450)
        self.live_timer.timeout.connect(self.on_live_sync_trigger)

        self.setup_ui()
        self.setup_shortcuts()
        self.load_default_script()

    def setup_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Container styling conforming to FreeCAD's native top bar aesthetic
        container.setStyleSheet(f"""
            QToolBar {{
                background-color: #202020;
                border: none;
                border-bottom: 1px solid #2d2d2d;
                spacing: 2px;
                padding: 2px 4px;
            }}
            QToolBar::separator {{
                width: 1px;
                background-color: #383838;
                margin: 3px 4px;
            }}
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 2px;
                margin: 0px;
            }}
            QToolButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.16);
            }}
            QToolButton:pressed {{
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(0, 0, 0, 0.4);
            }}
            QToolButton:checked {{
                background-color: rgba(56, 139, 253, 0.22);
                border: 1px solid rgba(56, 139, 253, 0.5);
            }}
            QToolButton#BtnLive:checked {{
                background-color: rgba(234, 179, 8, 0.22);
                border: 1px solid rgba(234, 179, 8, 0.5);
            }}
            QToolButton#BtnBody:checked {{
                background-color: rgba(14, 165, 233, 0.22);
                border: 1px solid rgba(14, 165, 233, 0.5);
            }}
            QToolButton#BtnTemplates, QToolButton#BtnExport {{
                padding-left: 2px;
                padding-right: 15px;
            }}
            QToolButton::menu-indicator {{
                image: url({ICON_MENU_ARROW});
                subcontrol-origin: padding;
                subcontrol-position: center right;
                right: 3px;
                width: 9px;
                height: 6px;
            }}
            QMenu {{
                background-color: #222222;
                color: #e0e0e0;
                border: 1px solid #383838;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 5px 18px 5px 22px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: #264f78;
                color: #ffffff;
            }}
            QSplitter::handle:vertical {{
                background-color: #2c2c2c;
                height: 3px;
            }}
        """)

        # =====================================================================
        # Header Toolbar (Ranked Left-to-Right from Most-Used to Least-Used)
        # =====================================================================
        self.toolbar = QToolBar("ScriptCAD Toolbar", container)
        self.toolbar.setIconSize(QSize(20, 20))
        self.toolbar.setMovable(False)

        # 1. Primary Execution Action: Run (#1 Most Used - Far Left)
        self.btn_run = QToolButton()
        self.btn_run.setObjectName("BtnRun")
        self.btn_run.setIcon(QIcon(ICON_RUN))
        self.btn_run.setToolTip(translate("ScriptCAD", "Executes the active script (Alt+P or Ctrl+Return)"))
        self.btn_run.clicked.connect(self.execute_script)
        self.toolbar.addWidget(self.btn_run)

        # 2. Live Sync (#2 Most Used Toggle)
        self.btn_live = QToolButton()
        self.btn_live.setObjectName("BtnLive")
        self.btn_live.setIcon(QIcon(ICON_LIVE))
        self.btn_live.setCheckable(True)
        self.btn_live.setToolTip(translate("ScriptCAD", "Automatically re-executes the script as you type"))
        self.btn_live.toggled.connect(self.on_live_toggle)
        self.toolbar.addWidget(self.btn_live)

        # 3. PartDesign Body Output (#3 Most Used CAD Mode)
        self.btn_body = QToolButton()
        self.btn_body.setObjectName("BtnBody")
        self.btn_body.setIcon(QIcon(ICON_TO_BODY))
        self.btn_body.setCheckable(True)
        self.btn_body.setChecked(True)
        self.btn_body.setToolTip(translate("ScriptCAD", "Wraps output solids into active PartDesign Body container"))
        self.toolbar.addWidget(self.btn_body)

        self.toolbar.addSeparator()

        # 4. Templates & Recipes Dropdown (#4 Preset Geometry Generator)
        self.btn_templates = QToolButton()
        self.btn_templates.setObjectName("BtnTemplates")
        self.btn_templates.setIcon(QIcon(ICON_TEMPLATES))
        self.btn_templates.setToolTip(translate("ScriptCAD", "Loads pre-made procedural CAD scripts and recipes"))
        self.btn_templates.setPopupMode(QToolButton.InstantPopup)
        self.setup_templates_menu()
        self.toolbar.addWidget(self.btn_templates)

        self.toolbar.addSeparator()

        # 5. File Operations: Save, Open, New (Ordered by active coding frequency)
        self.btn_save = QToolButton()
        self.btn_save.setIcon(QIcon(ICON_SAVE))
        self.btn_save.setToolTip(translate("ScriptCAD", "Saves the active script to disk (Ctrl+S)"))
        self.btn_save.clicked.connect(self.save_script)
        self.toolbar.addWidget(self.btn_save)

        self.btn_open = QToolButton()
        self.btn_open.setIcon(QIcon(ICON_OPEN))
        self.btn_open.setToolTip(translate("ScriptCAD", "Opens a script from disk (Ctrl+O)"))
        self.btn_open.clicked.connect(self.open_script)
        self.toolbar.addWidget(self.btn_open)

        self.btn_new = QToolButton()
        self.btn_new.setIcon(QIcon(ICON_NEW))
        self.btn_new.setToolTip(translate("ScriptCAD", "Creates a new blank script (Ctrl+N)"))
        self.btn_new.clicked.connect(self.new_script)
        self.toolbar.addWidget(self.btn_new)

        self.toolbar.addSeparator()

        # 6. Export Model Dropdown (Post-Modeling Action)
        self.btn_export = QToolButton()
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setIcon(QIcon(ICON_EXPORT))
        self.btn_export.setToolTip(translate("ScriptCAD", "Exports active 3D model to STEP, STL, or OBJ format"))
        self.btn_export.setPopupMode(QToolButton.InstantPopup)
        self.setup_export_menu()
        self.toolbar.addWidget(self.btn_export)

        self.toolbar.addSeparator()

        # 7. Search / Find (Code Navigation)
        self.btn_find_toggle = QToolButton()
        self.btn_find_toggle.setIcon(QIcon(ICON_FIND))
        self.btn_find_toggle.setToolTip(translate("ScriptCAD", "Searches text in code (Ctrl+F)"))
        self.btn_find_toggle.clicked.connect(self.toggle_find_bar)
        self.toolbar.addWidget(self.btn_find_toggle)

        layout.addWidget(self.toolbar)

        # =====================================================================
        # 2. In-Editor Find Bar (Toggle with Ctrl+F)
        # =====================================================================
        self.find_container = QWidget()
        find_layout = QHBoxLayout(self.find_container)
        find_layout.setContentsMargins(2, 2, 2, 2)
        find_layout.setSpacing(4)

        find_lbl = QLabel(translate("ScriptCAD", "Find:"))
        find_layout.addWidget(find_lbl)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText(translate("ScriptCAD", "Search code..."))
        self.find_input.returnPressed.connect(self.find_next)
        find_layout.addWidget(self.find_input)

        self.btn_find_next = QPushButton(translate("ScriptCAD", "Next"))
        self.btn_find_next.clicked.connect(self.find_next)
        find_layout.addWidget(self.btn_find_next)

        self.btn_find_prev = QPushButton(translate("ScriptCAD", "Prev"))
        self.btn_find_prev.clicked.connect(self.find_prev)
        find_layout.addWidget(self.btn_find_prev)

        self.btn_find_close = QPushButton("✕")
        self.btn_find_close.setToolTip(translate("ScriptCAD", "Closes find bar (Esc)"))
        self.btn_find_close.setMaximumWidth(28)
        self.btn_find_close.clicked.connect(self.toggle_find_bar)
        find_layout.addWidget(self.btn_find_close)

        self.find_container.hide()
        layout.addWidget(self.find_container)

        # =====================================================================
        # 3. Splitter: Code Editor (top) & Collapsible Console Drawer (bottom)
        # =====================================================================
        splitter = QSplitter(Qt.Vertical)

        # Code Editor
        self.editor = CodeEditor(self)
        is_dark = self.editor.palette().color(QPalette.Base).lightness() < 128
        self.highlighter = PythonHighlighter(self.editor.document(), is_dark=is_dark)
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)
        splitter.addWidget(self.editor)

        # Output / Console Log Area (Collapsible Drawer)
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(1)

        # Console Header with Drawer Toggle Chevron
        console_header = QHBoxLayout()
        console_header.setContentsMargins(2, 2, 2, 0)

        self.btn_console_drawer_title = QToolButton()
        self.btn_console_drawer_title.setText(translate("ScriptCAD", "▲ Console Output"))
        self.btn_console_drawer_title.setToolTip(translate("ScriptCAD", "Expands or collapses output console (Ctrl+` or F8)"))
        self.btn_console_drawer_title.setStyleSheet("border: none; background: transparent; color: #999999; font-weight: 500; font-size: 11px;")
        self.btn_console_drawer_title.clicked.connect(self.toggle_console_drawer)
        console_header.addWidget(self.btn_console_drawer_title)

        console_header.addStretch()

        self.btn_clear_console = QToolButton()
        self.btn_clear_console.setText(translate("ScriptCAD", "Clear Log"))
        self.btn_clear_console.setToolTip(translate("ScriptCAD", "Clears the console output log"))
        self.btn_clear_console.clicked.connect(lambda: self.console_output.clear())
        console_header.addWidget(self.btn_clear_console)

        log_layout.addLayout(console_header)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumHeight(130)
        self.console_output.setFont(QFont("Cascadia Code", 9))
        self.console_output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #161616;
                color: #b0bec5;
                border: 1px solid #2e2e2e;
                border-radius: 4px;
                padding: 2px;
            }
        """)
        # By default start collapsed so editor has maximum vertical space!
        self.console_output.hide()
        log_layout.addWidget(self.console_output)

        splitter.addWidget(log_container)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(splitter)

        # =====================================================================
        # 4. Bottom Status / Coordinate Bar
        # =====================================================================
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(4, 2, 4, 2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        status_bar.addWidget(self.status_label)

        status_bar.addStretch()

        self.cursor_pos_label = QLabel("Ln 1, Col 1")
        self.cursor_pos_label.setStyleSheet("color: #888888; font-size: 11px; padding-right: 4px;")
        status_bar.addWidget(self.cursor_pos_label)

        layout.addLayout(status_bar)
        self.setWidget(container)

    def setup_shortcuts(self):
        # Execution shortcuts
        self.sc_alt_p = QShortcut(QKeySequence("Alt+P"), self)
        self.sc_alt_p.activated.connect(self.execute_script)

        self.sc_ctrl_ret = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.sc_ctrl_ret.activated.connect(self.execute_script)

        # File I/O shortcuts
        self.sc_ctrl_s = QShortcut(QKeySequence("Ctrl+S"), self)
        self.sc_ctrl_s.activated.connect(self.save_script)

        self.sc_ctrl_o = QShortcut(QKeySequence("Ctrl+O"), self)
        self.sc_ctrl_o.activated.connect(self.open_script)

        self.sc_ctrl_n = QShortcut(QKeySequence("Ctrl+N"), self)
        self.sc_ctrl_n.activated.connect(self.new_script)

        # Find shortcut
        self.sc_ctrl_f = QShortcut(QKeySequence("Ctrl+F"), self)
        self.sc_ctrl_f.activated.connect(self.toggle_find_bar)

        # Output console drawer shortcuts
        self.sc_console_backtick = QShortcut(QKeySequence("Ctrl+`"), self)
        self.sc_console_backtick.activated.connect(self.toggle_console_drawer)

        self.sc_console_f8 = QShortcut(QKeySequence("F8"), self)
        self.sc_console_f8.activated.connect(self.toggle_console_drawer)

        # Zoom shortcuts
        self.sc_zoom_in = QShortcut(QKeySequence("Ctrl+="), self)
        self.sc_zoom_in.activated.connect(lambda: self.editor.zoomIn(1))

        self.sc_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
        self.sc_zoom_out.activated.connect(lambda: self.editor.zoomOut(1))

    def setup_export_menu(self):
        menu = QMenu(self)

        act_step = QAction(translate("ScriptCAD", "Export to STEP (.step)..."), self)
        act_step.setIcon(QIcon(ICON_EXPORT))
        act_step.triggered.connect(lambda: self.export_model("step"))
        menu.addAction(act_step)

        act_stl = QAction(translate("ScriptCAD", "Export to STL (.stl)..."), self)
        act_stl.setIcon(QIcon(ICON_EXPORT))
        act_stl.triggered.connect(lambda: self.export_model("stl"))
        menu.addAction(act_stl)

        act_obj = QAction(translate("ScriptCAD", "Export to OBJ (.obj)..."), self)
        act_obj.setIcon(QIcon(ICON_EXPORT))
        act_obj.triggered.connect(lambda: self.export_model("obj"))
        menu.addAction(act_obj)

        self.btn_export.setMenu(menu)

    def update_cursor_position(self):
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.cursor_pos_label.setText(f"Ln {line}, Col {col}")

    # --- File Management ---

    def new_script(self):
        if self.is_modified:
            ret = QMessageBox.question(
                self, "Unsaved Changes",
                "Current script has unsaved changes. Clear anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                return

        self.editor.clear()
        self.current_filepath = None
        self.is_modified = False
        self.update_dock_title()
        self.status_label.setText("New blank script created.")

    def open_script(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Script", "",
            "Python Scripts (*.py);;CAD Scripts (*.scad *.py);;All Files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            self.editor.setPlainText(code)
            self.current_filepath = filepath
            self.is_modified = False
            self.update_dock_title()
            self.status_label.setText(f"Opened: {os.path.basename(filepath)}")
            self.console_output.appendPlainText(f"[ScriptCAD] Opened file: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Could not open file: {e}")

    def save_script(self):
        if not self.current_filepath:
            return self.save_script_as()

        try:
            with open(self.current_filepath, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
            self.is_modified = False
            self.update_dock_title()
            self.status_label.setText(f"Saved: {os.path.basename(self.current_filepath)}")
            self.console_output.appendPlainText(f"[ScriptCAD] Saved to: {self.current_filepath}")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file: {e}")
            return False

    def save_script_as(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Script As", self.current_filepath or "my_model.py",
            "Python Scripts (*.py);;All Files (*)"
        )
        if not filepath:
            return False

        if not filepath.endswith(".py"):
            filepath += ".py"

        self.current_filepath = filepath
        return self.save_script()

    def update_dock_title(self):
        name = os.path.basename(self.current_filepath) if self.current_filepath else "Untitled"
        mod_star = "*" if self.is_modified else ""
        self.setWindowTitle(f"ScriptCAD Scripting - [{name}{mod_star}]")

    # --- Find Bar ---

    def toggle_find_bar(self):
        if self.find_container.isVisible():
            self.find_container.hide()
            self.editor.setFocus()
        else:
            self.find_container.show()
            self.find_input.setFocus()
            self.find_input.selectAll()

    def find_next(self):
        query = self.find_input.text()
        if not query:
            return
        found = self.editor.find(query)
        if not found:
            # Wrap around from top
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(query)
        if not found:
            self.status_label.setText(f"Find: '{query}' not found.")

    def find_prev(self):
        query = self.find_input.text()
        if not query:
            return
        found = self.editor.find(query, QTextEdit.FindBackward)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.End)
            self.editor.setTextCursor(cursor)
            self.editor.find(query, QTextEdit.FindBackward)

    # --- Console Drawer Management ---

    def toggle_console_drawer(self):
        """Toggle console output drawer visibility to maximize vertical code space."""
        if not self.console_output.isHidden():
            self.console_output.hide()
            self.btn_console_drawer_title.setText("▲ Console Output")
        else:
            self.console_output.show()
            self.btn_console_drawer_title.setText("▼ Console Output")

    # --- Direct Model Export ---

    def export_model(self, fmt: str):
        if App is None or App.ActiveDocument is None:
            QMessageBox.warning(self, "Export", "No active document or objects to export.")
            return

        doc = App.ActiveDocument
        target_obj = None

        # Check GUI selection first
        try:
            if Gui and Gui.Selection:
                sel = Gui.Selection.getSelection()
                if sel and hasattr(sel[0], "Shape"):
                    target_obj = sel[0]
        except Exception:
            pass

        # Fallback to latest shape object in document
        if target_obj is None:
            for o in reversed(doc.Objects):
                if hasattr(o, "Shape"):
                    target_obj = o
                    break

        if target_obj is None or not hasattr(target_obj, "Shape"):
            QMessageBox.warning(self, "Export", "No 3D solid or shape found to export.")
            return

        filter_str = {
            "step": "STEP Files (*.step *.stp);;All Files (*)",
            "stl": "STL 3D Mesh (*.stl);;All Files (*)",
            "obj": "Wavefront OBJ (*.obj);;All Files (*)"
        }.get(fmt, "All Files (*)")

        default_name = f"{target_obj.Name}.{fmt}"
        filepath, _ = QFileDialog.getSaveFileName(self, f"Export as {fmt.upper()}", default_name, filter_str)
        if not filepath:
            return

        try:
            import scriptcad
            wrapper = scriptcad.ShapeWrapper(target_obj.Shape)
            if fmt == "step":
                success = wrapper.export_step(filepath)
            elif fmt == "stl":
                success = wrapper.export_stl(filepath)
            elif fmt == "obj":
                success = wrapper.export_obj(filepath)
            else:
                success = False

            if success:
                self.status_label.setText(f"Exported {fmt.upper()}: {os.path.basename(filepath)}")
                self.console_output.appendPlainText(f"[ScriptCAD] Successfully exported: {filepath}")
            else:
                self.status_label.setText("Export failed.")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Export failed: {e}")

    # --- Presets & Execution ---

    def on_text_changed(self):
        if not self.is_modified:
            self.is_modified = True
            self.update_dock_title()
        if self.btn_live.isChecked():
            self.live_timer.start()

    def on_live_toggle(self, checked: bool):
        if checked:
            self.status_label.setText("⚡ Live Sync active: updates on typing pause")
        else:
            self.status_label.setText("Ready")

    def on_live_sync_trigger(self):
        self.execute_script(is_live=True)

    def setup_templates_menu(self):
        """Build the Templates dropdown menu with pre-made procedural CAD scripts."""
        menu = QMenu(self)

        act_new = QAction(translate("ScriptCAD", "New Blank Script"), self)
        act_new.setIcon(QIcon(ICON_NEW))
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self.new_script)
        menu.addAction(act_new)
        menu.addSeparator()

        self.presets = {
            "01 - Welcome: CSG Cutout": PRESET_CSG,
            "02 - Procedural Radial Fins (Polar Array)": PRESET_RADIAL_FINS,
            "03 - Twisted Organic Loft": PRESET_TWISTED_LOFT,
            "04 - Solidified Wave Surface (3D Printable)": PRESET_SOLIDIFIED_WAVE,
            "05 - Parametric Enclosure with Shelling (.shell)": PRESET_SHELL_ENCLOSURE,
            "06 - Swept Curved Pipe & Flange": PRESET_SWEPT_PIPE,
            "07 - Compression Spring (Helical Coil)": PRESET_SPRING,
            "08 - 3D Embossed Text Plaque": PRESET_TEXT_PLAQUE
        }
        for name in self.presets:
            act = QAction(name, self)
            act.setIcon(QIcon(ICON_TEMPLATES))
            act.triggered.connect(lambda checked=False, p_name=name: self.load_preset(p_name))
            menu.addAction(act)
        self.btn_templates.setMenu(menu)

    def load_preset(self, preset_name: str):
        """Load a selected template script into the editor."""
        if preset_name in self.presets:
            if self.is_modified and len(self.editor.toPlainText().strip()) > 30:
                ret = QMessageBox.question(
                    self, "Load Preset",
                    f"Replace current script with template '{preset_name}'?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ret != QMessageBox.Yes:
                    return

            self.editor.setPlainText(self.presets[preset_name])
            self.current_filepath = None
            self.is_modified = False
            self.update_dock_title()
            self.status_label.setText(f"Loaded: {preset_name}")
            self.execute_script()

    def load_default_script(self):
        self.editor.setPlainText(PRESET_CSG)
        self.is_modified = False
        self.update_dock_title()

    def clear_document(self):
        if App is None:
            return
        doc = App.ActiveDocument
        if doc:
            names = [getattr(obj, "Name", None) for obj in doc.Objects]
            for name in names:
                if name and doc.getObject(name) is not None:
                    try:
                        doc.removeObject(name)
                    except Exception:
                        pass
            doc.recompute()
            self.status_label.setText("Document cleared.")
            self.console_output.appendPlainText("[ScriptCAD] Cleared active document.")

    def convert_selection_to_body(self):
        """Wrap selected Part solid into an active PartDesign Body."""
        try:
            import scriptcad
            body = scriptcad.convert_to_body()
            if body:
                self.status_label.setText(f"✓ Converted into active Body: {body.Name}")
                self.console_output.appendPlainText(f"[ScriptCAD] Successfully converted into active PartDesign::Body '{body.Name}'.")
            else:
                self.status_label.setText("Select a Part solid to wrap into Body")
        except Exception as e:
            self.console_output.appendPlainText(f"[ScriptCAD Error] Could not convert to Body: {e}")

    def execute_script(self, is_live: bool = False):
        code = self.editor.toPlainText()
        if not code.strip():
            return

        # Sync PartDesign mode from checkbox
        try:
            import scriptcad
            scriptcad.set_partdesign_mode(self.btn_body.isChecked())
        except Exception:
            pass

        t0 = time.time()
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        doc = None
        if App:
            doc = App.ActiveDocument or App.newDocument("ScriptCAD_Project")
            doc.openTransaction("ScriptCAD Run")

        # Prepare execution namespace with scriptcad pre-imported
        scope: dict[str, Any] = {
            "__name__": "__main__",
            "App": App,
            "Gui": Gui
        }

        # Inject scriptcad module symbols into scope
        try:
            import scriptcad
            for attr in scriptcad.__all__:
                scope[attr] = getattr(scriptcad, attr)
            scope["scriptcad"] = scriptcad
            scope["blendcad"] = scriptcad
        except Exception as e:
            stdout_buf.write(f"[ScriptCAD Warning] Could not pre-import scriptcad: {e}\n")

        success = True
        error_msg = ""

        try:
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                exec(code, scope)
            if doc:
                doc.commitTransaction()
                doc.recompute()
        except Exception as e:
            success = False
            if doc:
                doc.abortTransaction()
            error_msg = traceback.format_exc()

        elapsed_ms = int((time.time() - t0) * 1000)

        # Update Console & Status
        out_str = stdout_buf.getvalue()
        err_str = stderr_buf.getvalue()

        self.console_output.clear()
        if out_str:
            self.console_output.appendPlainText(out_str.strip())
        if err_str:
            self.console_output.appendPlainText(err_str.strip())

        # Also echo to FreeCAD's native Report View / Python Console
        if App and hasattr(App, "Console"):
            try:
                if success:
                    App.Console.PrintMessage(f"[ScriptCAD] Run finished in {elapsed_ms}ms\n")
                    if out_str:
                        App.Console.PrintMessage(out_str.strip() + "\n")
                else:
                    App.Console.PrintError(f"[ScriptCAD Error] ({elapsed_ms}ms):\n{error_msg}\n")
            except Exception:
                pass

        if success:
            mode_prefix = "⚡ Live Sync" if is_live else "Run"
            self.status_label.setText(f"<span style='color: #86efac;'>●</span> {mode_prefix} succeeded in {elapsed_ms}ms")
        else:
            self.console_output.appendPlainText(error_msg)
            self.status_label.setText(f"<span style='color: #ef4444;'>●</span> Error during execution ({elapsed_ms}ms)")
            if self.console_output.isHidden():
                self.toggle_console_drawer()


# =============================================================================
# Preset Template Scripts
# =============================================================================

PRESET_CSG = '''# ScriptCAD: Quickstart CSG Solid
from scriptcad import *

# 1. Create base body
body = Box(length=40, width=40, height=15, center=True)

# 2. Subtract center hole
bore = Cylinder(r=8, h=25, center=True)
result = body - bore

# 3. Add 4 corner bolt countersinks
for x in [-14, 14]:
    for y in [-14, 14]:
        hole = Cylinder(r=2.5, h=20, center=True).at(x, y, 0)
        result -= hole

# 4. Display in FreeCAD viewport
result.fillet(1.0).color(0.2, 0.6, 0.9).show("ParametricMount")
'''

PRESET_RADIAL_FINS = '''# ScriptCAD: Radial Heat Sink / Turbofan Blades (.polar_array)
import math
from scriptcad import *

# 1. Center hub and motor bore
hub = Cylinder(r=12, h=30, center=True)
bore = Cylinder(r=5, h=35, center=True)
core = hub - bore

# 2. Single blade fin with polar array modifier
fin = Box(length=22, width=2.5, height=28, center=True).at(x=18, y=0, z=0)
fins = fin.polar_array(count=12, total_angle=360.0)

# 3. Fuse assembly
assembly = core + fins
assembly.color(0.85, 0.85, 0.88).show("TurbineRotor")
'''

PRESET_TWISTED_LOFT = '''# ScriptCAD: Twisted Organic Vase (Loft Art)
import math
from scriptcad import *

profiles = []
layers = 10
height_step = 6.0

for i in range(layers):
    z = i * height_step
    # Pulsing radius & rotation
    rad = 15.0 + 6.0 * math.sin(i * 0.6)
    rot = i * 15.0  # Twist angle
    
    # Octagonal polygon cross-section
    pts = []
    sides = 8
    for s in range(sides):
        ang = math.radians((360.0 / sides) * s + rot)
        pts.append((rad * math.cos(ang), rad * math.sin(ang), z))
    
    profiles.append(Polygon(pts, filled=True))

vase = Loft(profiles, solid=True)
vase.color(0.9, 0.45, 0.2).show("TwistedVase")
'''

PRESET_SOLIDIFIED_WAVE = '''# ScriptCAD: Procedural Mesh Art Solidified into CAD Solid
from scriptcad import *

# 1. Generate 3D procedural wave surface
wave_mesh = MeshArt.ripple_plane(size=60.0, resolution=25, wave_height=4.0, frequency=0.25)

# 2. Solidify into a watertight, manifold 3D-printable solid block!
solid_wave = wave_mesh.solidify(thickness=6.0)

# 3. Drill a mechanical center mounting hole through the procedural wave solid
hole = Cylinder(r=6.0, h=30.0, center=True)
part = solid_wave - hole

part.color(0.15, 0.75, 0.7).show("WatertightArtSolid")
'''

PRESET_SHELL_ENCLOSURE = '''# ScriptCAD: Parametric Enclosure with Native Shelling (.shell)
from scriptcad import *

# 1. Solid outer case with rounded corners
outer = Box(70, 50, 25, center=True).fillet(3.0)

# 2. Native OpenCASCADE Shelling: leaves top open with 2.0mm wall thickness
case = outer.shell(thickness=2.0, open_faces="top")

# 3. Add 4 corner screw standoff bosses and pilot holes
for x in [-28, 28]:
    for y in [-18, 18]:
        boss = Cylinder(r=3.5, h=18, center=True).at(x, y, -2.5)
        hole = Cylinder(r=1.5, h=22, center=True).at(x, y, -2.5)
        case = (case + boss) - hole

case.color(0.3, 0.35, 0.4).show("ShelledEnclosure")
'''

PRESET_SWEPT_PIPE = '''# ScriptCAD: Swept Curved Pipe & Mounting Flange (Sweep along Spline)
from scriptcad import *

# 1. Define a 3D curved guide path using a B-Spline
path_points = [
    (0, 0, 0),
    (0, 0, 30),
    (20, 0, 50),
    (50, 20, 60),
    (80, 20, 60)
]
guide_path = Spline(path_points)

# 2. Sweep a hollow pipe along the path using CSG difference
outer_pipe = Sweep(profile=Circle(6.0), path=guide_path, solid=True)
inner_pipe = Sweep(profile=Circle(4.5), path=guide_path, solid=True)
curved_pipe = outer_pipe - inner_pipe

# 3. Add a circular base flange with bolt holes
flange = Cylinder(r=15.0, h=5.0) - Cylinder(r=4.5, h=10.0)
for a in [0, 90, 180, 270]:
    bolt = Cylinder(r=2.0, h=10.0).at(x=10, y=0, z=0).rotate_z(a)
    flange -= bolt

assembly = curved_pipe + flange
assembly.color(0.8, 0.5, 0.2).show("SweptPipeAssembly")
'''

PRESET_SPRING = '''# ScriptCAD: Parametric Compression Spring (Helix)
from scriptcad import *

# Create a solid helical coil spring in 1 line
coil = Spring(pitch=6.0, height=45.0, radius=12.0, wire_radius=1.8)
coil.color(0.3, 0.7, 0.9).show("CompressionSpring")
'''

PRESET_TEXT_PLAQUE = '''# ScriptCAD: 3D Embossed Text Plaque
from scriptcad import *

# 1. Base plaque with beveled chamfer
base = Box(80, 35, 6, center=True).fillet(2.0)

# 2. 3D extruded lettering embossed on the top face
label = Text("ScriptCAD", size=10.0, thickness=2.5, center=True).at(z=3.0)

# 3. Combine plaque and embossed lettering
plaque = base + label
plaque.color(0.2, 0.6, 0.85).show("TextPlaque")
'''

# Backward-compatibility alias
BlendCADEditorDock = ScriptCADEditorDock
