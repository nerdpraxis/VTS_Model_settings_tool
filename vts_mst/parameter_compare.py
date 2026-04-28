"""Cross-file parameter summary: match by OutputLive2D / Input, compare mapping fields."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from vts_mst.hotkey_extract import format_keybind as fmt_val  # concise JSON-ish preview
from vts_mst.hotkey_extract import keybind_equal as val_equal
from vts_mst.json_file_io import load_json
from vts_mst.json_paths import PathTuple, get_at
from vts_mst.parameter_extract import (
    PARAM_SYNC_KEYS,
    ParameterRecord,
    extract_parameters,
)


@dataclass
class ParameterSummaryRow:
    json_file: str  # target file for writes
    source_json_file: str
    name: str
    output_live2d: str
    input_a: str
    input_b: str
    in_target: bool
    fields_match: Optional[bool]
    smoothing_a: str
    smoothing_b: str
    clamp_in_a: str
    clamp_in_b: str
    clamp_out_a: str
    clamp_out_b: str
    in_range_a: str
    in_range_b: str
    out_range_a: str
    out_range_b: str
    path_item_a: PathTuple
    path_item_b: Optional[PathTuple]
    raw_fields_a: Dict[str, Any]
    raw_fields_b: Dict[str, Any]

    def json_pair_label(self) -> str:
        if self.source_json_file and self.source_json_file != self.json_file:
            return f"{self.source_json_file} → {self.json_file}"
        return self.json_file


def _get_fields(d_path: PathTuple, blob: dict) -> Dict[str, Any]:
    d = get_at(blob, d_path)
    if not isinstance(d, dict):
        return {}
    return {k: d.get(k) for k in PARAM_SYNC_KEYS}


def _fmt_range(lo: Any, hi: Any) -> str:
    return f"[{fmt_val(lo)}, {fmt_val(hi)}]"


def _index_b(
    records: List[ParameterRecord],
) -> tuple[Dict[str, ParameterRecord], Dict[str, ParameterRecord]]:
    by_out: Dict[str, ParameterRecord] = {}
    by_inp: Dict[str, ParameterRecord] = {}
    for r in records:
        o = r.output_live2d.strip().lower()
        if o and o not in by_out:
            by_out[o] = r
        i = r.input_name.strip().lower()
        if i and i not in by_inp:
            by_inp[i] = r
    return by_out, by_inp


def _lookup_b(
    ra: ParameterRecord,
    by_out: Dict[str, ParameterRecord],
    by_inp: Dict[str, ParameterRecord],
) -> Optional[ParameterRecord]:
    o = ra.output_live2d.strip().lower()
    if o and o in by_out:
        return by_out[o]
    i = ra.input_name.strip().lower()
    if i and i in by_inp:
        return by_inp[i]
    return None


def _all_matched_fields_equal(fa: Dict[str, Any], fb: Dict[str, Any]) -> bool:
    for k in PARAM_SYNC_KEYS:
        if not val_equal(fa.get(k), fb.get(k)):
            return False
    return True


def build_parameter_cross_file_summary(
    live2d: Path,
    src_model: str,
    tgt_model: str,
    file_pairs: List[tuple[str, str]],
) -> List[ParameterSummaryRow]:
    sa = live2d / src_model
    sb = live2d / tgt_model
    rows: List[ParameterSummaryRow] = []
    for fn_a, fn_b in file_pairs:
        try:
            ja = load_json(sa / fn_a)
            jb = load_json(sb / fn_b)
        except (OSError, ValueError):
            continue
        if not isinstance(ja, dict) or not isinstance(jb, dict):
            continue
        src_tag = fn_a if fn_a != fn_b else ""
        rec_a = extract_parameters(fn_a, ja)
        rec_b = extract_parameters(fn_b, jb)
        by_out, by_inp = _index_b(rec_b)
        for ra in rec_a:
            fa = _get_fields(ra.path_to_item, ja)
            rb = _lookup_b(ra, by_out, by_inp)
            if rb is None:
                rows.append(
                    ParameterSummaryRow(
                        json_file=fn_b,
                        source_json_file=src_tag,
                        name=ra.name,
                        output_live2d=ra.output_live2d,
                        input_a=ra.input_name,
                        input_b="",
                        in_target=False,
                        fields_match=None,
                        smoothing_a=fmt_val(fa.get("Smoothing")),
                        smoothing_b="",
                        clamp_in_a=fmt_val(fa.get("ClampInput")),
                        clamp_in_b="",
                        clamp_out_a=fmt_val(fa.get("ClampOutput")),
                        clamp_out_b="",
                        in_range_a=_fmt_range(
                            fa.get("InputRangeLower"), fa.get("InputRangeUpper")
                        ),
                        in_range_b="",
                        out_range_a=_fmt_range(
                            fa.get("OutputRangeLower"), fa.get("OutputRangeUpper")
                        ),
                        out_range_b="",
                        path_item_a=ra.path_to_item,
                        path_item_b=None,
                        raw_fields_a=dict(fa),
                        raw_fields_b={k: None for k in PARAM_SYNC_KEYS},
                    )
                )
                continue
            fb = _get_fields(rb.path_to_item, jb)
            same = _all_matched_fields_equal(fa, fb)
            rows.append(
                ParameterSummaryRow(
                    json_file=fn_b,
                    source_json_file=src_tag,
                    name=ra.name,
                    output_live2d=ra.output_live2d,
                    input_a=ra.input_name,
                    input_b=rb.input_name,
                    in_target=True,
                    fields_match=same,
                    smoothing_a=fmt_val(fa.get("Smoothing")),
                    smoothing_b=fmt_val(fb.get("Smoothing")),
                    clamp_in_a=fmt_val(fa.get("ClampInput")),
                    clamp_in_b=fmt_val(fb.get("ClampInput")),
                    clamp_out_a=fmt_val(fa.get("ClampOutput")),
                    clamp_out_b=fmt_val(fb.get("ClampOutput")),
                    in_range_a=_fmt_range(
                        fa.get("InputRangeLower"), fa.get("InputRangeUpper")
                    ),
                    in_range_b=_fmt_range(
                        fb.get("InputRangeLower"), fb.get("InputRangeUpper")
                    ),
                    out_range_a=_fmt_range(
                        fa.get("OutputRangeLower"), fa.get("OutputRangeUpper")
                    ),
                    out_range_b=_fmt_range(
                        fb.get("OutputRangeLower"), fb.get("OutputRangeUpper")
                    ),
                    path_item_a=ra.path_to_item,
                    path_item_b=rb.path_to_item,
                    raw_fields_a=dict(fa),
                    raw_fields_b=dict(fb),
                )
            )
    return rows
