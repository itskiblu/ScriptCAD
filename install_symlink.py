# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Installation & Linker:
Creates a directory junction from this repository into FreeCAD's Mod folder.
Works automatically for FreeCAD 1.1, 1.0, and 0.2x.
"""

import os
import sys
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
APPDATA = os.environ.get("APPDATA", "")

CANDIDATE_MOD_DIRS = [
    os.path.join(APPDATA, "FreeCAD", "v1-1", "Mod"),
    os.path.join(APPDATA, "FreeCAD", "v1-0", "Mod"),
    os.path.join(APPDATA, "FreeCAD", "Mod"),
]

def install():
    print(f"Installing ScriptCAD from:\n  {PROJECT_DIR}\n")
    installed_count = 0

    for mod_dir in CANDIDATE_MOD_DIRS:
        if os.path.exists(mod_dir):
            target_link = os.path.join(mod_dir, "ScriptCAD")
            old_link = os.path.join(mod_dir, "BlendCAD")
            print(f"Found FreeCAD Mod folder:\n  {mod_dir}")

            # Remove obsolete BlendCAD junction if present
            if os.path.exists(old_link):
                try:
                    subprocess.run(f'cmd /c rmdir "{old_link}"', shell=True, capture_output=True)
                    print(f"  [CLEANUP] Removed legacy link: {old_link}")
                except Exception as e:
                    print(f"  Warning removing legacy link: {e}")

            if os.path.exists(target_link):
                print(f"  Target already exists: {target_link}")
                installed_count += 1
                continue

            try:
                # Use Windows Directory Junction (no admin rights needed!)
                cmd = f'cmd /c mklink /J "{target_link}" "{PROJECT_DIR}"'
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if res.returncode == 0:
                    print(f"  [OK] Linked successfully via Directory Junction: {target_link}")
                    installed_count += 1
                else:
                    print(f"  mklink output: {res.stderr or res.stdout}")
            except Exception as e:
                print(f"  Error creating junction: {e}")

    if installed_count > 0:
        print("\n[SUCCESS] ScriptCAD is now linked to FreeCAD!")
        print("Launch FreeCAD, and select 'ScriptCAD' from the Workbench dropdown.")
    else:
        print("\n[WARNING] Could not find FreeCAD Mod folder automatically.")

if __name__ == "__main__":
    install()
