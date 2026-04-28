"""Tuple paths into JSON; format for display; get/set in nested dict/list trees."""

from __future__ import annotations

import copy
import json
from typing import Any, Iterator, Tuple, Union

PathTuple = Tuple[Union[str, int], ...]


def format_path(path: PathTuple) -> str:
    if not path:
        return ""
    s = str(path[0]) if not isinstance(path[0], int) else f"[{path[0]}]"
    for p in path[1:]:
        if isinstance(p, int):
            s += f"[{p}]"
        else:
            s += f".{p}"
    return s


def iter_paths(obj: Any, base: PathTuple = ()) -> Iterator[Tuple[PathTuple, Any]]:
    """Depth-first: leaf values only (str, int, float, bool, None)."""
    if isinstance(obj, dict):
        for k in sorted(obj.keys(), key=lambda x: (str(x),)):
            yield from iter_paths(obj[k], base + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_paths(v, base + (i,))
    else:
        yield (base, obj)


def get_at(obj: Any, path: PathTuple) -> Any:
    cur: Any = obj
    for p in path:
        if isinstance(p, int):
            cur = cur[p]
        else:
            cur = cur[p]
    return cur


def set_at(root: dict, path: PathTuple, value: Any) -> None:
    """
    Set value at path. Extends lists with None as needed. Creates missing parents:
    next key int -> new list, next key str -> new dict. If existing node is None,
    it is replaced with a list or dict as appropriate.
    """
    if not path:
        raise ValueError("empty path to set_at")
    cur: Any = root
    for i, p in enumerate(path[:-1]):
        nxt_key = path[i + 1]
        need_list = isinstance(nxt_key, int)
        nxt: Any
        if isinstance(p, int):
            if not isinstance(cur, list):
                raise TypeError("path mismatch: list index on non-list")
            while len(cur) <= p:
                cur.append(None)
            bad = cur[p] is None
            if not bad:
                bad = (
                    not isinstance(cur[p], list)
                    if need_list
                    else not isinstance(cur[p], dict)
                )
            if bad:
                cur[p] = [] if need_list else {}
            nxt = cur[p]
        else:
            if not isinstance(cur, dict):
                raise TypeError("path mismatch: str key on non-dict")
            bad = p not in cur or cur[p] is None
            if not bad:
                bad = (
                    not isinstance(cur[p], list)
                    if need_list
                    else not isinstance(cur[p], dict)
                )
            if bad:
                cur[p] = [] if need_list else {}
            nxt = cur[p]
        cur = nxt

    last = path[-1]
    if isinstance(last, int):
        if not isinstance(cur, list):
            raise TypeError("path mismatch")
        while len(cur) <= last:
            cur.append(None)
        cur[last] = value
    else:
        if not isinstance(cur, dict):
            raise TypeError("path mismatch")
        cur[last] = value


def json_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )


def deep_clone(obj: Any) -> Any:
    return copy.deepcopy(obj)
