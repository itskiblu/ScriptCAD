# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
BlendCAD backward-compatibility alias module.
Redirects all imports to the renamed `scriptcad` package.
"""

from scriptcad import *
from scriptcad import __all__ as _scriptcad_all

__all__ = list(_scriptcad_all)

