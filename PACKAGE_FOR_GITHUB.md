# Publishing this folder as its own GitHub repository

If this folder currently lives inside another project (e.g. a control panel repo), use one of these approaches:

## Option A: Subfolder as new repo (`git subtree` or copy)

1. Copy **`vts_model_settings_tool/`** to a new directory (or use `git subtree split`).
2. Inside that directory:
   ```bash
   git init
   git add .
   git commit -m "Initial import: VTS Model Settings Tool"
   ```
3. Create an empty repo on GitHub and push:
   ```bash
   git remote add origin https://github.com/YOU/vts-model-settings-tool.git
   git branch -M main
   git push -u origin main
   ```

## Option B: Monorepo — publish only this subfolder

GitHub does not support “subfolder as default repo root” natively; prefer Option A for a clean standalone project.

## Before pushing

- Ensure **no** `venv/`, `dist/`, `build/`, or personal **`config.ini`** are committed (see `.gitignore`).
- Replace `v1.0.0` and dates in **`RELEASE_DESCRIPTION.template.md`** when tagging.
- Attach **`VTSModelSettingsTool.exe`** to the GitHub **Release** after running `build_exe.bat` on a clean machine.

## Release checklist

1. Update version strings / changelog in `RELEASE_DESCRIPTION.template.md`.
2. Tag: `git tag -a v1.0.0 -m "Release v1.0.0"`.
3. Push tag: `git push origin v1.0.0`.
4. On GitHub: **Releases → Draft release** → paste body from template or from your local **`RELEASE_DESCRIPTION.local.txt`**.
