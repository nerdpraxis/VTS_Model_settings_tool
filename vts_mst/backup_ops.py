"""Timestamped copies of model JSON in the app backup area."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, List

from vts_mst.json_file_io import load_json, save_json


def resolve_backup_dir(app_root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p
    return (app_root / p).resolve()


def create_session(
    app_root: Path, backup_root_rel: str, label: str = ""
) -> Path:
    """Return new session directory backups/YYYYMMDD_HHMMSS__label/"""
    root = resolve_backup_dir(app_root, backup_root_rel)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "_".join(c for c in label if c.isalnum() or c in "._- ")[:64].strip() or "session"
    safe = safe.replace(" ", "_")
    session = root / f"{ts}__{safe}"
    session.mkdir(parents=True, exist_ok=True)
    return session


def backup_file(
    session: Path, live2d_root: Path, model_name: str, filename: str
) -> Path:
    """
    Copy <live2d_root>/<model_name>/<filename> into
    session/<model_name>/<filename>
    """
    src = live2d_root / model_name / filename
    dst = session / model_name / filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def list_sessions(backup_root: Path) -> List[Path]:
    if not backup_root.is_dir():
        return []
    dirs = [p for p in backup_root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name, reverse=True)


def list_files_in_model_backup(session: Path, model_name: str) -> List[str]:
    d = session / model_name
    if not d.is_dir():
        return []
    return sorted(
        p.name for p in d.iterdir() if p.is_file() and p.suffix.lower() == ".json"
    )


def restore_file(
    session: Path,
    live2d_root: Path,
    model_name: str,
    filename: str,
) -> Path:
    src = session / model_name / filename
    dst = live2d_root / model_name / filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def read_backup_json(session: Path, model_name: str, filename: str) -> Any:
    return load_json(session / model_name / filename)


def write_json_to_live(
    data: Any, live2d_root: Path, model_name: str, filename: str
) -> Path:
    path = live2d_root / model_name / filename
    save_json(path, data)
    return path
