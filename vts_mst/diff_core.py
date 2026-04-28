"""Compare two JSON trees into flat rows for the UI table."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Set

from vts_mst.json_paths import PathTuple, format_path, iter_paths, json_equal


class RowKind(Enum):
    SAME = auto()
    DIFFER = auto()
    ONLY_A = auto()
    ONLY_B = auto()
    TYPE_MISMATCH = auto()


@dataclass
class DiffRow:
    path_in_source: PathTuple
    path_in_target: PathTuple
    path_s: str
    value_a: Any
    value_b: Any
    kind: RowKind
    value_a_str: str
    value_b_str: str

    @property
    def path(self) -> PathTuple:
        """Legacy: prefer source path; may differ for aligned lists."""
        return self.path_in_source


def _preview(v: Any) -> str:
    if v is None:
        return "null"
    s = v if isinstance(v, str) else str(v)
    if len(s) > 200:
        return s[:197] + "..."
    return s


def _leaf_paths(obj: Any) -> dict[tuple, Any]:
    return {p: v for p, v in iter_paths(obj)}


def diff_json_trees_flat(a: Any, b: Any) -> List[DiffRow]:
    """
    Path-aligned leaf diff: same path tuple in A and B (old behavior, index-based lists).
    """
    pa, pb = _leaf_paths(a), _leaf_paths(b)
    all_paths: Set[tuple] = set(pa) | set(pb)
    sortable = sorted(all_paths, key=lambda t: (len(t), [str(x) for x in t]))
    rows: List[DiffRow] = []

    for path in sortable:
        in_a, in_b = path in pa, path in pb
        va, vb = pa.get(path), pb.get(path)
        sa, sb = _preview(va), _preview(vb)
        path_s = format_path(path)

        if in_a and in_b:
            if json_equal(va, vb):
                kind = RowKind.SAME
            else:
                ta, tb = type(va).__name__, type(vb).__name__
                kind = (
                    RowKind.TYPE_MISMATCH
                    if ta != tb
                    and not (isinstance(va, (int, float)) and isinstance(vb, (int, float)))
                    else RowKind.DIFFER
                )
            rows.append(
                DiffRow(
                    path_in_source=path,
                    path_in_target=path,
                    path_s=path_s,
                    value_a=va,
                    value_b=vb,
                    kind=kind,
                    value_a_str=sa,
                    value_b_str=sb,
                )
            )
        elif in_a:
            rows.append(
                DiffRow(
                    path_in_source=path,
                    path_in_target=path,
                    path_s=path_s,
                    value_a=va,
                    value_b=None,
                    kind=RowKind.ONLY_A,
                    value_a_str=sa,
                    value_b_str="",
                )
            )
        else:
            rows.append(
                DiffRow(
                    path_in_source=path,
                    path_in_target=path,
                    path_s=path_s,
                    value_a=None,
                    value_b=vb,
                    kind=RowKind.ONLY_B,
                    value_a_str="",
                    value_b_str=sb,
                )
            )
    return rows


def diff_json_trees(
    a: Any, b: Any, use_aligned: bool = True, id_keys: tuple[str, ...] | None = None
) -> List[DiffRow]:
    """
    Default: tree diff with list-of-dict alignment (hotkeyID, name, …).
    Set use_aligned False for strict index path matching.
    """
    if not use_aligned:
        return diff_json_trees_flat(a, b)
    from vts_mst import tree_diff

    return tree_diff.diff_trees(a, b, id_keys)
