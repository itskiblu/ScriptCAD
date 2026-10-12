# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
ScriptCAD Distribution & Packaging Tool:
Validates package metadata and builds a production-ready FreeCAD addon ZIP archive.

Usage:
    python package.py           # Validates and builds dist/ScriptCAD-v<version>.zip
    python package.py --verify  # Validates package.xml without building archive
"""

import argparse
import hashlib
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_XML_PATH = os.path.join(PROJECT_DIR, "package.xml")
DIST_DIR = os.path.join(PROJECT_DIR, "dist")

# Files and directories to package into distribution release
INCLUDE_ITEMS = [
    "Init.py",
    "InitGui.py",
    "package.xml",
    "LICENSE",
    "README.md",
    "CHANGELOG.md",
    "llms.txt",
    "AGENTS.md",
    "install.py",
    "Resources",
    "gui",
    "scriptcad",
    "blendcad",
]

EXCLUDE_PATTERNS = [
    r"__pycache__",
    r"\.py[cod]$",
    r"\.git",
    r"\.vscode",
    r"\.idea",
    r"\.DS_Store",
    r"Thumbs\.db",
]


def validate_metadata() -> dict:
    """Validate package.xml against FreeCAD Addon Manager standards."""
    print("[1/3] Validating package.xml metadata...")
    if not os.path.exists(PACKAGE_XML_PATH):
        raise FileNotFoundError(f"Missing package.xml at {PACKAGE_XML_PATH}")

    try:
        tree = ET.parse(PACKAGE_XML_PATH)
        root = tree.getroot()
    except Exception as e:
        raise ValueError(f"Invalid XML in package.xml: {e}")

    # Verify namespace & format
    if root.tag.split("}")[-1] != "package":
        raise ValueError(f"Expected root tag <package>, got <{root.tag}>")

    format_ver = root.attrib.get("format")
    if format_ver != "1":
        raise ValueError(f"Expected format='1' on <package>, found '{format_ver}'")

    # Helper to find tag with or without namespace
    def find_text(elem, tag_name):
        for child in elem:
            if child.tag.split("}")[-1] == tag_name:
                return (child.text or "").strip()
        return None

    def find_elem(elem, tag_name):
        for child in elem:
            if child.tag.split("}")[-1] == tag_name:
                return child
        return None

    name = find_text(root, "name")
    version = find_text(root, "version")
    date = find_text(root, "date")
    desc = find_text(root, "description")
    license_elem = find_elem(root, "license")
    maintainer_elem = find_elem(root, "maintainer")
    content_elem = find_elem(root, "content")
    icon_text = find_text(root, "icon")

    # Validate required tags
    assert name, "Missing required tag <name>"
    assert version, "Missing required tag <version>"
    assert date, "Missing required tag <date>"
    assert desc, "Missing required tag <description>"
    assert license_elem is not None, "Missing required tag <license>"
    assert maintainer_elem is not None, "Missing required tag <maintainer>"
    assert content_elem is not None, "Missing required tag <content>"

    # Check version format (SemVer)
    if not re.match(r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$", version):
        raise ValueError(f"Version '{version}' is not a valid Semantic Version string")

    # Check date format (YYYY-MM-DD)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ValueError(f"Date '{date}' must match YYYY-MM-DD format")

    # Check license file
    license_file = license_elem.attrib.get("file", "LICENSE")
    license_path = os.path.join(PROJECT_DIR, license_file)
    if not os.path.exists(license_path):
        raise FileNotFoundError(f"License file '{license_file}' specified in package.xml not found on disk")

    # Check workbench content
    wb_elem = find_elem(content_elem, "workbench")
    if wb_elem is None:
        raise ValueError("Missing <workbench> element inside <content>")

    classname = find_text(wb_elem, "classname")
    if classname != "ScriptCADWorkbench":
        raise ValueError(f"Workbench <classname> must be 'ScriptCADWorkbench', got '{classname}'")

    # Check icon files
    for icon_ref in [icon_text, find_text(wb_elem, "icon")]:
        if icon_ref:
            full_icon_path = os.path.join(PROJECT_DIR, icon_ref.replace("/", os.sep))
            if not os.path.exists(full_icon_path):
                raise FileNotFoundError(f"Icon file referenced in package.xml not found: {icon_ref}")
            if os.path.getsize(full_icon_path) == 0:
                raise ValueError(f"Icon file is empty: {icon_ref}")

    # Check readme URL
    for child in root:
        if child.tag.split("}")[-1] == "url" and child.attrib.get("type") == "readme":
            readme_url = (child.text or "").strip()
            if not readme_url.startswith("http://") and not readme_url.startswith("https://"):
                raise ValueError(
                    f"The <url type='readme'> must be an HTTP(S) URL for remote Addon Manager rendering, got '{readme_url}'"
                )

    print(f"  [OK] Valid FreeCAD Package Metadata: {name} v{version} ({date})")
    return {
        "name": name,
        "version": version,
        "date": date,
        "description": desc,
    }


def should_exclude(rel_path: str) -> bool:
    """Check if file matches any exclusion pattern."""
    normalized = rel_path.replace("\\", "/")
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, normalized):
            return True
    return False


def build_package(metadata: dict) -> str:
    """Create a clean distribution zip archive."""
    print("\n[2/3] Collecting files for distribution...")
    os.makedirs(DIST_DIR, exist_ok=True)

    name = metadata["name"]
    version = metadata["version"]
    zip_filename = f"{name}-v{version}.zip"
    zip_path = os.path.join(DIST_DIR, zip_filename)

    # Collect all files to include
    files_to_pack = []
    for item in INCLUDE_ITEMS:
        item_path = os.path.join(PROJECT_DIR, item)
        if not os.path.exists(item_path):
            print(f"  [WARNING] Item not found: {item}")
            continue

        if os.path.isfile(item_path):
            if not should_exclude(item):
                files_to_pack.append((item_path, f"{name}/{item}"))
        elif os.path.isdir(item_path):
            for root, dirs, files in os.walk(item_path):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, PROJECT_DIR)
                    if not should_exclude(rel_p):
                        arc_name = f"{name}/{rel_p.replace(os.sep, '/')}"
                        files_to_pack.append((full_p, arc_name))

    print(f"  Collected {len(files_to_pack)} distribution files.")

    print(f"\n[3/3] Generating release archive: {zip_filename}...")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for full_p, arc_name in files_to_pack:
            zf.write(full_p, arc_name)

    # Also generate a generic ScriptCAD.zip for easy rolling links
    generic_zip_path = os.path.join(DIST_DIR, f"{name}.zip")
    with zipfile.ZipFile(generic_zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for full_p, arc_name in files_to_pack:
            zf.write(full_p, arc_name)

    # Calculate SHA256 checksum
    hasher = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    sha256 = hasher.hexdigest()

    checksum_file = os.path.join(DIST_DIR, f"{zip_filename}.sha256")
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write(f"{sha256}  {zip_filename}\n")

    size_kb = os.path.getsize(zip_path) / 1024
    print("=" * 60)
    print(f"[SUCCESS] Package created successfully!")
    print(f"Archive:   {zip_path}")
    print(f"Size:      {size_kb:.1f} KiB")
    print(f"SHA-256:   {sha256}")
    print(f"Checksum:  {checksum_file}")
    print("=" * 60)
    return zip_path


def main():
    parser = argparse.ArgumentParser(description="ScriptCAD Packaging & Distribution Tool")
    parser.add_argument("--verify", action="store_true", help="Verify package.xml metadata only")
    args = parser.parse_args()

    try:
        meta = validate_metadata()
        if args.verify:
            print("[SUCCESS] Metadata verification passed.")
            return 0
        build_package(meta)
        return 0
    except Exception as e:
        print(f"\n[ERROR] Packaging failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
