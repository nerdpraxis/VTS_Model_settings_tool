# Contributing

Thanks for helping improve the VTS Model Settings Tool.

## Principles

- Keep changes **focused** (one feature or fix per PR when possible).
- **GUI code** stays under `vts_mst/` (e.g. `main_window.py`, wizards).
- **No imports** from external apps (this repo must stay standalone).
- Match existing **style** (types, naming, PyQt6 patterns).
- If you fix a user-visible bug, mention it in the PR body; optional follow-up to project docs if relevant.

## Local setup

```bash
python -3.11 -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install -r requirements-build.txt   # if you use PyInstaller
python main.py
```

## Checks before a PR

1. Run the app: **migrate summaries**, **wizards** (dry-run preview), **raw diff**.
2. If you touch the frozen build: run **`build_exe.bat`** and smoke-test `dist\VTSModelSettingsTool.exe`.
3. Run a quick **syntax/import** check: `python -c "import vts_mst.main_window"`.

## Legal

By contributing, you agree to license your contributions under the same terms as this project (**MIT** — see `LICENSE`).
