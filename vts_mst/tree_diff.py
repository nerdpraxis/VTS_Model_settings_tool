"""
Recursive tree diff with optional alignment of list[dict] by id-like keys
(hotkeyID, name, …) so the same hotkey in different list positions still rows up.
"""

from __future__ import annotations

import json
from typing import Any, List, Set, Tuple

from vts_mst.diff_core import DiffRow, RowKind, _preview
from vts_mst.json_paths import format_path, iter_paths, json_equal
from vts_mst.list_id_keys import DEFAULT_ID_KEYS
from vts_mst.model_similarity import short_label

PathTuple = Tuple[str | int, ...]


def is_leaf_value(x: Any) -> bool:
    return not isinstance(x, (dict, list))


def _norm_id_key(v: Any) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, default=str)
    return str(v)


def _pick_id_key(
    a: list, b: list, candidates: tuple[str, ...] | None
) -> str | None:
    keys: tuple[str, ...] = candidates if candidates is not None else DEFAULT_ID_KEYS
    if not a or not b:
        return None
    best: str | None = None
    best_m = 0.0
    for key in keys:
        ca = sum(
            1
            for x in a
            if isinstance(x, dict) and _nonempty_id(x.get(key))
        )
        cb = sum(
            1
            for x in b
            if isinstance(x, dict) and _nonempty_id(x.get(key))
        )
        if ca == 0 or cb == 0:
            continue
        m = (ca + cb) / (len(a) + len(b))
        if m > best_m and min(ca, cb) >= 1:
            best_m, best = m, key
    if best is None or best_m < 0.25:
        return None
    return best


def _nonempty_id(v: Any) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    return bool(s)


def _diff_leaves(
    a: Any,
    b: Any,
    path_a: PathTuple,
    path_b: PathTuple,
    path_s: str,
) -> List[DiffRow]:
    if json_equal(a, b):
        return [
            DiffRow(
                path_in_source=path_a,
                path_in_target=path_b,
                path_s=path_s,
                value_a=a,
                value_b=b,
                kind=RowKind.SAME,
                value_a_str=_preview(a),
                value_b_str=_preview(b),
            )
        ]
    ta, tb = type(a).__name__, type(b).__name__
    kind = (
        RowKind.TYPE_MISMATCH
        if ta != tb
        and not (isinstance(a, (int, float)) and isinstance(b, (int, float)))
        else RowKind.DIFFER
    )
    return [
        DiffRow(
            path_in_source=path_a,
            path_in_target=path_b,
            path_s=path_s,
            value_a=a,
            value_b=b,
            kind=kind,
            value_a_str=_preview(a),
            value_b_str=_preview(b),
        )
    ]


def _emit_only(
    side: str,
    obj: Any,
    path_base: PathTuple,
) -> List[DiffRow]:
    """Emit leaf rows for subtree only in A or only in B. Apply paths use same tuple for A/B copy."""
    rows: List[DiffRow] = []
    for p, v in iter_paths(obj, path_base):
        disp = format_path(p)
        if side == "a":
            rows.append(
                DiffRow(
                    path_in_source=p,
                    path_in_target=p,
                    path_s=disp,
                    value_a=v,
                    value_b=None,
                    kind=RowKind.ONLY_A,
                    value_a_str=_preview(v),
                    value_b_str="",
                )
            )
        else:
            rows.append(
                DiffRow(
                    path_in_source=p,
                    path_in_target=p,
                    path_s=disp,
                    value_a=None,
                    value_b=v,
                    kind=RowKind.ONLY_B,
                    value_a_str="",
                    value_b_str=_preview(v),
                )
            )
    return rows


def diff_trees(
    a: Any,
    b: Any,
    id_keys: tuple[str, ...] | None = None,
) -> List[DiffRow]:
    return _rec(a, b, (), (), "", id_keys)


def _rec(
    a: Any,
    b: Any,
    pa: PathTuple,
    pb: PathTuple,
    path_s: str,
    id_keys: tuple[str, ...] | None,
) -> List[DiffRow]:
    if is_leaf_value(a) and is_leaf_value(b):
        return _diff_leaves(a, b, pa, pb, path_s)
    if is_leaf_value(a) or is_leaf_value(b):
        return _diff_leaves(a, b, pa, pb, path_s)

    if isinstance(a, dict) and isinstance(b, dict):
        return _rec_dict(a, b, pa, pb, path_s, id_keys)
    if isinstance(a, list) and isinstance(b, list):
        return _rec_list(a, b, pa, pb, path_s, id_keys)
    return _diff_leaves(a, b, pa, pb, path_s)


def _rec_dict(
    a: dict,
    b: dict,
    pa: PathTuple,
    pb: PathTuple,
    path_s: str,
    id_keys: tuple[str, ...] | None,
) -> List[DiffRow]:
    rows: List[DiffRow] = []
    for k in sorted(set(a) | set(b), key=lambda x: str(x)):
        ka = f"{path_s}.{k}" if path_s else str(k)
        if k in a and k in b:
            rows += _rec(a[k], b[k], pa + (k,), pb + (k,), ka, id_keys)
        elif k in a:
            rows += _emit_only("a", a[k], pa + (k,))
        else:
            rows += _emit_only("b", b[k], pb + (k,))
    return rows


def _rec_list(
    a: list,
    b: list,
    pa: PathTuple,
    pb: PathTuple,
    path_s: str,
    id_keys: tuple[str, ...] | None,
) -> List[DiffRow]:
    rows: List[DiffRow] = []
    ikey = _pick_id_key(a, b, id_keys) if a and b else None
    if ikey is not None:
        ma: dict = {}
        mb: dict = {}
        for i, e in enumerate(a):
            if isinstance(e, dict) and _nonempty_id(e.get(ikey)):
                raw = e[ikey]
                vid = _norm_id_key(raw)
                if vid not in ma:
                    ma[vid] = (i, e, raw)
        for i, e in enumerate(b):
            if isinstance(e, dict) and _nonempty_id(e.get(ikey)):
                raw = e[ikey]
                vid = _norm_id_key(raw)
                if vid not in mb:
                    mb[vid] = (i, e, raw)
        used_a: Set[int] = set()
        used_b: Set[int] = set()
        all_v = sorted(set(ma) | set(mb), key=_sort_key)
        for vidk in all_v:
            if vidk in ma and vidk in mb:
                ia, ea, raws = ma[vidk]
                ib, eb, _ = mb[vidk]
                dlab = (
                    f"{path_s}[{ikey}={short_label(raws, 32)}]"
                    if path_s
                    else f"[{ikey}={short_label(raws, 32)}]"
                )
                used_a.add(ia)
                used_b.add(ib)
                rows += _rec(ea, eb, pa + (ia,), pb + (ib,), dlab, id_keys)
            elif vidk in ma:
                ia, ea, _ = ma[vidk]
                used_a.add(ia)
                rows += _emit_only("a", ea, pa + (ia,))
            else:
                ib, eb, _ = mb[vidk]
                used_b.add(ib)
                rows += _emit_only("b", eb, pb + (ib,))
        for i, e in enumerate(a):
            if i not in used_a:
                dlab = f"{path_s}[{i}]" if path_s else f"[{i}]"
                if i < len(b) and i not in used_b:
                    used_b.add(i)
                    rows += _rec(e, b[i], pa + (i,), pb + (i,), dlab, id_keys)
                else:
                    rows += _emit_only("a", e, pa + (i,))
        for j, e in enumerate(b):
            if j not in used_b:
                rows += _emit_only("b", e, pb + (j,))
        return rows

    m = min(len(a), len(b))
    for i in range(m):
        dlab = f"{path_s}[{i}]" if path_s else f"[{i}]"
        rows += _rec(a[i], b[i], pa + (i,), pb + (i,), dlab, id_keys)
    for i in range(m, len(a)):
        rows += _emit_only("a", a[i], pa + (i,))
    for j in range(m, len(b)):
        rows += _emit_only("b", b[j], pb + (j,))
    return rows


def _sort_key(x: str) -> str:
    return x.lower()
