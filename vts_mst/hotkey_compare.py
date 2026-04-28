"""Cross-file hotkey summary: old model vs new — toggle, in target, keybind match."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from vts_mst.hotkey_extract import (
    HotkeyRecord,
    extract_hotkeys,
    format_keybind,
    keybind_equal,
)
from vts_mst.json_file_io import load_json
from vts_mst.json_paths import PathTuple


@dataclass
class HotkeySummaryRow:
    json_file: str  # target-side filename (wizard writes here)
    hotkey_id: str
    name: str
    toggle_file: str
    action: str
    keybind_a: str
    keybind_b: str
    in_target: bool
    keys_match: Optional[bool]
    path_keycomb_a: PathTuple
    path_keycomb_b: Optional[PathTuple]
    raw_kc_a: Any
    raw_kc_b: Optional[Any] = None
    source_json_file: str = ""

    def json_pair_label(self) -> str:
        if self.source_json_file and self.source_json_file != self.json_file:
            return f"{self.source_json_file} → {self.json_file}"
        return self.json_file


def _index_b_records(
    records: List[HotkeyRecord],
) -> tuple[Dict[str, HotkeyRecord], Dict[str, HotkeyRecord]]:
    by_id: Dict[str, HotkeyRecord] = {}
    by_nf: Dict[str, HotkeyRecord] = {}
    for r in records:
        ik = r.hotkey_id.strip().lower()
        if ik and ik not in by_id:
            by_id[ik] = r
        if r.name.strip():
            nk = f"{r.name.strip().lower()}|{r.toggle_file.strip().lower()}"
            if nk not in by_nf:
                by_nf[nk] = r
    return by_id, by_nf


def _lookup_b(
    ra: HotkeyRecord,
    by_id: Dict[str, HotkeyRecord],
    by_nf: Dict[str, HotkeyRecord],
):
    ik = ra.hotkey_id.strip().lower()
    if ik in by_id:
        return by_id[ik]
    nk = f"{ra.name.strip().lower()}|{ra.toggle_file.strip().lower()}"
    if ra.name and nk in by_nf:
        return by_nf[nk]
    return None


def build_cross_file_summary(
    live2d: Path,
    src_model: str,
    tgt_model: str,
    file_pairs: List[tuple[str, str]],
) -> List[HotkeySummaryRow]:
    """Aggregate hotkey rows from source (A) across paired JSON files (names may differ per side)."""
    sa = live2d / src_model
    sb = live2d / tgt_model
    rows: List[HotkeySummaryRow] = []
    for fn_a, fn_b in file_pairs:
        try:
            ja = load_json(sa / fn_a)
            jb = load_json(sb / fn_b)
        except (OSError, ValueError):
            continue
        if not isinstance(ja, dict) or not isinstance(jb, dict):
            continue
        src_tag = fn_a if fn_a != fn_b else ""
        rec_a = extract_hotkeys(fn_a, ja)
        rec_b = extract_hotkeys(fn_b, jb)
        by_id, by_nf = _index_b_records(rec_b)
        for ra in rec_a:
            rb = _lookup_b(ra, by_id, by_nf)
            ka = format_keybind(ra.key_combination)
            if rb is None:
                rows.append(
                    HotkeySummaryRow(
                        json_file=fn_b,
                        source_json_file=src_tag,
                        hotkey_id=ra.hotkey_id,
                        name=ra.name,
                        toggle_file=ra.toggle_file,
                        action=ra.action,
                        keybind_a=ka,
                        keybind_b="",
                        in_target=False,
                        keys_match=None,
                        path_keycomb_a=ra.path_to_keycombination,
                        path_keycomb_b=None,
                        raw_kc_a=ra.key_combination,
                        raw_kc_b=None,
                    )
                )
            else:
                kb = format_keybind(rb.key_combination)
                same = keybind_equal(ra.key_combination, rb.key_combination)
                rows.append(
                    HotkeySummaryRow(
                        json_file=fn_b,
                        source_json_file=src_tag,
                        hotkey_id=ra.hotkey_id,
                        name=ra.name,
                        toggle_file=ra.toggle_file,
                        action=ra.action,
                        keybind_a=ka,
                        keybind_b=kb,
                        in_target=True,
                        keys_match=same,
                        path_keycomb_a=ra.path_to_keycombination,
                        path_keycomb_b=rb.path_to_keycombination,
                        raw_kc_a=ra.key_combination,
                        raw_kc_b=rb.key_combination,
                    )
                )
    return rows
