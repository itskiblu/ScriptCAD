"""
ScriptCAD Interactive Scripting Dock:
Interactive dockable code editor inside FreeCAD with live sync,
syntax highlighting, line numbers, and instant execution.
"""

import sys
import time
import traceback
import io
from typing import Any
from contextlib import redirect_stdout, redirect_stderr

from .qt_compat import (
    QWidget, QDockWidget, QPlainTextEdit, QTextEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QSplitter,
    QColor, QFont, QPainter, QRect, QSize, QTextFormat,
    Qt, QTimer, QKeySequence, QShortcut
)
from .highlighter import PythonHighlighter

try:
    import FreeCAD as App
    import FreeCADGui as Gui
except ImportError:
    App = None
    Gui = None


class LineNumberArea(QWidget):
    """Gutter widget displaying line numbers for the CodeEditor."""
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_paint_event(event)


class CodeEditor(QPlainTextEdit):
    """
    High-performance code editor widget with line numbering,
    current-line highlight, tab replacement, and Blender dark aesthetic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        # Connect signals
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_line_number_area_width(0)
        self.setup_appearance()

    def setup_appearance(self):
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)

        # Tab stop = 4 spaces
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)

        # Blender Dark Theme styling
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #333333;
                border-radius: 4px;
                selection-background-color: #e57e25;
                selection-color: #ffffff;
            }
        """)

    def line_number_area_width(self):
        digits = 1
        max_blocks = max(1, self.blockCount())
        while max_blocks >= 10:
            max_blocks //= 10
            digits += 1
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

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
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#222222"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        painter.setPen(QColor("#666666"))
        font = self.font()
        painter.setFont(font)

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
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
            line_color = QColor("#282828")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        # Auto indent on return
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            cursor = self.textCursor()
            current_line = cursor.block().text()
            indentation = len(current_line) - len(current_line.lstrip(' '))
            super().keyPressEvent(event)
            if current_line.rstrip().endswith(':'):
                indentation += 4
            self.insertPlainText(' ' * indentation)
            return
        # Replace Tab with 4 spaces
        elif event.key() == Qt.Key_Tab:
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)


class ScriptCADEditorDock(QDockWidget):
    """
    Main Dock Widget housing the ScriptCAD code workspace.
    """
    def __init__(self, parent=None):
        super().__init__("ScriptCAD Scripting", parent)
        self.setObjectName("ScriptCADScriptingDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

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
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- Top Header / Toolbar ---
        header_bar = QHBoxLayout()
        header_bar.setSpacing(6)

        # Run Button (Blender Orange Accent)
        self.btn_run = QPushButton("▶ Run (Alt+P)")
        self.btn_run.setToolTip("Execute the script (Alt+P or Ctrl+Return)")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #e57e25;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #ff944d;
            }
            QPushButton:pressed {
                background-color: #c96818;
            }
        """)
        self.btn_run.clicked.connect(self.execute_script)
        header_bar.addWidget(self.btn_run)

        # Live Sync Checkbox
        self.chk_live = QCheckBox("⚡ Live Sync")
        self.chk_live.setToolTip("Automatically re-run script as you type")
        self.chk_live.setStyleSheet("color: #d0d0d0; font-weight: 500;")
        self.chk_live.stateChanged.connect(self.on_live_toggle)
        header_bar.addWidget(self.chk_live)

        # PartDesign Body Checkbox (Checked by default!)
        self.chk_body = QCheckBox("📦 PartDesign Body")
        self.chk_body.setChecked(True)
        self.chk_body.setToolTip("Automatically output as active PartDesign::Body containers so Part Design tools (Fillet, Chamfer, Sketch, Pocket) work immediately.")
        self.chk_body.setStyleSheet("color: #d0d0d0; font-weight: 500;")
        header_bar.addWidget(self.chk_body)

        header_bar.addStretch()

        # Preset Templates Dropdown
        self.combo_presets = QComboBox()
        self.combo_presets.setToolTip("Load pre-made procedural CAD & mesh art scripts")
        self.combo_presets.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.populate_presets()
        self.combo_presets.currentIndexChanged.connect(self.on_preset_selected)
        header_bar.addWidget(self.combo_presets)

        # Convert Selection to PartDesign Body Button
        self.btn_to_body = QPushButton("📦 To Body")
        self.btn_to_body.setToolTip("Convert current FreeCAD selection into an active PartDesign::Body")
        self.btn_to_body.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                color: #bbb;
                border: 1px solid #484848;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: #fff;
            }
        """)
        self.btn_to_body.clicked.connect(self.convert_selection_to_body)
        header_bar.addWidget(self.btn_to_body)

        # Clear Document Button
        self.btn_clear = QPushButton("🗑 Clear")
        self.btn_clear.setToolTip("Clear all objects in the active document")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                color: #bbb;
                border: 1px solid #484848;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                color: #fff;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_document)
        header_bar.addWidget(self.btn_clear)

        layout.addLayout(header_bar)

        # --- Splitter (Editor on top, Log console on bottom) ---
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #333333;
                height: 4px;
            }
        """)

        # Code Editor
        self.editor = CodeEditor(self)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self.on_text_changed)
        splitter.addWidget(self.editor)

        # Output / Console Log Area
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(2)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 4px;")
        log_layout.addWidget(self.status_label)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumHeight(140)
        self.console_output.setFont(QFont("Consolas", 9))
        self.console_output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #141414;
                color: #b0bec5;
                border: 1px solid #282828;
                border-radius: 4px;
            }
        """)
        log_layout.addWidget(self.console_output)

        splitter.addWidget(log_container)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
        self.setWidget(container)

    def setup_shortcuts(self):
        # Blender shortcut: Alt+P
        self.sc_alt_p = QShortcut(QKeySequence("Alt+P"), self)
        self.sc_alt_p.activated.connect(self.execute_script)

        # Alternate standard shortcut: Ctrl+Return
        self.sc_ctrl_ret = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.sc_ctrl_ret.activated.connect(self.execute_script)

    def on_text_changed(self):
        if self.chk_live.isChecked():
            self.live_timer.start()

    def on_live_toggle(self, state):
        if state:
            self.status_label.setText("⚡ Live Sync active: updates on typing pause")
        else:
            self.status_label.setText("Ready")

    def on_live_sync_trigger(self):
        self.execute_script(is_live=True)

    def populate_presets(self):
        self.combo_presets.addItem("Templates & Recipes...")
        self.presets = {
            "01 - Welcome: CSG Cutout": PRESET_CSG,
            "02 - Procedural Radial Fins": PRESET_RADIAL_FINS,
            "03 - Twisted Organic Loft": PRESET_TWISTED_LOFT,
            "04 - Procedural Wave Surface (Mesh Art)": PRESET_MESH_WAVE,
            "05 - Parametric Enclosure with Screws": PRESET_ENCLOSURE
        }
        for name in self.presets:
            self.combo_presets.addItem(name)

    def on_preset_selected(self, index):
        if index <= 0:
            return
        preset_name = self.combo_presets.currentText()
        if preset_name in self.presets:
            self.editor.setPlainText(self.presets[preset_name])
            self.execute_script()
        self.combo_presets.setCurrentIndex(0)

    def load_default_script(self):
        self.editor.setPlainText(PRESET_CSG)

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
                self.status_label.setText(f"<span style='color: #81c784;'>✓ Converted into active Body: {body.Name}</span>")
                self.console_output.appendPlainText(f"[ScriptCAD] Successfully converted into active PartDesign::Body '{body.Name}'.")
            else:
                self.status_label.setText("<span style='color: #e57373;'>Select a Part solid to wrap into Body</span>")
        except Exception as e:
            self.console_output.appendPlainText(f"[ScriptCAD Error] Could not convert to Body: {e}")

    def execute_script(self, is_live=False):
        code = self.editor.toPlainText()
        if not code.strip():
            return

        # Sync PartDesign mode from checkbox
        try:
            import scriptcad
            scriptcad.set_partdesign_mode(self.chk_body.isChecked())
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

        if success:
            mode_prefix = "⚡ Live Sync" if is_live else "✓ Run"
            self.status_label.setText(f"<span style='color: #81c784;'>{mode_prefix} succeeded in {elapsed_ms}ms</span>")
        else:
            self.console_output.appendPlainText(error_msg)
            self.status_label.setText(f"<span style='color: #e57373;'>✗ Error during execution ({elapsed_ms}ms)</span>")


# --- Preset Template Scripts ---

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

PRESET_RADIAL_FINS = '''# ScriptCAD: Radial Heat Sink / Turbofan Blades
import math
from scriptcad import *

core = Cylinder(r=12, h=30, center=True)
hub = Cylinder(r=6, h=35, center=True)
assembly = core - hub

num_fins = 12
for i in range(num_fins):
    angle = (360.0 / num_fins) * i
    fin = Box(length=22, width=2.5, height=28, center=True)
    fin = fin.at(x=18, y=0, z=0).rotate_z(angle)
    assembly += fin

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

PRESET_MESH_WAVE = '''# ScriptCAD: Procedural Mesh Art to CAD Solid
import math
from scriptcad import *

# 1. Generate 3D procedural wave surface
wave = MeshArt.ripple_plane(size=60.0, resolution=25, wave_height=4.0, frequency=0.25)

# 2. Render as CAD solid (or use as_solid=False for high-speed polygon mesh)
wave.show(name="GenerativeWave", color=(0.1, 0.75, 0.7), as_solid=False)
'''

PRESET_ENCLOSURE = '''# ScriptCAD: Electronics Enclosure with Screw Bosses
from scriptcad import *

outer = Box(70, 50, 25, center=True).fillet(3.0)
inner = Box(66, 46, 23, center=True).at(z=2)  # Hollow inside
case = outer - inner

# Add 4 internal corner screw bosses
for x in [-28, 28]:
    for y in [-18, 18]:
        boss = Cylinder(r=3.5, h=20, center=True).at(x, y, 0)
        hole = Cylinder(r=1.5, h=22, center=True).at(x, y, 0)
        case = (case + boss) - hole

case.color(0.3, 0.3, 0.35).show("ProjectEnclosure")
'''

# Backward-compatibility alias
BlendCADEditorDock = ScriptCADEditorDock

