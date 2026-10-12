# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD OpenSCAD Engine & Transpiler:
Provides native OpenSCAD script execution, automatic syntax detection,
and 1-click transpilation of OpenSCAD (.scad) code into clean, idiomatic
procedural ScriptCAD Python scripts.
Zero external dependencies required (pure Python parser & AST evaluator).
"""

import ast
import math
import os
import re
import shutil
import subprocess
from typing import List, Dict, Any, Tuple, Optional, Union

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

from .core import ShapeWrapper, union, difference, intersection
from .primitives import (
    Box, Cube, Cylinder, Sphere, Cone, Torus, Wedge, Pipe,
    Plane, Rectangle, Circle, Arc, Ellipse, Polygon, Slot, Text
)

# -----------------------------------------------------------------------------
# Tokenizer
# -----------------------------------------------------------------------------

TOK_NUM = "NUM"
TOK_STR = "STR"
TOK_IDENT = "IDENT"
TOK_PUNCT = "PUNCT"
TOK_OP = "OP"
TOK_EOF = "EOF"

TOKEN_SPEC = [
    ("COMMENT_MULTI", r"/\*[\s\S]*?\*/"),
    ("COMMENT_SINGLE", r"//.*"),
    ("NUM", r"\b\d+(\.\d+)?([eE][+-]?\d+)?\b"),
    ("STR", r'"([^"\\]|\\.)*"'),
    ("IDENT", r"[\$a-zA-Z_][a-zA-Z0-9_\$]*"),
    ("OP", r"==|!=|<=|>=|&&|\|\||[+\-*/%<>=!?:&|]"),
    ("PUNCT", r"[\(\)\{\}\[\];,]"),
    ("WS", r"\s+"),
]

MASTER_RE = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in TOKEN_SPEC))

# Standard CSS Color map for OpenSCAD color("name") calls
CSS_COLORS = {
    "red": (1.0, 0.0, 0.0), "green": (0.0, 0.8, 0.0), "blue": (0.0, 0.4, 1.0),
    "yellow": (1.0, 0.9, 0.0), "cyan": (0.0, 0.9, 0.9), "magenta": (1.0, 0.0, 1.0),
    "orange": (1.0, 0.5, 0.0), "purple": (0.6, 0.1, 0.8), "black": (0.1, 0.1, 0.1),
    "white": (0.95, 0.95, 0.95), "gray": (0.5, 0.5, 0.5), "grey": (0.5, 0.5, 0.5),
    "silver": (0.75, 0.75, 0.75), "gold": (1.0, 0.84, 0.0), "lime": (0.2, 0.9, 0.2),
    "teal": (0.0, 0.5, 0.5), "navy": (0.0, 0.0, 0.5), "maroon": (0.5, 0.0, 0.0)
}


class Token:
    def __init__(self, typ: str, val: str, line: int, col: int):
        self.type = typ
        self.val = val
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {repr(self.val)}, L{self.line}:C{self.col})"


def tokenize(source: str) -> List[Token]:
    tokens = []
    line = 1
    line_start = 0
    for match in MASTER_RE.finditer(source):
        typ = match.lastgroup
        val = match.group(typ)
        col = match.start() - line_start + 1

        if typ in ("COMMENT_MULTI", "COMMENT_SINGLE", "WS"):
            newlines = val.count("\n")
            if newlines > 0:
                line += newlines
                line_start = match.end() - len(val.rsplit("\n", 1)[-1])
            continue

        tokens.append(Token(typ, val, line, col))
        newlines = val.count("\n")
        if newlines > 0:
            line += newlines
            line_start = match.end() - len(val.rsplit("\n", 1)[-1])

    tokens.append(Token(TOK_EOF, "", line, 0))
    return tokens


# -----------------------------------------------------------------------------
# AST Nodes
# -----------------------------------------------------------------------------

class ASTNode:
    pass

class VarAssign(ASTNode):
    def __init__(self, name: str, expr: str):
        self.name = name
        self.expr = expr

class FuncDef(ASTNode):
    def __init__(self, name: str, params: List[str], expr: str):
        self.name = name
        self.params = params
        self.expr = expr

class ModuleDef(ASTNode):
    def __init__(self, name: str, params: List[str], body: List[ASTNode]):
        self.name = name
        self.params = params
        self.body = body

class IfStatement(ASTNode):
    def __init__(self, cond: str, then_body: List[ASTNode], else_body: Optional[List[ASTNode]] = None):
        self.cond = cond
        self.then_body = then_body
        self.else_body = else_body or []

class ForLoop(ASTNode):
    def __init__(self, loop_vars: List[Tuple[str, str]], body: List[ASTNode]):
        self.loop_vars = loop_vars
        self.body = body

class CSGBlock(ASTNode):
    def __init__(self, op: str, children: List[ASTNode]):
        self.op = op  # "union", "difference", "intersection"
        self.children = children

class Transform(ASTNode):
    def __init__(self, name: str, args: List[str], kwargs: Dict[str, str], children: List[ASTNode]):
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.children = children

class Primitive(ASTNode):
    def __init__(self, name: str, args: List[str], kwargs: Dict[str, str]):
        self.name = name
        self.args = args
        self.kwargs = kwargs

class ModuleCall(ASTNode):
    def __init__(self, name: str, args: List[str], kwargs: Dict[str, str], children: Optional[List[ASTNode]] = None):
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.children = children or []


# -----------------------------------------------------------------------------
# OpenSCAD Parser
# -----------------------------------------------------------------------------

class OpenSCADParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def lookahead(self, n: int = 1) -> Token:
        idx = min(self.pos + n, len(self.tokens) - 1)
        return self.tokens[idx]

    def next(self) -> Token:
        t = self.tokens[self.pos]
        if t.type != TOK_EOF:
            self.pos += 1
        return t

    def expect(self, val: str) -> Token:
        t = self.next()
        if t.val != val:
            raise SyntaxError(f"Expected '{val}', got '{t.val}' at line {t.line}")
        return t

    def match(self, val: str) -> bool:
        if self.peek().val == val:
            self.next()
            return True
        return False

    def parse_program(self) -> List[ASTNode]:
        nodes = []
        while self.peek().type != TOK_EOF:
            if self.match(";"):
                continue
            node = self.parse_statement()
            if node:
                nodes.append(node)
        return nodes

    def parse_statement(self) -> Optional[ASTNode]:
        # Handle modifier prefixes: * (disable), ! (root), # (debug), % (background)
        while self.peek().val in ("*", "!", "#", "%"):
            mod = self.next().val
            if mod == "*":
                self.parse_statement()
                return None

        t = self.peek()

        # Variable assignment: IDENT = expr;
        if t.type == TOK_IDENT and self.lookahead().val == "=":
            name = self.next().val
            self.expect("=")
            clean_name = re.sub(r"^\$", "", name)
            expr = self.parse_expr()
            self.match(";")
            return VarAssign(clean_name, expr)

        # Function definition: function name(...) = expr;
        if t.type == TOK_IDENT and t.val == "function":
            self.next()
            fname = self.expect_ident()
            params = self.parse_param_list()
            self.expect("=")
            expr = self.parse_expr()
            self.match(";")
            return FuncDef(fname, params, expr)

        # Module definition: module name(...) statement_or_block
        if t.type == TOK_IDENT and t.val == "module":
            self.next()
            mname = self.expect_ident()
            params = self.parse_param_list()
            body = self.parse_statement_or_block()
            return ModuleDef(mname, params, body)

        # Include / Use directives: skip
        if t.type == TOK_IDENT and t.val in ("include", "use"):
            self.next()
            self.next()
            self.match(";")
            return None

        # Echo statement: echo(...)
        if t.type == TOK_IDENT and t.val == "echo":
            self.next()
            self.parse_call_args()
            self.match(";")
            return None

        # Flow control
        if t.type == TOK_IDENT and t.val == "if":
            return self.parse_if()

        if t.type == TOK_IDENT and t.val in ("for", "intersection_for"):
            return self.parse_for()

        # Geometry statement
        return self.parse_geometry_statement()

    def expect_ident(self) -> str:
        t = self.next()
        if t.type != TOK_IDENT:
            raise SyntaxError(f"Expected identifier at line {t.line}, got {t.val}")
        return t.val

    def parse_param_list(self) -> List[str]:
        self.expect("(")
        params = []
        if self.match(")"):
            return params
        while True:
            pname = self.expect_ident()
            clean_p = re.sub(r"^\$", "", pname)
            if self.match("="):
                default_val = self.parse_expr()
                params.append(f"{clean_p}={default_val}")
            else:
                params.append(clean_p)
            if not self.match(","):
                break
        self.expect(")")
        return params

    def parse_statement_or_block(self) -> List[ASTNode]:
        if self.match("{"):
            body = []
            while not self.match("}"):
                if self.peek().type == TOK_EOF:
                    raise SyntaxError("Unexpected EOF inside block")
                stmt = self.parse_statement()
                if stmt:
                    body.append(stmt)
            return body
        else:
            stmt = self.parse_statement()
            return [stmt] if stmt else []

    def parse_if(self) -> ASTNode:
        self.expect("if")
        self.expect("(")
        cond = self.parse_expr()
        self.expect(")")
        then_body = self.parse_statement_or_block()
        else_body = []
        if self.match("else"):
            else_body = self.parse_statement_or_block()
        return IfStatement(cond, then_body, else_body)

    def parse_for(self) -> ASTNode:
        self.next()
        self.expect("(")
        loop_vars = []
        while True:
            vname = self.expect_ident()
            clean_v = re.sub(r"^\$", "", vname)
            self.expect("=")
            vexpr = self.parse_expr()
            loop_vars.append((clean_v, vexpr))
            if not self.match(","):
                break
        self.expect(")")
        body = self.parse_statement_or_block()
        return ForLoop(loop_vars, body)

    def parse_geometry_statement(self) -> ASTNode:
        name = self.expect_ident()
        args, kwargs = self.parse_call_args()

        if self.match(";"):
            if name in ("cube", "cylinder", "sphere", "square", "circle", "polygon", "polyhedron", "text"):
                return Primitive(name, args, kwargs)
            else:
                return ModuleCall(name, args, kwargs)

        children = self.parse_statement_or_block()

        if name in ("difference", "union", "intersection", "hull", "minkowski"):
            return CSGBlock(name, children)
        elif name in ("translate", "rotate", "scale", "mirror", "color", "linear_extrude", "rotate_extrude", "offset"):
            return Transform(name, args, kwargs, children)
        else:
            return ModuleCall(name, args, kwargs, children)

    def parse_call_args(self) -> Tuple[List[str], Dict[str, str]]:
        self.expect("(")
        args = []
        kwargs = {}
        if self.match(")"):
            return args, kwargs
        while True:
            if self.peek().type == TOK_IDENT and self.lookahead().val == "=":
                kw = self.next().val
                clean_kw = re.sub(r"^\$", "", kw)
                self.expect("=")
                val = self.parse_expr()
                kwargs[clean_kw] = val
            else:
                args.append(self.parse_expr())
            if not self.match(","):
                break
        self.expect(")")
        return args, kwargs

    def parse_expr(self) -> str:
        return self.parse_ternary()

    def parse_ternary(self) -> str:
        expr = self.parse_logical_or()
        if self.match("?"):
            true_expr = self.parse_expr()
            self.expect(":")
            false_expr = self.parse_expr()
            return f"({true_expr} if {expr} else {false_expr})"
        return expr

    def parse_logical_or(self) -> str:
        left = self.parse_logical_and()
        while self.match("||"):
            right = self.parse_logical_and()
            left = f"({left} or {right})"
        return left

    def parse_logical_and(self) -> str:
        left = self.parse_equality()
        while self.match("&&"):
            right = self.parse_equality()
            left = f"({left} and {right})"
        return left

    def parse_equality(self) -> str:
        left = self.parse_relational()
        while self.peek().val in ("==", "!="):
            op = self.next().val
            right = self.parse_relational()
            left = f"({left} {op} {right})"
        return left

    def parse_relational(self) -> str:
        left = self.parse_additive()
        while self.peek().val in ("<", "<=", ">", ">="):
            op = self.next().val
            right = self.parse_additive()
            left = f"({left} {op} {right})"
        return left

    def parse_additive(self) -> str:
        left = self.parse_multiplicative()
        while self.peek().val in ("+", "-"):
            op = self.next().val
            right = self.parse_multiplicative()
            left = f"({left} {op} {right})"
        return left

    def parse_multiplicative(self) -> str:
        left = self.parse_unary()
        while self.peek().val in ("*", "/", "%"):
            op = self.next().val
            right = self.parse_unary()
            left = f"({left} {op} {right})"
        return left

    def parse_unary(self) -> str:
        if self.match("+"):
            return f"+{self.parse_unary()}"
        if self.match("-"):
            return f"-{self.parse_unary()}"
        if self.match("!"):
            return f"(not {self.parse_unary()})"
        return self.parse_postfix()

    def parse_postfix(self) -> str:
        atom = self.parse_atom()
        while True:
            if self.match("["):
                idx = self.parse_expr()
                self.expect("]")
                atom = f"{atom}[{idx}]"
            elif self.peek().val == "(" and isinstance(atom, str):
                args, kwargs = self.parse_call_args()
                arg_strs = args + [f"{k}={v}" for k, v in kwargs.items()]
                if atom in ("sin", "cos", "tan"):
                    atom = f"math.{atom}(math.radians({', '.join(arg_strs)}))"
                elif atom in ("asin", "acos", "atan", "atan2"):
                    atom = f"math.degrees(math.{atom}({', '.join(arg_strs)}))"
                elif atom in ("sqrt", "pow", "abs", "floor", "ceil", "round", "exp", "log"):
                    atom = f"math.{atom}({', '.join(arg_strs)})" if hasattr(math, atom) else f"{atom}({', '.join(arg_strs)})"
                elif atom in ("min", "max"):
                    atom = f"{atom}({', '.join(arg_strs)})"
                else:
                    atom = f"{atom}({', '.join(arg_strs)})"
            else:
                break
        return atom

    def parse_atom(self) -> str:
        t = self.next()
        if t.type == TOK_NUM:
            return t.val
        if t.type == TOK_STR:
            return t.val
        if t.type == TOK_IDENT:
            val = t.val
            if val == "true":
                return "True"
            if val == "false":
                return "False"
            if val == "undef":
                return "None"
            if val == "PI":
                return "math.pi"
            clean_name = re.sub(r"^\$", "", val)
            return clean_name
        if t.val == "(":
            e = self.parse_expr()
            self.expect(")")
            return f"({e})"
        if t.val == "[":
            if self.match("]"):
                return "[]"
            first = self.parse_expr()
            if self.match(":"):
                second = self.parse_expr()
                if self.match(":"):
                    third = self.parse_expr()
                    self.expect("]")
                    return f"list(range(int({first}), int({third}) + 1, int({second})))"
                else:
                    self.expect("]")
                    return f"list(range(int({first}), int({second}) + 1))"
            else:
                elements = [first]
                while self.match(","):
                    if self.peek().val == "]":
                        break
                    elements.append(self.parse_expr())
                self.expect("]")
                return f"[{', '.join(elements)}]"

        raise SyntaxError(f"Unexpected token '{t.val}' at line {t.line}")


# -----------------------------------------------------------------------------
# Code Generator (Transpiler)
# -----------------------------------------------------------------------------

class CodeGenerator:
    def __init__(self):
        self.lines: List[str] = []
        self.indent_level = 0
        self.var_counter = 0

    def gen_var(self, prefix: str = "obj") -> str:
        self.var_counter += 1
        return f"{prefix}_{self.var_counter}"

    def emit(self, line: str = ""):
        if line:
            self.lines.append("    " * self.indent_level + line)
        else:
            self.lines.append("")

    def transpile(self, ast_nodes: List[ASTNode], model_name: str = "OpenSCAD_Model") -> str:
        self.lines = [
            "# Transpiled from OpenSCAD to ScriptCAD Python",
            "import math",
            "from scriptcad import *",
            ""
        ]

        top_level_objects = []

        for node in ast_nodes:
            if isinstance(node, VarAssign):
                self.emit(f"{node.name} = {node.expr}")
            elif isinstance(node, FuncDef):
                params_str = ", ".join(node.params)
                self.emit(f"def {node.name}({params_str}):")
                self.indent_level += 1
                self.emit(f"return {node.expr}")
                self.indent_level -= 1
                self.emit("")
            elif isinstance(node, ModuleDef):
                self.transpile_module_def(node)
            else:
                v = self.transpile_geometry_node(node)
                if v:
                    top_level_objects.append(v)

        self.emit("")
        if len(top_level_objects) == 1:
            self.emit(f"result = {top_level_objects[0]}")
            self.emit(f'result.show("{model_name}")')
        elif len(top_level_objects) > 1:
            fuse_expr = " + ".join(top_level_objects)
            self.emit(f"result = {fuse_expr}")
            self.emit(f'result.show("{model_name}")')

        return "\n".join(self.lines)

    def transpile_module_def(self, mod: ModuleDef):
        params_str = ", ".join(mod.params)
        self.emit(f"def {mod.name}({params_str}):")
        self.indent_level += 1
        self.emit("_mod_parts = []")
        for stmt in mod.body:
            if isinstance(stmt, VarAssign):
                self.emit(f"{stmt.name} = {stmt.expr}")
            else:
                v = self.transpile_geometry_node(stmt)
                if v:
                    self.emit(f"_mod_parts.append({v})")
        self.emit("if not _mod_parts: return ShapeWrapper()")
        self.emit("res = _mod_parts[0]")
        self.emit("for p in _mod_parts[1:]: res = res + p")
        self.emit("return res")
        self.indent_level -= 1
        self.emit("")

    def transpile_geometry_node(self, node: ASTNode) -> str:
        if isinstance(node, Primitive):
            return self.transpile_primitive(node)
        elif isinstance(node, Transform):
            return self.transpile_transform(node)
        elif isinstance(node, CSGBlock):
            return self.transpile_csg(node)
        elif isinstance(node, ModuleCall):
            return self.transpile_module_call(node)
        elif isinstance(node, ForLoop):
            return self.transpile_for_loop(node)
        elif isinstance(node, IfStatement):
            return self.transpile_if(node)
        elif isinstance(node, VarAssign):
            self.emit(f"{node.name} = {node.expr}")
            return ""
        return ""

    def transpile_primitive(self, p: Primitive) -> str:
        name = p.name
        args = p.args
        kwargs = p.kwargs

        if name == "cube":
            center = kwargs.get("center", "False")
            size = kwargs.get("size") or (args[0] if args else "10.0")
            if size.startswith("[") and size.endswith("]"):
                parts = [x.strip() for x in size[1:-1].split(",")]
                if len(parts) == 3:
                    return f"Box(length={parts[0]}, width={parts[1]}, height={parts[2]}, center={center})"
                elif len(parts) == 2:
                    return f"Box(length={parts[0]}, width={parts[1]}, height=1.0, center={center})"
            return f"(Box(length={size}[0], width={size}[1], height={size}[2], center={center}) if isinstance({size}, (list, tuple)) else Box({size}, {size}, {size}, center={center}))"

        elif name == "cylinder":
            center = kwargs.get("center", "False")
            h = kwargs.get("h") or (args[0] if len(args) > 0 else "10.0")
            r = kwargs.get("r")
            d = kwargs.get("d")
            r1 = kwargs.get("r1")
            r2 = kwargs.get("r2")
            d1 = kwargs.get("d1")
            d2 = kwargs.get("d2")

            if not (r or d or r1 or r2 or d1 or d2):
                if len(args) == 2:
                    r = args[1]
                elif len(args) >= 3:
                    r1 = args[1]
                    r2 = args[2]

            if d and not r:
                r = f"({d}) / 2.0"
            if d1 and not r1:
                r1 = f"({d1}) / 2.0"
            if d2 and not r2:
                r2 = f"({d2}) / 2.0"

            if r1 is not None or r2 is not None:
                rad1 = r1 if r1 is not None else (r if r else "5.0")
                rad2 = r2 if r2 is not None else (r if r else "5.0")
                return f"Cone(radius1={rad1}, radius2={rad2}, height={h}, center={center})"
            else:
                rad = r if r is not None else "5.0"
                return f"Cylinder(r={rad}, h={h}, center={center})"

        elif name == "sphere":
            r = kwargs.get("r") or (args[0] if args else None)
            d = kwargs.get("d")
            if d and not r:
                r = f"({d}) / 2.0"
            rad = r if r else "5.0"
            return f"Sphere(r={rad})"

        elif name == "square":
            center = kwargs.get("center", "False")
            size = kwargs.get("size") or (args[0] if args else "10.0")
            if size.startswith("[") and size.endswith("]"):
                parts = [x.strip() for x in size[1:-1].split(",")]
                return f"Rectangle(length={parts[0]}, width={parts[1]}, center={center})"
            return f"(Rectangle(length={size}[0], width={size}[1], center={center}) if isinstance({size}, (list, tuple)) else Rectangle({size}, {size}, center={center}))"

        elif name == "circle":
            r = kwargs.get("r") or (args[0] if args else None)
            d = kwargs.get("d")
            if d and not r:
                r = f"({d}) / 2.0"
            rad = r if r else "5.0"
            return f"Circle(radius={rad}, filled=True)"

        elif name == "polygon":
            points = kwargs.get("points") or (args[0] if args else "[]")
            return f"Polygon(points={points}, filled=True)"

        elif name == "text":
            txt = kwargs.get("text") or (args[0] if args else '""')
            size = kwargs.get("size", "10.0")
            return f"Text(text={txt}, size={size})"

        return f"ShapeWrapper()"

    def transpile_transform(self, t: Transform) -> str:
        child_vars = []
        for c in t.children:
            res = self.transpile_geometry_node(c)
            if res:
                child_vars.append(res)

        if not child_vars:
            return "ShapeWrapper()"

        base = child_vars[0] if len(child_vars) == 1 else f"({' + '.join(child_vars)})"

        name = t.name
        args = t.args
        kwargs = t.kwargs

        if name == "translate":
            vec = kwargs.get("v") or (args[0] if args else "[0, 0, 0]")
            if vec.startswith("[") and vec.endswith("]"):
                parts = [x.strip() for x in vec[1:-1].split(",")]
                if len(parts) == 3:
                    return f"{base}.at({parts[0]}, {parts[1]}, {parts[2]})"
                elif len(parts) == 2:
                    return f"{base}.at({parts[0]}, {parts[1]}, 0)"
            return f"{base}.at({vec}[0], {vec}[1], {vec}[2] if len({vec}) > 2 else 0)"

        elif name == "rotate":
            if len(args) == 1:
                vec = args[0]
                if vec.startswith("[") and vec.endswith("]"):
                    parts = [x.strip() for x in vec[1:-1].split(",")]
                    res = base
                    if len(parts) >= 1 and parts[0] != "0": res = f"{res}.rotate_x({parts[0]})"
                    if len(parts) >= 2 and parts[1] != "0": res = f"{res}.rotate_y({parts[1]})"
                    if len(parts) >= 3 and parts[2] != "0": res = f"{res}.rotate_z({parts[2]})"
                    return res
                else:
                    return f"{base}.rotate_z({vec})"
            elif len(args) >= 2:
                angle = args[0]
                vec = args[1]
                if vec.startswith("[") and vec.endswith("]"):
                    parts = [x.strip() for x in vec[1:-1].split(",")]
                    return f"{base}.rotate(axis=({parts[0]}, {parts[1]}, {parts[2]}), angle={angle})"
                return f"{base}.rotate(axis=({vec}[0], {vec}[1], {vec}[2]), angle={angle})"

        elif name == "scale":
            vec = kwargs.get("v") or (args[0] if args else "1.0")
            return f"{base}.scale({vec}[0] if isinstance({vec}, (list, tuple)) else {vec})"

        elif name == "mirror":
            return f'{base}.mirror("XY")'

        elif name == "color":
            c = kwargs.get("c") or (args[0] if args else None)
            if c:
                clean_c = c.strip('"\'').lower()
                if clean_c in CSS_COLORS:
                    rgb = CSS_COLORS[clean_c]
                    return f"{base}.color({rgb[0]}, {rgb[1]}, {rgb[2]})"
                elif c.startswith("["):
                    parts = [x.strip() for x in c[1:-1].split(",")]
                    if len(parts) >= 3:
                        alpha = parts[3] if len(parts) >= 4 else "1.0"
                        return f"{base}.color({parts[0]}, {parts[1]}, {parts[2]}, {alpha})"
            return base

        elif name == "linear_extrude":
            h = kwargs.get("height") or (args[0] if args else "10.0")
            return f"{base}.extrude(distance={h})"

        elif name == "rotate_extrude":
            a = kwargs.get("angle") or (args[0] if args else "360.0")
            return f"{base}.revolve(angle={a})"

        return base

    def transpile_csg(self, csg: CSGBlock) -> str:
        child_vars = []
        for c in csg.children:
            res = self.transpile_geometry_node(c)
            if res:
                child_vars.append(res)

        if not child_vars:
            return "ShapeWrapper()"

        if csg.op == "difference":
            base = child_vars[0]
            for sub in child_vars[1:]:
                base = f"({base} - {sub})"
            return base
        elif csg.op == "intersection":
            base = child_vars[0]
            for other in child_vars[1:]:
                base = f"({base} & {other})"
            return base
        else:
            base = child_vars[0]
            for other in child_vars[1:]:
                base = f"({base} + {other})"
            return base

    def transpile_module_call(self, call: ModuleCall) -> str:
        args_str = ", ".join(call.args + [f"{k}={v}" for k, v in call.kwargs.items()])
        return f"{call.name}({args_str})"

    def transpile_for_loop(self, loop: ForLoop) -> str:
        loop_var_name = self.gen_var("loop_items")
        self.emit(f"{loop_var_name} = []")

        for var_name, var_expr in loop.loop_vars:
            self.emit(f"for {var_name} in {var_expr}:")
            self.indent_level += 1

        for child in loop.body:
            res = self.transpile_geometry_node(child)
            if res:
                self.emit(f"{loop_var_name}.append({res})")

        for _ in loop.loop_vars:
            self.indent_level -= 1

        fused_var = self.gen_var("fused_loop")
        self.emit(f"{fused_var} = union(*{loop_var_name}) if {loop_var_name} else ShapeWrapper()")
        return fused_var

    def transpile_if(self, if_stmt: IfStatement) -> str:
        cond_var = self.gen_var("cond_item")
        self.emit(f"if {if_stmt.cond}:")
        self.indent_level += 1
        then_items = []
        for c in if_stmt.then_body:
            res = self.transpile_geometry_node(c)
            if res: then_items.append(res)
        self.emit(f"{cond_var} = {' + '.join(then_items) if then_items else 'ShapeWrapper()'}")
        self.indent_level -= 1

        if if_stmt.else_body:
            self.emit("else:")
            self.indent_level += 1
            else_items = []
            for c in if_stmt.else_body:
                res = self.transpile_geometry_node(c)
                if res: else_items.append(res)
            self.emit(f"{cond_var} = {' + '.join(else_items) if else_items else 'ShapeWrapper()'}")
            self.indent_level -= 1
        else:
            self.emit(f"else: {cond_var} = ShapeWrapper()")

        return cond_var


# -----------------------------------------------------------------------------
# Public API & Helpers
# -----------------------------------------------------------------------------

def is_openscad_code(source: str) -> bool:
    """
    Determine if a code string is written in OpenSCAD syntax rather than Python.
    """
    clean = source.strip()
    if not clean:
        return False

    # If it contains explicit Python imports for scriptcad, it's Python
    if "from scriptcad import" in clean or "import scriptcad" in clean:
        return False

    # Fast heuristic check for typical OpenSCAD indicators
    scad_indicators = [
        r"\bdifference\s*\(\s*\)\s*\{",
        r"\bunion\s*\(\s*\)\s*\{",
        r"\bintersection\s*\(\s*\)\s*\{",
        r"\bmodule\s+[a-zA-Z0-9_]+\s*\(",
        r"\bcube\s*\(\s*\[",
        r"\bcylinder\s*\(",
        r"\btranslate\s*\(\s*\[",
        r"\brotate\s*\(\s*\[",
        r"\$fn\s*=",
        r"\$fa\s*=",
        r"\$fs\s*=",
        r"//[^\n]*\n",
        r"\blinear_extrude\s*\(",
        r"\brotate_extrude\s*\(",
    ]

    has_indicator = any(re.search(pat, clean) for pat in scad_indicators)

    # Check if code parses as valid Python
    try:
        ast.parse(clean)
        is_python = True
    except SyntaxError:
        is_python = False

    if has_indicator:
        return True

    # Semicolons and curly braces without being valid python
    if not is_python and (";" in clean and ("{" in clean or "}" in clean)):
        return True

    return False


def transpile_openscad(source: str, model_name: str = "OpenSCAD_Model") -> str:
    """
    Transpile an OpenSCAD code string into clean ScriptCAD Python code.
    """
    tokens = tokenize(source)
    parser = OpenSCADParser(tokens)
    nodes = parser.parse_program()
    gen = CodeGenerator()
    return gen.transpile(nodes, model_name=model_name)


def run_openscad(source_or_path: str, doc=None, model_name: str = "OpenSCAD_Model"):
    """
    Execute OpenSCAD code or file directly in the active FreeCAD document.
    """
    if os.path.exists(source_or_path):
        with open(source_or_path, "r", encoding="utf-8") as f:
            code = f.read()
    else:
        code = source_or_path

    py_code = transpile_openscad(code, model_name=model_name)

    # Execute in FreeCAD
    scope: Dict[str, Any] = {
        "__name__": "__main__",
        "App": App,
        "math": math
    }

    import scriptcad
    for attr in scriptcad.__all__:
        scope[attr] = getattr(scriptcad, attr)

    exec(py_code, scope)
    return scope.get("result", None)


def find_openscad_executable() -> Optional[str]:
    """
    Search for the native OpenSCAD CLI executable on the system.
    """
    path = shutil.which("openscad")
    if path:
        return path

    candidates = [
        r"C:\Program Files\OpenSCAD\openscad.exe",
        r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\OpenSCAD\openscad.exe"),
        "/usr/bin/openscad",
        "/usr/local/bin/openscad",
        "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None
