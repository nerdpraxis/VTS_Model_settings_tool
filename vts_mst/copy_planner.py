"""Build and execute planned keyCombination writes from hotkey summary rows."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

from vts_mst.backup_ops import backup_file, write_json_to_live
from vts_mst.hotkey_compare import HotkeySummaryRow
from vts_mst.json_file_io import load_json
from vts_mst.json_paths import PathTuple, deep_clone
from vts_mst.merge_apply import set_target_leaf


@dataclass
class PlannedKeybindWrite:
    json_file: str
    label: str
    path_in_source: PathTuple
    path_in_target: PathTuple
    value: Any


def plan_keybind_writes(
    rows: List[HotkeySummaryRow],
    only_where_keybind_differs: bool,
) -> List[PlannedKeybindWrite]:
    """Copy keyCombination from A into B at matched paths (both models must already have the hotkey)."""
    out: List[PlannedKeybindWrite] = []
    for r in rows:
        if not r.in_target or r.path_keycomb_b is None:
            continue
        if only_where_keybind_differs and r.keys_match is True:
            continue
        pair = r.json_pair_label()
        label = f"{pair} — {r.name or r.hotkey_id}"
        if r.toggle_file:
            label += f" → {r.toggle_file}"
        out.append(
            PlannedKeybindWrite(
                json_file=r.json_file,
                label=label,
                path_in_source=r.path_keycomb_a,
                path_in_target=r.path_keycomb_b,
                value=deep_clone(r.raw_kc_a),
            )
        )
    return out


def execute_planned_leaf_writes(
    live2d: Path,
    tgt_model: str,
    plan: List[PlannedKeybindWrite],
    backup_session: Path,
) -> Tuple[int, str | None]:
    """
    Backup each touched target file once, then apply leaf writes and save per file.
    ``path_in_source`` is ignored at apply time (values are already on the plan).
    """
    if not plan:
        return 0, None
    by_file: dict[str, List[PlannedKeybindWrite]] = defaultdict(list)
    for p in plan:
        by_file[p.json_file].append(p)
    total = 0
    for fn, ops in by_file.items():
        try:
            backup_file(backup_session, live2d, tgt_model, fn)
            tgt_d = load_json(live2d / tgt_model / fn)
        except OSError as e:
            return total, f"{fn} backup/load: {e}"
        if not isinstance(tgt_d, dict):
            return total, f"{fn}: expected JSON object at root"
        try:
            for op in ops:
                set_target_leaf(tgt_d, op.path_in_target, deep_clone(op.value))
                total += 1
            write_json_to_live(tgt_d, live2d, tgt_model, fn)
        except Exception as e:
            return total, f"{fn} write: {e}"
    return total, None


def execute_planned_keybinds(
    live2d: Path,
    src_model: str,
    tgt_model: str,
    plan: List[PlannedKeybindWrite],
    backup_session: Path,
) -> Tuple[int, str | None]:
    """Same as :func:`execute_planned_leaf_writes`; ``src_model`` kept for call-site clarity."""
    _ = src_model
    return execute_planned_leaf_writes(live2d, tgt_model, plan, backup_session)
