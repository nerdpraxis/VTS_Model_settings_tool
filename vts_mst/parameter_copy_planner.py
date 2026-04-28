"""Plan and apply ParameterSettings field copies (source → target)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from vts_mst.copy_planner import PlannedKeybindWrite, execute_planned_leaf_writes
from vts_mst.hotkey_extract import keybind_equal as val_equal
from vts_mst.json_paths import deep_clone
from vts_mst.parameter_compare import ParameterSummaryRow
from vts_mst.parameter_extract import (
    PARAM_FIELD_CLAMP_IN,
    PARAM_FIELD_CLAMP_OUT,
    PARAM_FIELD_IN_HI,
    PARAM_FIELD_IN_LO,
    PARAM_FIELD_INPUT,
    PARAM_FIELD_OUT_HI,
    PARAM_FIELD_OUT_LO,
    PARAM_FIELD_SMOOTHING,
)


@dataclass
class ParameterCopyScope:
    copy_input: bool = True
    copy_smoothing: bool = True
    copy_clamp_input: bool = True
    copy_clamp_output: bool = True
    copy_input_range: bool = True
    copy_output_range: bool = True


def plan_parameter_writes(
    rows: List[ParameterSummaryRow],
    scope: ParameterCopyScope,
    only_where_differs: bool,
) -> List[PlannedKeybindWrite]:
    """Copy selected fields from A onto B for matched parameters (same OutputLive2D / Input)."""
    out: List[PlannedKeybindWrite] = []
    field_jobs: List[Tuple[bool, str, str]] = [
        (scope.copy_input, PARAM_FIELD_INPUT, "Input"),
        (scope.copy_smoothing, PARAM_FIELD_SMOOTHING, "Smoothing"),
        (scope.copy_clamp_input, PARAM_FIELD_CLAMP_IN, "ClampInput"),
        (scope.copy_clamp_output, PARAM_FIELD_CLAMP_OUT, "ClampOutput"),
        (scope.copy_input_range, PARAM_FIELD_IN_LO, "InputRangeLower"),
        (scope.copy_input_range, PARAM_FIELD_IN_HI, "InputRangeUpper"),
        (scope.copy_output_range, PARAM_FIELD_OUT_LO, "OutputRangeLower"),
        (scope.copy_output_range, PARAM_FIELD_OUT_HI, "OutputRangeUpper"),
    ]

    for r in rows:
        if not r.in_target or r.path_item_b is None:
            continue
        if only_where_differs and r.fields_match is True:
            continue
        pair = r.json_pair_label()
        base_lab = f"{pair} — {r.output_live2d or r.name or r.input_a}"

        for enabled, json_key, _short in field_jobs:
            if not enabled:
                continue
            va = r.raw_fields_a.get(json_key)
            vb = r.raw_fields_b.get(json_key)
            if only_where_differs and val_equal(va, vb):
                continue
            pa = r.path_item_a + (json_key,)
            pb = r.path_item_b + (json_key,)
            label = f"{base_lab} — {json_key}"
            out.append(
                PlannedKeybindWrite(
                    json_file=r.json_file,
                    label=label,
                    path_in_source=pa,
                    path_in_target=pb,
                    value=deep_clone(va),
                )
            )
    return out


def execute_planned_parameter_writes(
    live2d: Path,
    tgt_model: str,
    plan: List[PlannedKeybindWrite],
    backup_session: Path,
) -> tuple[int, str | None]:
    return execute_planned_leaf_writes(live2d, tgt_model, plan, backup_session)
