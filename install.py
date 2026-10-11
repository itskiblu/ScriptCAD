# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Universal Installer:
Installs or symlinks ScriptCAD into FreeCAD's Mod directory.
Supports Windows, Linux, and macOS across FreeCAD 1.1, 1.0, and 0.2x.

Usage:
    python install.py               # Links via Directory Junction / Symlink (default)
    python install.py --copy        # Copies files directly (standalone installation)
    python install.py --uninstall   # Removes ScriptCAD from FreeCAD Mod folders
    python install.py --target PATH # Installs into a specific FreeCAD Mod folder
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_NAME = "ScriptCAD"
LEGACY_NAME = "BlendCAD"


def get_candidate_mod_dirs() -> list:
    """Detect candidate FreeCAD Mod directories based on the operating system."""
    system = platform.system()
    candidates = []

    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.extend([
                os.path.join(appdata, "FreeCAD", "v1-1", "Mod"),
                os.path.join(appdata, "FreeCAD", "v1-0", "Mod"),
                os.path.join(appdata, "FreeCAD", "Mod"),
            ])
    elif system == "Darwin":  # macOS
        home = os.path.expanduser("~")
        candidates.extend([
            os.path.join(home, "Library", "Application Support", "FreeCAD", "v1-1", "Mod"),
            os.path.join(home, "Library", "Application Support", "FreeCAD", "v1-0", "Mod"),
            os.path.join(home, "Library", "Application Support", "FreeCAD", "Mod"),
        ])
    else:  # Linux / Unix
        home = os.path.expanduser("~")
        candidates.extend([
            os.path.join(home, ".local", "share", "FreeCAD", "v1-1", "Mod"),
            os.path.join(home, ".local", "share", "FreeCAD", "v1-0", "Mod"),
            os.path.join(home, ".local", "share", "FreeCAD", "Mod"),
            os.path.join(home, ".FreeCAD", "Mod"),
        ])

    return candidates


def remove_path(path: str) -> bool:
    """Safely remove a file, symlink, junction, or directory."""
    if not os.path.exists(path) and not os.path.islink(path):
        return False

    try:
        if os.path.islink(path):
            os.unlink(path)
            return True
        elif os.path.isdir(path):
            # On Windows, Directory Junctions might not report as islink
            if platform.system() == "Windows":
                res = subprocess.run(f'cmd /c rmdir "{path}"', shell=True, capture_output=True)
                if res.returncode == 0:
                    return True
            shutil.rmtree(path)
            return True
        else:
            os.remove(path)
            return True
    except Exception as e:
        print(f"  Warning removing {path}: {e}")
        return False


def link_addon(target_link: str, source_dir: str) -> bool:
    """Create directory junction on Windows or symlink on Unix."""
    if platform.system() == "Windows":
        try:
            # Use Windows Directory Junction (requires no admin privileges)
            cmd = f'cmd /c mklink /J "{target_link}" "{source_dir}"'
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0 and os.path.exists(target_link):
                return True
        except Exception:
            pass

    try:
        os.symlink(source_dir, target_link, target_is_directory=True)
        return True
    except Exception as e:
        print(f"  Failed to create symlink: {e}")
        return False


def copy_addon(target_dir: str, source_dir: str) -> bool:
    """Copy the addon files excluding git and temporary caches."""
    ignore_patterns = shutil.ignore_patterns(
        ".git*",
        "__pycache__",
        "*.pyc",
        "*.pyo",
        ".vscode",
        ".idea",
        "dist",
        "build",
        "tests",
        "*.egg-info"
    )
    try:
        shutil.copytree(source_dir, target_dir, ignore=ignore_patterns)
        return True
    except Exception as e:
        print(f"  Failed to copy addon files: {e}")
        return False


def install(mode: str = "link", custom_target: str = None):
    print("=" * 60)
    print(f"  ScriptCAD FreeCAD Workbench Installer ({mode.upper()} mode)")
    print("=" * 60)
    print(f"Source Directory: {PROJECT_DIR}\n")

    if custom_target:
        mod_dirs = [custom_target]
    else:
        candidates = get_candidate_mod_dirs()
        # Find all existing Mod directories
        mod_dirs = [d for d in candidates if os.path.exists(d)]
        # If none exist yet, pick the most appropriate candidate to create
        if not mod_dirs and candidates:
            mod_dirs = [candidates[0]]
            os.makedirs(mod_dirs[0], exist_ok=True)
            print(f"Created FreeCAD Mod folder: {mod_dirs[0]}")

    if not mod_dirs:
        print("[ERROR] No FreeCAD Mod directory found.")
        print("Please specify one with: python install.py --target <path_to_Mod>")
        return 1

    installed_count = 0

    for mod_dir in mod_dirs:
        print(f"Processing FreeCAD Mod folder:\n  {mod_dir}")
        os.makedirs(mod_dir, exist_ok=True)

        target_path = os.path.join(mod_dir, ADDON_NAME)
        legacy_path = os.path.join(mod_dir, LEGACY_NAME)

        # 1. Clean up obsolete legacy BlendCAD installation if present
        if os.path.exists(legacy_path) or os.path.islink(legacy_path):
            if remove_path(legacy_path):
                print(f"  [CLEANUP] Removed legacy folder: {legacy_path}")

        # 2. If target already exists, clean it up before reinstalling
        if os.path.exists(target_path) or os.path.islink(target_path):
            print(f"  Existing installation found, updating...")
            remove_path(target_path)

        # 3. Perform installation
        if mode == "link":
            if link_addon(target_path, PROJECT_DIR):
                print(f"  [OK] Linked successfully via Directory Junction / Symlink: {target_path}")
                installed_count += 1
            else:
                print(f"  [FALLBACK] Symlink failed; attempting direct copy...")
                if copy_addon(target_path, PROJECT_DIR):
                    print(f"  [OK] Copied successfully: {target_path}")
                    installed_count += 1
        elif mode == "copy":
            if copy_addon(target_path, PROJECT_DIR):
                print(f"  [OK] Copied successfully: {target_path}")
                installed_count += 1

    print("-" * 60)
    if installed_count > 0:
        print("[SUCCESS] ScriptCAD is now installed in FreeCAD!")
        print("1. Launch FreeCAD.")
        print("2. Select 'ScriptCAD' from the Workbench dropdown.")
        print("3. Enjoy procedural CAD solid modeling & mesh art scripting!")
        return 0
    else:
        print("[WARNING] Installation failed for all candidate locations.")
        return 1


def uninstall(custom_target: str = None):
    print("=" * 60)
    print("  ScriptCAD FreeCAD Workbench Uninstaller")
    print("=" * 60)

    if custom_target:
        mod_dirs = [custom_target]
    else:
        mod_dirs = [d for d in get_candidate_mod_dirs() if os.path.exists(d)]

    removed_count = 0
    for mod_dir in mod_dirs:
        for name in [ADDON_NAME, LEGACY_NAME]:
            path = os.path.join(mod_dir, name)
            if os.path.exists(path) or os.path.islink(path):
                if remove_path(path):
                    print(f"[REMOVED] {path}")
                    removed_count += 1

    if removed_count > 0:
        print(f"\n[SUCCESS] Removed {removed_count} ScriptCAD installation(s).")
    else:
        print("\nNo ScriptCAD installations found to remove.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="ScriptCAD FreeCAD Workbench Installer")
    parser.add_argument("--copy", action="store_true", help="Copy files directly instead of symlinking")
    parser.add_argument("--link", action="store_true", help="Create directory junction / symlink (default)")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall ScriptCAD from FreeCAD")
    parser.add_argument("--target", type=str, default=None, help="Custom FreeCAD Mod directory path")

    args = parser.parse_args()

    if args.uninstall:
        return uninstall(custom_target=args.target)

    mode = "copy" if args.copy else "link"
    return install(mode=mode, custom_target=args.target)


if __name__ == "__main__":
    sys.exit(main())
