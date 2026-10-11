# Submitting ScriptCAD to the Official FreeCAD Addon Catalog

This guide provides step-by-step instructions for submitting ScriptCAD to the official FreeCAD Addon Index so that all FreeCAD users worldwide can find, install, and update ScriptCAD directly from FreeCAD's built-in **Addon Manager**.

---

## 1. Prerequisites Checklist

Before submitting, ensure all packaging standards are met:

- [x] **`package.xml` valid**: Matches FreeCAD Package Metadata format 1, includes valid SemVer version, maintainer, license, tags, and valid raw/blob README URL.
- [x] **Icon provided**: Vector SVG icon located at `Resources/icons/ScriptCAD_Workbench.svg` and referenced in `package.xml`.
- [x] **Workbench Entry**: Main Python class `ScriptCADWorkbench` in `InitGui.py` matching `<classname>`.
- [x] **Open Source License**: LGPL-2.1-or-later with full text in `LICENSE`.
- [x] **Test suite**: 100% passing tests via `python tests/run_tests.py`.
- [x] **Clean release package**: Archive built and verified via `python package.py`.

---

## 2. FreeCAD 1.0+ Official Index Submission (`FreeCAD/Addons`)

FreeCAD 1.0 and 1.1 use the new [FreeCAD/Addons](https://github.com/FreeCAD/Addons) repository.

### Step 1: Fork the Repository
1. Navigate to [https://github.com/FreeCAD/Addons](https://github.com/FreeCAD/Addons).
2. Click **Fork** to create your own copy.

### Step 2: Edit `Data/Index.json`
1. Open `Data/Index.json` in your fork.
2. In alphabetical order under the existing addons, add the entry for `ScriptCAD`:

```json
  "ScriptCAD": [
    {
      "repository": "https://github.com/itskiblu/ScriptCAD",
      "git_ref": "main",
      "branch_display_name": "main",
      "zip_url": "https://github.com/itskiblu/ScriptCAD/archive/refs/heads/main.zip",
      "curated": false
    }
  ],
```

### Step 3: Open a Pull Request
1. Commit the change with the message: `Add ScriptCAD workbench to Index.json`.
2. Submit a Pull Request from your fork to `FreeCAD/Addons:main`.
3. Title: `Add ScriptCAD workbench`
4. Description:
   ```markdown
   ### Addon Details
   - **Name:** ScriptCAD
   - **Description:** Procedural CAD solid modeling and 3D mesh art scripting workbench with an integrated live code editor for FreeCAD.
   - **Repository:** https://github.com/itskiblu/ScriptCAD
   - **License:** LGPL-2.1-or-later
   - **Maintainer:** ScriptCAD Team
   - **FreeCAD Compatibility:** FreeCAD 0.20, 0.21, 1.0, 1.1+
   - **Python Compatibility:** Python 3.8+
   - `package.xml` has been validated against AddonManager metadata specifications.
   ```

---

## 3. Legacy FreeCAD 0.20 / 0.21 Catalog Submission (`FreeCAD/FreeCAD-addons`)

For older FreeCAD installations (< 1.0), the legacy catalog is maintained at [FreeCAD/FreeCAD-addons](https://github.com/FreeCAD/FreeCAD-addons):

1. Fork [FreeCAD/FreeCAD-addons](https://github.com/FreeCAD/FreeCAD-addons).
2. Add `ScriptCAD` as a git submodule or submit an issue requesting addition.
3. Submit a Pull Request to `FreeCAD/FreeCAD-addons:master`.

---

## 4. Testing Before Official Index Merge

Anyone can install and test ScriptCAD in FreeCAD right now without waiting for the official index PR to be merged:

1. Open FreeCAD.
2. Go to **Tools → Addon Manager**.
3. Click the **Gear (⚙) icon** in the bottom-left corner of the Addon Manager dialog.
4. Under **Custom repositories**, click **+ Add repository**.
5. Set:
   - **URL:** `https://github.com/itskiblu/ScriptCAD`
   - **Branch:** `main`
6. Click **Save**.
7. Close and reopen the Addon Manager — **ScriptCAD** will appear with its icon, description, and 1-click **Install** button!
