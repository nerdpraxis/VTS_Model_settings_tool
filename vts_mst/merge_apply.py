"""Apply a value from source tree into target tree at a given path."""

from __future__ import annotations

from typing import Any

from vts_mst.json_paths import PathTuple, deep_clone, get_at, set_at


def copy_source_leaf_to_target(
    source: Any,
    target: dict,
    path_in_source: PathTuple,
    path_in_target: PathTuple,
) -> None:
    """Copy leaf from source path to target path (for aligned list rows paths may differ)."""
    v = deep_clone(get_at(source, path_in_source))
    set_at(target, path_in_target, v)


def set_target_leaf(target: dict, path: PathTuple, value: Any) -> None:
    set_at(target, path, value)
