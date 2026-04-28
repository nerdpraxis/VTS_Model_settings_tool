# VTS Model Settings Tool — Design notes

> **For installation and usage, read [README.md](README.md).** This file is internal design / roadmap history.

**Repository layout:** this folder is intended to be published as its **own** GitHub repository (no dependency on AIKA).  
**Status:** Active; core features shipped — hotkey & parameter migration wizards, raw JSON diff, backups.

---

## 1. Purpose

Give VTubers a **separate, file-based** utility to **compare and migrate on-disk VTube Studio model JSON** between Live2D model folders (e.g. before/after a rigger update), using only **local files** (no VTS API required).

**Core workflow (target UX):**

1. Point the app at the **Live2D models root** (e.g. `.../StreamingAssets/Live2DModels`).
2. **Discover** model subfolders and optional **name similarity** grouping (e.g. common prefix `Aika_Nova-`).
3. Load **all relevant JSON** from each model directory (at minimum `*.vtube.json`; other `.json` files as first-class for diff/migrate when present).
4. **Deep-compare** structures (entire file and nested hotkeys, parameters, and any other keys VTS stores).
5. Show a **tabular / navigable** view: paths or logical rows, with **green** = same or confidently mapped, **red** = missing, conflict, or type mismatch; **amber** = fuzzy/uncertain match.
6. Allow **merging** source → target: everything user selects (not only keybinds), with **per-row** override via a **detail dialog** (edit JSON fragment or mapped field before apply).
7. **Mandatory safety:** before any write, a **full backup** of the JSON files that will be touched; **per-backup** and **per-file** restore in the UI.

**Optional / non-goals (initial build):**  
- **VTS WebSocket API** is **not** required for the core design; everything is file I/O. A future “live reload” or validation step could use the API but stays optional.

---

## 2. Standalone repository rules

| Aspect | Rule |
|--------|------|
| Code | **Self-contained** — no `import` from private parent apps; copy patterns only where license allows. |
| Virtualenv | **Own** venv: `venv/` in this repo (or user-created; see `build_exe.bat`). |
| Config | **Own** `config.ini` in this folder (paths, UI geometry, diff options, backup root). |
| Build | **Own** `requirements.txt`, `requirements-build.txt`, **`build_exe.bat`**, optional `VTSModelSettingsTool.spec`. |
| Data | Read/write only **VTS `Live2DModels/.../modelname/`** JSON and **this app’s backup directory**. |

---

## 3. Configuration (`config.ini` in this folder)

Planned sections (evolve with implementation):

- **`[Paths]`**  
  - `live2d_models_path` — root containing one folder per model (required for scan).
- **`[Backup]`**  
  - `root` — where timestamped sessions are stored (default: `backups/` under this app folder).
- **`[UI]`**  
  - Window size, last selected source/target models, table column state (optional).
- **`[Diff]`** (optional later)  
  - Similarity threshold for “fuzzy” row matching, max depth for tree flattening, include/exclude file globs.

**Persistence rule:** any field edited in the UI is saved to this `config.ini` when changed.

---

## 4. File discovery and scope (“ALL settings”)

1. For each **model directory** under `live2d_models_path`:  
   - Enumerate `*.json` (non-recursive by default; optional shallow recurse if we find real-world need).
2. **Primary file:** `*.vtube.json` (typically one per model) — **full JSON** is in scope for diff and merge.
3. **Additional JSON:** any other `.json` in the same folder (e.g. exports or auxiliary config if present) — **include in compare and backup**; user can select which files participate in a given merge.
4. **Non-JSON** (textures, moc3, etc.) — **out of scope** for v1.

**Compare semantics:**

- **Structural diff** per file: use normalized ordered walks (e.g. path → value) to build rows.
- **Arrays with identity:** for hotkey-like lists, match by stable IDs if present, else by ordered index + `name` / `type` / `file` heuristics; **conflicts** surface as red with manual resolution in the detail dialog.
- **Merge direction:** `source` model → `target` model; never overwrite without explicit user action and without backup.

---

## 5. Backup and restore (mandatory)

**Before the first write in a session:**

- Create: `backups/YYYYMMDD_HHMMSS__<label>/` (label optional user string).
- Copy **entire** set of files selected for that operation, preserving relative paths:  
  - `ModelA/foo.vtube.json` → `.../ModelA/foo.vtube.json` under backup root.

**Restore:**

- **Restore all** for that backup, or **restore one file** from the list.
- **Recommendation:** if VTS has the file open, close VTS first (document in UI); optional future check for file locks on Windows.

---

## 6. UI (high level)

- **Main window:** dark theme, white text, consistent with typical AIKA styling but **self-contained** QSS in this app.
- **Top:** path to `live2d_models_path`, browse, **Scan / Refresh**.
- **Model list** or **similarity groups** (e.g. tree or list) to pick **source** and one or more **targets**.
- **Center:** main compare surface — `QTableWidget` or `QTreeView` + model for path/value pairs; color roles for green/red/amber; buttons per row: **Map**, **Edit**, **Apply row**.
- **Detail dialog:** JSON or field-level editor for a single path; validate JSON on accept.
- **Bottom / toolbar:** **Create backup & apply** (where applicable), **Open backup folder**, **Restore** (dropdown of sessions).

**Phased UI:**

1. **v0:** window + path + config load/save.  
2. **v1 (done):** scan, common JSON file picker, leaf-level diff for two models (color by status), copy A→B, edit+apply, backup session + restore.  
3. **v2 (partial):** name-similarity suggestions (pairs + prefix groups), **aligned** `list[dict]` diff by configurable `id_keys` (default `hotkeyID`, `name`, …), `path_in_source` / `path_in_target` for different list indices, TSV export. *Still open:* multi-target batch, richer “whole hotkey object” copy.  
4. **v3:** optional VTS API smoke check, performance on huge JSON.

---

## 7. Standalone EXE and `build_exe.bat`

**Goal:** one-folder or one-file Windows executable for operators who do not use Python.

- **Tooling:** [PyInstaller](https://github.com/pyinstaller/pyinstaller) (invoked from `build_exe.bat`).
- **Typical options:**  
  - `--noconfirm --clean`  
  - `--windowed` (no console) for GUI  
  - `--onefile` or `onedir` (onedir = faster start; onefile = single artifact — bat can document the chosen default)  
  - `main.py` as entry.  
- **Config:** ship **no** secrets; first run creates `config.ini` next to the EXE (same directory as the executable) if missing — code resolves base path with `sys.executable` / `__file__` handling for frozen mode.

`build_exe.bat` responsibilities:

1. `cd` to the directory containing the bat.  
2. Create `venv` if missing: `py -3.11 -m venv venv` (or `python -m venv venv`).  
3. `venv\Scripts\activate.bat`  
4. `pip install -r requirements.txt`  
5. `pip install -r requirements-build.txt` (PyInstaller)  
6. Run PyInstaller with a fixed spec or inline args; output to `dist/`.

**Note:** The repo’s global rule “no dependency changes without permission” applies to the main AIKA app; **this subfolder** has its own `requirements*.txt` managed here.

---

## 8. Technology stack (this app only)

- **Python 3.11+** (align with your environment).
- **PyQt6** — single GUI stack; no web view required for v1.
- **stdlib:** `json`, `configparser`, `pathlib`, `shutil`, `dataclasses`, `difflib` (optional for text), `datetime`.

Optional later (only if really needed, and added to this folder’s `requirements.txt` with your approval):  
- `deepdiff` or similar for huge nested dicts — prefer stdlib first.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| VTS rewrites file while we save | User message: close VTS; optional read-only pre-check. |
| Large `vtube.json` | Virtualize table rows / lazy load sections. |
| Renamed hotkeys / items | Fuzzy + manual mapping in detail dialog. |
| Corrupt JSON | Validate before write; keep backup. |

---

## 10. Milestone checklist (living)

- [x] `PLAN.md` + folder layout + own `config.ini` template.  
- [x] `main.py` + main window + config load/save.  
- [x] `build_exe.bat` + `requirements.txt` + `requirements-build.txt`.  
- [x] JSON discovery + per-file load.  
- [x] Diff engine (leaf path/value rows + status colors + hide-identical).  
- [x] Merge + backup session + per-file restore.  
- [x] Detail editor dialog + copy/edit apply.  
- [ ] PyInstaller smoke test on clean Windows / onefolder option if onefile is slow.

---

## 11. Relation to the main AIKA app (optional)

The main app may later get a **button** that only **spawns** this tool’s `VTSModelSettingsTool.exe` or `python main.py` with **no** shared code. That integration is **not** part of this folder’s core responsibility and can be a separate, small change in AIKA when you want it.

---

*End of plan document.*
