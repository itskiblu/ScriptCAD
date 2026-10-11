# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 ScriptCAD Team

"""
Unit tests for FreeCAD package.xml metadata compliance.
"""

import os
import re
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_XML = os.path.join(REPO_ROOT, "package.xml")


class TestPackageMetadata(unittest.TestCase):
    """Test package.xml structure against FreeCAD Addon Manager requirements."""

    def setUp(self):
        self.assertTrue(os.path.exists(PACKAGE_XML), "package.xml file must exist in repository root")
        self.tree = ET.parse(PACKAGE_XML)
        self.root = self.tree.getroot()

    def _find_text(self, tag_name: str) -> str:
        for child in self.root:
            if child.tag.split("}")[-1] == tag_name:
                return (child.text or "").strip()
        return ""

    def _find_elem(self, tag_name: str):
        for child in self.root:
            if child.tag.split("}")[-1] == tag_name:
                return child
        return None

    def test_root_tag_and_format(self):
        self.assertEqual(self.root.tag.split("}")[-1], "package")
        self.assertEqual(self.root.attrib.get("format"), "1")
        self.assertIn("https://wiki.freecad.org/Package_Metadata", self.root.tag)

    def test_name_and_version(self):
        name = self._find_text("name")
        self.assertEqual(name, "ScriptCAD")

        version = self._find_text("version")
        self.assertTrue(bool(re.match(r"^\d+\.\d+\.\d+", version)), f"Invalid SemVer: {version}")

        date = self._find_text("date")
        self.assertTrue(bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date)), f"Invalid date: {date}")

    def test_description(self):
        desc = self._find_text("description")
        self.assertGreater(len(desc), 10)
        self.assertNotIn("<", desc, "Description should not contain HTML/XML markup")

    def test_maintainer_and_author(self):
        maintainer = self._find_elem("maintainer")
        self.assertIsNotNone(maintainer)
        self.assertTrue(maintainer.attrib.get("email"))

        author = self._find_elem("author")
        self.assertIsNotNone(author)
        self.assertTrue(author.attrib.get("email"))

    def test_license(self):
        lic = self._find_elem("license")
        self.assertIsNotNone(lic)
        self.assertEqual(lic.text.strip(), "LGPL-2.1-or-later")
        lic_file = lic.attrib.get("file", "LICENSE")
        self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, lic_file)))

    def test_urls(self):
        urls = [c for c in self.root if c.tag.split("}")[-1] == "url"]
        url_types = {u.attrib.get("type"): u.text.strip() for u in urls}

        self.assertIn("repository", url_types)
        self.assertTrue(url_types["repository"].startswith("https://github.com/"))

        self.assertIn("readme", url_types)
        self.assertTrue(url_types["readme"].startswith("http"), "Readme URL must be full HTTP URL")

        self.assertIn("bugtracker", url_types)

    def test_workbench_content(self):
        content = self._find_elem("content")
        self.assertIsNotNone(content)

        wb = None
        for c in content:
            if c.tag.split("}")[-1] == "workbench":
                wb = c
                break
        self.assertIsNotNone(wb, "Content must contain a <workbench> element")

        classname = None
        for c in wb:
            if c.tag.split("}")[-1] == "classname":
                classname = c.text.strip()
        self.assertEqual(classname, "ScriptCADWorkbench")

    def test_icons_exist_and_are_valid_svg(self):
        icon_path_rel = self._find_text("icon")
        self.assertTrue(icon_path_rel)
        full_path = os.path.join(REPO_ROOT, icon_path_rel.replace("/", os.sep))
        self.assertTrue(os.path.exists(full_path), f"Icon not found: {full_path}")

        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<svg", content)
        self.assertIn("</svg>", content)


if __name__ == "__main__":
    unittest.main()
