# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Syntax Highlighter:
Modern, balanced Python syntax highlighting for FreeCAD.
Provides high-contrast, visually pleasing highlighting for CAD scripts,
featuring distinct colors for CAD primitives, chained methods, keywords,
numbers, strings, and comments.
"""

from typing import Optional
from .qt_compat import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QRegularExpression
)


class PythonHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter with a refined, professional color scheme
    harmonized for FreeCAD's dark and light environments.
    """

    def __init__(self, document, is_dark: bool = True):
        super().__init__(document)
        self.is_dark = is_dark
        self.rules: list = []
        self.tri_double = QRegularExpression(r'"""')
        self.tri_single = QRegularExpression(r"'''")
        self.str_fmt = QTextCharFormat()
        self.comment_fmt = QTextCharFormat()
        self.setup_rules()

    def set_theme(self, is_dark: bool):
        """Update highlighter theme colors and refresh highlight."""
        if self.is_dark != is_dark:
            self.is_dark = is_dark
            self.setup_rules()
            self.rehighlight()

    def setup_rules(self):
        self.rules = []

        if self.is_dark:
            # Curated modern Dark Palette (balanced, vibrant, high-contrast)
            c_kw = QColor("#569cd6")       # Royal Electric Blue
            c_const = QColor("#4fc1ff")    # Bright Sky Cyan
            c_builtin = QColor("#4ec9b0")  # Soft Teal
            c_cad = QColor("#4ec9b0")      # Luminous Mint Turquoise
            c_method = QColor("#dcdcaa")   # Warm Luminous Gold
            c_fn = QColor("#dcdcaa")       # Warm Luminous Gold
            c_str = QColor("#f08d49")      # Warm Apricot / Amber Coral
            c_com = QColor("#85929e")      # Crisp Slate Gray
            c_num = QColor("#b5cea8")      # Soft Pastel Mint
        else:
            # Curated modern Light Palette
            c_kw = QColor("#0550ae")       # Rich Sapphire Blue
            c_const = QColor("#0969da")    # Deep Cobalt Blue
            c_builtin = QColor("#0e7c68")  # Deep Teal
            c_cad = QColor("#116329")      # Deep Emerald Green
            c_method = QColor("#795e26")   # Amber Bronze
            c_fn = QColor("#8250df")       # Royal Purple
            c_str = QColor("#a31515")      # Crimson Red
            c_com = QColor("#6e7681")      # Slate Gray
            c_num = QColor("#098658")      # Forest Green

        # Helper to register a rule (pattern, format, capture_group)
        def add_rule(pattern_str: str, fmt: QTextCharFormat, group: int = 0):
            regex = QRegularExpression(pattern_str)
            self.rules.append((regex, fmt, group))

        # 1. Comments (lowest precedence of basic rules, but processed)
        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(c_com)
        self.comment_fmt.setFontItalic(True)

        # 2. Numbers (integers, floats, scientific notation)
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(c_num)
        add_rule(r"\b[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?\b", num_fmt)

        # 3. Python & OpenSCAD Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(c_kw)
        kw_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return",
            "try", "while", "with", "yield", "async", "await",
            "module", "function", "include", "use"
        ]
        for kw in keywords:
            add_rule(r"\b" + kw + r"\b", kw_fmt)

        # 4. Booleans & Constants
        const_fmt = QTextCharFormat()
        const_fmt.setForeground(c_const)
        const_fmt.setFontWeight(QFont.Bold)
        for const in ["True", "False", "None", "true", "false", "undef", "PI"]:
            add_rule(r"\b" + const + r"\b", const_fmt)

        # 5. Builtin Functions
        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(c_builtin)
        builtins = [
            "print", "range", "len", "enumerate", "zip", "map", "filter",
            "int", "float", "str", "bool", "list", "dict", "set", "tuple",
            "min", "max", "sum", "abs", "round", "isinstance", "type"
        ]
        for b in builtins:
            add_rule(r"\b" + b + r"\b", builtin_fmt)

        # 6. ScriptCAD & OpenSCAD Primitives & Transforms (Mint Turquoise)
        cad_fmt = QTextCharFormat()
        cad_fmt.setForeground(c_cad)
        cad_fmt.setFontWeight(QFont.Bold)
        cad_symbols = [
            "ShapeWrapper", "Box", "Cube", "Cylinder", "Sphere", "Cone",
            "Torus", "Wedge", "Plane", "Rectangle", "Circle", "Arc", "Ellipse",
            "Polygon", "Spline", "Slot", "Text", "Pipe", "Tube", "Loft", "Extrude",
            "Revolve", "Sweep", "Helix", "Spring", "HelixSolid", "MeshArt",
            "clear_document", "active_document", "convert_to_body",
            "decompile", "ModelDecompiler", "get_document_models",
            "cube", "cylinder", "sphere", "square", "circle", "polygon", "polyhedron",
            "difference", "union", "intersection", "hull", "minkowski",
            "translate", "rotate", "scale", "mirror", "linear_extrude", "rotate_extrude",
            "offset", "color", "transpile_openscad", "run_openscad"
        ]
        for sym in cad_symbols:
            add_rule(r"\b" + sym + r"\b", cad_fmt)

        # 7. Function, Class & Module Declarations
        fn_fmt = QTextCharFormat()
        fn_fmt.setForeground(c_fn)
        fn_fmt.setFontWeight(QFont.Bold)
        add_rule(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", fn_fmt, 1)
        add_rule(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_]*)", fn_fmt, 1)
        add_rule(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)", cad_fmt, 1)

        # 8. Chained Method Calls (.fillet(), .color(), .show(), .at(), etc.)
        method_fmt = QTextCharFormat()
        method_fmt.setForeground(c_method)
        add_rule(r"\.([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()", method_fmt, 1)

        # 9. Single-line strings (Higher precedence than numbers/keywords)
        self.str_fmt = QTextCharFormat()
        self.str_fmt.setForeground(c_str)
        add_rule(r'"[^"\\]*(\\.[^"\\]*)*"', self.str_fmt)
        add_rule(r"'[^'\\]*(\\.[^'\\]*)*'", self.str_fmt)

        # 10. Comments (Python # and OpenSCAD //)
        add_rule(r"#[^\n]*", self.comment_fmt)
        add_rule(r"//[^\n]*", self.comment_fmt)

    def highlightBlock(self, text):
        # Apply registered rules in sequence
        for pattern, fmt, group in self.rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                start = match.capturedStart(group)
                length = match.capturedLength(group)
                if start >= 0 and length > 0:
                    self.setFormat(start, length, fmt)

        # Multi-line strings / docstrings (e.g. """...""" or '''...''')
        prev_state = self.previousBlockState()
        self.setCurrentBlockState(0)

        if prev_state == 2:
            self._highlight_multiline(text, self.tri_single, 2)
        elif prev_state == 1:
            self._highlight_multiline(text, self.tri_double, 1)
        else:
            # Check which multiline delimiter appears first on this line
            m_double = self.tri_double.match(text)
            m_single = self.tri_single.match(text)
            pos_double = m_double.capturedStart() if m_double.hasMatch() else -1
            pos_single = m_single.capturedStart() if m_single.hasMatch() else -1

            if pos_double != -1 and (pos_single == -1 or pos_double < pos_single):
                self._highlight_multiline(text, self.tri_double, 1)
            elif pos_single != -1:
                self._highlight_multiline(text, self.tri_single, 2)

    def _highlight_multiline(self, text: str, delimiter: QRegularExpression, state: int):
        offset = 0
        text_len = len(text)

        # If line begins inside an open multiline string from a previous block
        if self.previousBlockState() == state:
            end_match = delimiter.match(text, 0)
            if not end_match.hasMatch():
                # Entire line is inside multiline string
                self.setCurrentBlockState(state)
                self.setFormat(0, text_len, self.str_fmt)
                return
            else:
                # Closing delimiter found on this line
                end_idx = end_match.capturedStart()
                delim_len = end_match.capturedLength()
                closed_len = end_idx + delim_len
                self.setFormat(0, closed_len, self.str_fmt)
                offset = closed_len

        # Search for any opening multiline string starting at offset
        while offset < text_len:
            start_match = delimiter.match(text, offset)
            if not start_match.hasMatch():
                break
            open_idx = start_match.capturedStart()
            end_match = delimiter.match(text, open_idx + 3)
            if end_match.hasMatch():
                end_idx = end_match.capturedStart()
                delim_len = end_match.capturedLength()
                closed_len = end_idx - open_idx + delim_len
                self.setFormat(open_idx, closed_len, self.str_fmt)
                offset = open_idx + closed_len
            else:
                # String remains unclosed at end of line
                self.setCurrentBlockState(state)
                self.setFormat(open_idx, text_len - open_idx, self.str_fmt)
                break
