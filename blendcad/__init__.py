"""
BlendCAD backward-compatibility alias module.
Redirects all imports to the renamed `scriptcad` package.
"""

from scriptcad import *
from scriptcad import __all__ as _all_exports

__all__ = _all_exports
