"""
BlendCAD Syntax Highlighter:
Blender-inspired dark theme Python syntax highlighting for PySide.
"""

from .qt_compat import (
    QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QtCore
)


class PythonHighlighter(QSyntaxHighlighter):
    """Blender Dark Theme Python syntax highlighter."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Color Palette (Blender Dark Theme)
        COLOR_KEYWORD = QColor("#ff944d")     # Blender Orange
        COLOR_BUILTIN = QColor("#4dd0e1")     # Cyan
        COLOR_BLENDCAD = QColor("#81c784")    # Soft Mint Green
        COLOR_STRING = QColor("#9ccc65")      # Light Green
        COLOR_COMMENT = QColor("#78909c")     # Slate Grey
        COLOR_NUMBER = QColor("#ba68c8")      # Soft Violet
        COLOR_FUNCTION = QColor("#64b5f6")    # Light Sky Blue

        # 1. Keywords
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(COLOR_KEYWORD)
        kw_fmt.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def",
            "del", "elif", "else", "except", "False", "finally", "for",
            "from", "global", "if", "import", "in", "is", "lambda",
            "None", "nonlocal", "not", "or", "pass", "raise", "return",
            "True", "try", "while", "with", "yield", "async", "await"
        ]
        for kw in keywords:
            pattern = QtCore.QRegularExpression(r"\b" + kw + r"\b")
            self.rules.append((pattern, kw_fmt))

        # 2. Builtins
        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(COLOR_BUILTIN)
        builtins = [
            "print", "range", "len", "enumerate", "zip", "map", "filter",
            "int", "float", "str", "bool", "list", "dict", "set", "tuple",
            "min", "max", "sum", "abs", "round", "isinstance", "type"
        ]
        for b in builtins:
            pattern = QtCore.QRegularExpression(r"\b" + b + r"\b")
            self.rules.append((pattern, builtin_fmt))

        # 3. BlendCAD Core Functions & Classes
        blendcad_fmt = QTextCharFormat()
        blendcad_fmt.setForeground(COLOR_BLENDCAD)
        blendcad_fmt.setFontWeight(QFont.Bold)
        blendcad_symbols = [
            "ShapeWrapper", "Box", "Cube", "Cylinder", "Sphere", "Cone",
            "Torus", "Plane", "Circle", "Polygon", "Loft", "Extrude",
            "Revolve", "MeshArt", "clear_document", "active_document"
        ]
        for sym in blendcad_symbols:
            pattern = QtCore.QRegularExpression(r"\b" + sym + r"\b")
            self.rules.append((pattern, blendcad_fmt))

        # 4. Function definitions
        fn_fmt = QTextCharFormat()
        fn_fmt.setForeground(COLOR_FUNCTION)
        self.rules.append((QtCore.QRegularExpression(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)"), fn_fmt))

        # 5. Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(COLOR_NUMBER)
        self.rules.append((QtCore.QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), num_fmt))

        # 6. Single-line strings
        self.str_fmt = QTextCharFormat()
        self.str_fmt.setForeground(COLOR_STRING)
        self.rules.append((QtCore.QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), self.str_fmt))
        self.rules.append((QtCore.QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), self.str_fmt))

        # 7. Comments
        self.comment_fmt = QTextCharFormat()
        self.comment_fmt.setForeground(COLOR_COMMENT)
        self.comment_fmt.setFontItalic(True)
        self.rules.append((QtCore.QRegularExpression(r"#[^\n]*"), self.comment_fmt))

        # Multi-line strings / docstrings regex
        self.tri_double = QtCore.QRegularExpression(r'"""')
        self.tri_single = QtCore.QRegularExpression(r"'''")

    def highlightBlock(self, text):
        # Apply standard single-line rules
        for pattern, fmt in self.rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        # Multi-line strings
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
            end_index = match.capturedStart() if match.hasMatch() else -1
            if end_index == -1:
                self.setCurrentBlockState(state)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + 3

            self.setFormat(start_index, comment_length, self.str_fmt)
            if end_index == -1:
                break
            match2 = delimiter.match(text, start_index + comment_length)
            start_index = match2.capturedStart() if match2.hasMatch() else -1
