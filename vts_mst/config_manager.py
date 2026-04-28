"""Load/save this app's config.ini (independent of AIKA config_utils)."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any


class AppConfig:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._cp = configparser.ConfigParser(
            interpolation=None,
            delimiters=("=",),
        )
        self._cp.optionxform = str  # case-sensitive keys
        if path.exists():
            self._cp.read(path, encoding="utf-8")
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        if "Paths" not in self._cp:
            self._cp.add_section("Paths")
        if "Backup" not in self._cp:
            self._cp.add_section("Backup")
        if "UI" not in self._cp:
            self._cp.add_section("UI")
        if "Diff" not in self._cp:
            self._cp.add_section("Diff")
        p = "Paths"
        b = "Backup"
        u = "UI"
        d = "Diff"
        if not self._cp.has_option(p, "live2d_models_path"):
            self._cp.set(p, "live2d_models_path", "")
        if not self._cp.has_option(b, "root"):
            self._cp.set(b, "root", "backups")
        if not self._cp.has_option(u, "window_width"):
            self._cp.set(u, "window_width", "1100")
        if not self._cp.has_option(u, "window_height"):
            self._cp.set(u, "window_height", "720")
        if not self._cp.has_option(d, "min_name_similarity"):
            self._cp.set(d, "min_name_similarity", "0.55")
        if not self._cp.has_option(d, "use_aligned_list_diff"):
            self._cp.set(d, "use_aligned_list_diff", "true")
        if not self._cp.has_option(d, "id_keys"):
            self._cp.set(
                d,
                "id_keys",
                "hotkeyID,id,name,Name,file,fileName",
            )
        if not self._cp.has_option(u, "last_source_model"):
            self._cp.set(u, "last_source_model", "")
        if not self._cp.has_option(u, "last_target_model"):
            self._cp.set(u, "last_target_model", "")
        if not self._cp.has_option(u, "last_json_file"):
            self._cp.set(u, "last_json_file", "")
        if not self._cp.has_option(u, "hide_identical_rows"):
            self._cp.set(u, "hide_identical_rows", "true")

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(
                "# VTS Model Settings Tool — see README.md\n"
                "# Values changed in the UI are written here.\n\n"
            )
            self._cp.write(f)

    def get(self, section: str, key: str, fallback: str = "") -> str:
        if self._cp.has_option(section, key):
            return self._cp.get(section, key).strip()
        return fallback

    def set_value(self, section: str, key: str, value: Any) -> None:
        if not self._cp.has_section(section):
            self._cp.add_section(section)
        self._cp.set(section, key, str(value))

    @property
    def live2d_models_path(self) -> str:
        return self.get("Paths", "live2d_models_path", "")

    @live2d_models_path.setter
    def live2d_models_path(self, v: str) -> None:
        self.set_value("Paths", "live2d_models_path", v)

    @property
    def backup_root(self) -> str:
        return self.get("Backup", "root", "backups")

    @backup_root.setter
    def backup_root(self, v: str) -> None:
        self.set_value("Backup", "root", v)

    @property
    def window_size(self) -> tuple[int, int]:
        w = int(self.get("UI", "window_width", "1100") or 1100)
        h = int(self.get("UI", "window_height", "720") or 720)
        return w, h

    def set_window_size(self, w: int, h: int) -> None:
        self.set_value("UI", "window_width", w)
        self.set_value("UI", "window_height", h)

    @property
    def last_source_model(self) -> str:
        return self.get("UI", "last_source_model", "")

    @last_source_model.setter
    def last_source_model(self, v: str) -> None:
        self.set_value("UI", "last_source_model", v)

    @property
    def last_target_model(self) -> str:
        return self.get("UI", "last_target_model", "")

    @last_target_model.setter
    def last_target_model(self, v: str) -> None:
        self.set_value("UI", "last_target_model", v)

    @property
    def last_json_file(self) -> str:
        return self.get("UI", "last_json_file", "")

    @last_json_file.setter
    def last_json_file(self, v: str) -> None:
        self.set_value("UI", "last_json_file", v)

    @property
    def hide_identical_rows(self) -> bool:
        s = self.get("UI", "hide_identical_rows", "true").lower()
        return s in ("1", "true", "yes", "on")

    @hide_identical_rows.setter
    def hide_identical_rows(self, v: bool) -> None:
        self.set_value("UI", "hide_identical_rows", "true" if v else "false")

    @property
    def use_aligned_list_diff(self) -> bool:
        s = self.get("Diff", "use_aligned_list_diff", "true").lower()
        return s in ("1", "true", "yes", "on")

    @use_aligned_list_diff.setter
    def use_aligned_list_diff(self, v: bool) -> None:
        self.set_value("Diff", "use_aligned_list_diff", "true" if v else "false")

    def id_keys_tuple(self) -> tuple[str, ...] | None:
        raw = self.get("Diff", "id_keys", "")
        if not raw.strip():
            return None
        return tuple(
            k.strip() for k in raw.split(",") if k.strip()
        )

    @property
    def id_keys_raw(self) -> str:
        return self.get("Diff", "id_keys", "")

    @id_keys_raw.setter
    def id_keys_raw(self, v: str) -> None:
        self.set_value("Diff", "id_keys", v)

    @property
    def min_name_similarity(self) -> float:
        try:
            return float(self.get("Diff", "min_name_similarity", "0.55"))
        except ValueError:
            return 0.55
