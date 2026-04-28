"""Discover model folders and per-model JSON files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, Tuple


@dataclass
class ModelInfo:
    name: str
    directory: Path
    json_files: List[str] = field(default_factory=list)

    def vtube_file(self) -> Optional[str]:
        for n in self.json_files:
            if n.lower().endswith(".vtube.json"):
                return n
        return None


def scan_models(live2d_root: str | Path) -> List[ModelInfo]:
    root = Path(live2d_root)
    if not root.is_dir():
        return []
    out: List[ModelInfo] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        jsons = [
            p.name
            for p in entry.iterdir()
            if p.is_file() and p.suffix.lower() == ".json"
        ]
        jsons.sort(key=str.lower)
        out.append(ModelInfo(name=entry.name, directory=entry, json_files=jsons))
    return out


def common_json_names(a: ModelInfo, b: ModelInfo) -> List[str]:
    sa: Set[str] = set(a.json_files)
    sb: Set[str] = set(b.json_files)
    inter = sa & sb
    return sorted(inter, key=str.lower)


def paired_json_for_hotkey_summary(a: ModelInfo, b: ModelInfo) -> List[Tuple[str, str]]:
    """
    (source_filename, target_filename) pairs to scan for hotkeys.

    Includes every same-named JSON in both folders, plus the main *.vtube.json from
    each model when the basenames differ (typical when comparing two model versions).
    """
    sa: Set[str] = set(a.json_files)
    sb: Set[str] = set(b.json_files)
    out: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for name in sorted(sa & sb, key=str.lower):
        pair = (name, name)
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    va, vb = a.vtube_file(), b.vtube_file()
    if va and vb:
        pair = (va, vb)
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out
