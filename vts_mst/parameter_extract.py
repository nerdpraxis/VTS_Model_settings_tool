"""Extract VTS ParameterSettings entries from model JSON (vtube.json)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from vts_mst.json_paths import PathTuple


def _is_parameter_dict(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    return "OutputLive2D" in d and "Input" in d


def _list_looks_like_parameter_settings(lst: list) -> bool:
    if not lst:
        return False
    n = sum(1 for x in lst if _is_parameter_dict(x))
    return n >= max(1, int(len(lst) * 0.35))


@dataclass(frozen=True)
class ParameterRecord:
    json_file: str
    path_to_item: PathTuple
    name: str
    input_name: str
    output_live2d: str


def _record(json_file: str, path_to_item: PathTuple, d: dict) -> ParameterRecord:
    return ParameterRecord(
        json_file=json_file,
        path_to_item=path_to_item,
        name=str(d.get("Name") or d.get("name") or ""),
        input_name=str(d.get("Input") or d.get("input") or ""),
        output_live2d=str(d.get("OutputLive2D") or d.get("outputLive2D") or ""),
    )


def extract_parameters(json_file: str, root: Any) -> List[ParameterRecord]:
    out: List[ParameterRecord] = []

    def walk(obj: Any, path: PathTuple, parent_dict_key: str | None = None) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, path + (k,), k)
        elif isinstance(obj, list):
            named = (
                parent_dict_key is not None
                and parent_dict_key.lower() == "parametersettings"
            )
            if named or _list_looks_like_parameter_settings(obj):
                for i, item in enumerate(obj):
                    if isinstance(item, dict) and _is_parameter_dict(item):
                        out.append(_record(json_file, path + (i,), item))
                    elif not named:
                        walk(item, path + (i,), None)
            else:
                for i, item in enumerate(obj):
                    walk(item, path + (i,), None)

    walk(root, (), None)
    return out


# JSON keys copied for tracking / UI (PascalCase as on disk)
PARAM_FIELD_INPUT = "Input"
PARAM_FIELD_SMOOTHING = "Smoothing"
PARAM_FIELD_CLAMP_IN = "ClampInput"
PARAM_FIELD_CLAMP_OUT = "ClampOutput"
PARAM_FIELD_IN_LO = "InputRangeLower"
PARAM_FIELD_IN_HI = "InputRangeUpper"
PARAM_FIELD_OUT_LO = "OutputRangeLower"
PARAM_FIELD_OUT_HI = "OutputRangeUpper"

PARAM_SYNC_KEYS = (
    PARAM_FIELD_INPUT,
    PARAM_FIELD_SMOOTHING,
    PARAM_FIELD_CLAMP_IN,
    PARAM_FIELD_CLAMP_OUT,
    PARAM_FIELD_IN_LO,
    PARAM_FIELD_IN_HI,
    PARAM_FIELD_OUT_LO,
    PARAM_FIELD_OUT_HI,
)
