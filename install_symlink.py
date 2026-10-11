# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Installation & Linker (Backward-compatibility wrapper).
Delegates to universal installer `install.py --link`.
"""

import sys
from install import install

if __name__ == "__main__":
    sys.exit(install(mode="link"))
