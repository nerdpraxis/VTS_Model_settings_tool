"""Heuristic “similar name” model pairs for the suggestions panel."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import List, Tuple


def short_label(v: object, max_len: int = 48) -> str:
    s = str(v)
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def model_pairs_by_ratio(
    names: List[str],
    min_ratio: float = 0.55,
) -> List[Tuple[str, str, float]]:
    """Return (name_a, name_b, score) for pairs with normalized similarity >= min_ratio."""
    uniq = sorted({n.strip() for n in names if n.strip()}, key=str.lower)
    out: List[Tuple[str, str, float]] = []
    for i, a in enumerate(uniq):
        for b in uniq[i + 1 :]:
            r = SequenceMatcher(a=a, b=b).ratio()
            if r >= min_ratio:
                out.append((a, b, r))
    out.sort(key=lambda t: (-t[2], t[0].lower(), t[1].lower()))
    return out


def model_groups_by_prefix(names: List[str], min_len: int = 3) -> List[List[str]]:
    """
    Group names that share a long common prefix (e.g. Aika_Nova-2, Aika_Nova-2.1).
    Single-pass greedy on sorted list.
    """
    uniq = sorted({n.strip() for n in names if n.strip()}, key=str.lower)
    if not uniq:
        return []
    groups: List[List[str]] = []
    current = [uniq[0]]
    for w in uniq[1:]:
        a, b = current[0], w
        p = 0
        m = min(len(a), len(b), 80)
        while p < m and a[p].lower() == b[p].lower():
            p += 1
        if p >= min_len and p >= min(len(a), len(b)) * 0.4:
            current.append(w)
        else:
            if len(current) > 1:
                groups.append(current)
            current = [w]
    if len(current) > 1:
        groups.append(current)
    return groups
