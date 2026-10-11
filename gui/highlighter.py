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

        # 3. Python Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(c_kw)
        kw_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return",
            "try", "while", "with", "yield", "async", "await"
        ]
        for kw in keywords:
            add_rule(r"\b" + kw + r"\b", kw_fmt)

        # 4. Booleans & Constants
        const_fmt = QTextCharFormat()
        const_fmt.setForeground(c_const)
        const_fmt.setFontWeight(QFont.Bold)
        for const in ["True", "False", "None"]:
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

        # 6. ScriptCAD Primitives & 3D Solids (Distinctive Mint Turquoise)
        cad_fmt = QTextCharFormat()
        cad_fmt.setForeground(c_cad)
        cad_fmt.setFontWeight(QFont.Bold)
        cad_symbols = [
            "ShapeWrapper", "Box", "Cube", "Cylinder", "Sphere", "Cone",
            "Torus", "Plane", "Circle", "Polygon", "Loft", "Extrude",
            "Revolve", "Sweep", "Helix", "Spring", "Slot", "Text", "MeshArt",
            "clear_document", "active_document", "convert_to_body"
        ]
        for sym in cad_symbols:
            add_rule(r"\b" + sym + r"\b", cad_fmt)

        # 7. Function and Class Declarations
        fn_fmt = QTextCharFormat()
        fn_fmt.setForeground(c_fn)
        fn_fmt.setFontWeight(QFont.Bold)
        add_rule(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)", fn_fmt, 1)
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

        # 10. Comments (Top precedence for single lines)
        add_rule(r"#[^\n]*", self.comment_fmt)

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

        # Multi-line strings / docstrings
        self.setCurrentBlockState(0)
        self._highlight_multiline(text, self.tri_double, 1)
        self._highlight_multiline(text, self.tri_single, 2)

    def _highlight_multiline(self, text, delimiter, state):
        start_index = 0
        if self.previousBlockState() == state:
            start_index = 0
        else:
            match = delimiter.match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1

        while start_index >= 0:
            match = delimiter.match(text, start_index + 3)
            match_len = match.capturedLength()
            if match_len > 0:
                end_index = match.capturedStart()
                comment_length = end_index - start_index + match_len
                self.setFormat(start_index, comment_length, self.str_fmt)
                start_index = delimiter.match(text, start_index + comment_length).capturedStart()
            else:
                self.setCurrentBlockState(state)
                comment_length = len(text) - start_index
                self.setFormat(start_index, comment_length, self.str_fmt)
                break
