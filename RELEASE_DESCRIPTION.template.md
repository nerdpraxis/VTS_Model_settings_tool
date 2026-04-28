# Template: GitHub release description

Copy everything **below** the line into the GitHub release notes (or copy into `RELEASE_DESCRIPTION.local.txt` for a private draft; that filename is gitignored).

---

## VTS Model Settings Tool v1.0.0

**Released:** YYYY-MM-DD

### What’s this?

A **standalone Windows-friendly** tool (Python + PyQt6, optional PyInstaller `.exe`) to **compare and migrate** VTube Studio **on-disk model JSON** between two Live2D model folders — hotkeys (`Triggers` / `keyCombination`), `ParameterSettings` (input name, clamps, smoothing, ranges), plus a **raw JSON diff** tab for power users. Works **offline** via file I/O (no VTS API required).

### Highlights

- **Hotkey summary** across all relevant JSON pairs, including **`*.vtube.json` with different filenames** per folder.
- **Guided wizards** for hotkeys and parameters: choose scope → preview writes → timestamped **backup** → apply.
- **Dark UI** with resizable tables; export summaries as **TSV**.
- **Safety:** backups and per-file restore; strongly recommended to **close VTube Studio** before writing.

### Downloads

- **Binary (Windows):** attach `VTSModelSettingsTool.exe` from `dist/` (build locally with `build_exe.bat`, or use your CI artifact).
- **Source:** clone this repo; `pip install -r requirements.txt` and `python main.py`.

### Quick setup

1. Point **Live2D models path** at:  
   `…\VTube Studio_Data\StreamingAssets\Live2DModels`  
   (or your custom install location).
2. **Scan models** → pick **source (A)** and **target (B)**.
3. **Refresh** Hotkey / Parameter summaries → run wizards as needed.

### Known limitations

- Wizards update **existing** matched hotkey / parameter rows only; they do **not** append brand-new array elements if the target model has no matching slot.
- Primary pairing uses the first `*.vtube.json` per folder (sorted name) when names differ — models with multiple vtube files may need manual care.

### Files in this release

| Artifact | Description |
|----------|-------------|
| `VTSModelSettingsTool.exe` | Windowed one-file build (Windows) |
| Source zip / git tag | Full tree |

### Checksums

*(Optional: add SHA256 for your uploaded exe)*

```
SHA256 (VTSModelSettingsTool.exe) = …
```

### Thanks / notes

Third-party tool; **not** affiliated with DenchiSoft. Use at your own risk; keep backups.

---

### Full changelog

#### Added
- Initial public release as standalone repository.
- Hotkey summary + copy wizard (Triggers + keyCombination; PascalCase disk format).
- Parameter summary + copy wizard (Input, clamps, smoothing, IN/OUT ranges).
- Raw JSON diff with list alignment and direct copy.
- Model scan, similarity hints, backup/restore, TSV export.
- `config.ini.example`, MIT `LICENSE`, documentation.

#### Changed
- Default `live2d_models_path` in-app is empty until the user sets it (portable installs).

#### Fixed
- *(List any bugfixes for this tag.)*
