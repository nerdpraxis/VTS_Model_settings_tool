"""Find VTube-style hotkey dicts in arbitrary JSON and record paths for keyCombination."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Tuple

from vts_mst.json_paths import PathTuple

# Keys that usually appear on on-disk hotkey objects (vtube.json)
# VTS file format uses PascalCase (HotkeyID, Action, File); API-style dumps may use camelCase.
_HK_ACTION_KEYS = (
    "hotkeyAction",
    "HotkeyAction",
    "action",
    "Action",
    "type",
    "Type",
    "hotkeyType",
)


def _has_file_key(d: dict) -> bool:
    return "file" in d or "File" in d


def _has_keycombination_key(d: dict) -> bool:
    return "keyCombination" in d or "KeyCombination" in d


def _looks_like_keyboard_triggers(t: Any) -> bool:
    """On-disk model JSON uses Triggers.{Trigger1,Trigger2,Trigger3,ScreenButton}, not keyCombination."""
    if not isinstance(t, dict):
        return False
    keys = frozenset(t.keys())
    if keys & {"Trigger1", "Trigger2", "Trigger3", "ScreenButton"}:
        return True
    return any(str(k).startswith("Trigger") for k in keys)


def _is_hotkey_like_dict(d: Any) -> bool:
    if not isinstance(d, dict):
        return False
    tr = d.get("Triggers")
    has_marker = (
        any(k in d for k in _HK_ACTION_KEYS)
        or _has_keycombination_key(d)
        or _has_file_key(d)
        or _looks_like_keyboard_triggers(tr)
    )
    has_id = bool(
        str(d.get("hotkeyID") or d.get("HotkeyID") or d.get("id") or "").strip()
    ) or bool(str(d.get("name") or d.get("Name") or "").strip())
    return has_marker and has_id


def _list_looks_like_hotkeys(lst: list) -> bool:
    if not lst:
        return False
    n = sum(1 for x in lst if _is_hotkey_like_dict(x))
    return n >= max(1, int(len(lst) * 0.35))


@dataclass(frozen=True)
class HotkeyRecord:
    json_file: str
    path_to_item: PathTuple  # path to the hotkey dict
    hotkey_id: str
    name: str
    action: str
    toggle_file: str
    key_combination: Any
    _key_field: str  # "keyCombination" | "KeyCombination" | "Triggers"

    @property
    def path_to_keycombination(self) -> PathTuple:
        return self.path_to_item + (self._key_field,)


def _action_str(d: dict) -> str:
    for k in _HK_ACTION_KEYS:
        if k in d and d[k] not in (None, ""):
            return str(d[k])
    return ""


def _toggle_str(d: dict) -> str:
    return str(d.get("file") or d.get("File") or d.get("expression") or d.get("Expression") or "")


def _hotkey_id_for(d: dict) -> str:
    hid = str(d.get("hotkeyID") or d.get("HotkeyID") or d.get("id") or "").strip()
    if hid:
        return hid
    name = str(d.get("name") or d.get("Name") or "").strip()
    if name:
        return f"name:{name}"
    return ""


def _keybind_field_and_value(d: dict) -> tuple[str, Any]:
    """Return JSON path segment + value used for keybind compare/copy (disk Triggers vs API keyCombination)."""
    if "keyCombination" in d:
        return "keyCombination", d.get("keyCombination", [])
    if "KeyCombination" in d:
        return "KeyCombination", d.get("KeyCombination", [])
    if _looks_like_keyboard_triggers(d.get("Triggers")):
        return "Triggers", d.get("Triggers")
    return "keyCombination", d.get("keyCombination", [])


def _record(json_file: str, path_to_item: PathTuple, d: dict) -> HotkeyRecord:
    kfield, kval = _keybind_field_and_value(d)
    return HotkeyRecord(
        json_file=json_file,
        path_to_item=path_to_item,
        hotkey_id=_hotkey_id_for(d),
        name=str(d.get("name") or d.get("Name") or ""),
        action=_action_str(d),
        toggle_file=_toggle_str(d),
        key_combination=kval if kval is not None else ([] if kfield != "Triggers" else {}),
        _key_field=kfield,
    )


def extract_hotkeys(json_file: str, root: Any) -> List[HotkeyRecord]:
    out: List[HotkeyRecord] = []

    def walk(obj: Any, path: PathTuple, parent_dict_key: str | None = None) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, path + (k,), k)
        elif isinstance(obj, list):
            # VTS model files use "Hotkeys" — always treat that array as hotkeys (no 35% heuristic).
            named_hotkeys = (
                parent_dict_key is not None and parent_dict_key.lower() == "hotkeys"
            )
            if named_hotkeys or _list_looks_like_hotkeys(obj):
                for i, item in enumerate(obj):
                    if isinstance(item, dict) and _hotkey_id_for(item):
                        if named_hotkeys or _is_hotkey_like_dict(item):
                            out.append(_record(json_file, path + (i,), item))
                    elif not named_hotkeys:
                        walk(item, path + (i,), None)
            else:
                for i, item in enumerate(obj):
                    walk(item, path + (i,), None)

    walk(root, (), None)
    return out


def format_keybind(kc: Any) -> str:
    if kc is None:
        return ""
    if isinstance(kc, (str, int, float, bool)):
        return str(kc)
    try:
        s = json.dumps(kc, ensure_ascii=False, default=str)
    except TypeError:
        s = str(kc)
    if len(s) > 120:
        return s[:117] + "…"
    return s


def keybind_equal(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )
