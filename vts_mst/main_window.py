"""Main window: scan models, diff two JSON files, copy/edit with backup + restore."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QCloseEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vts_mst.backup_ops import (
    backup_file,
    create_session,
    list_files_in_model_backup,
    list_sessions,
    resolve_backup_dir,
    restore_file,
    write_json_to_live,
)
from vts_mst.config_manager import AppConfig
from vts_mst.copy_wizard import WizardContext, run_copy_wizard
from vts_mst.diff_core import DiffRow, RowKind, diff_json_trees
from vts_mst.hotkey_compare import HotkeySummaryRow, build_cross_file_summary
from vts_mst.parameter_compare import ParameterSummaryRow, build_parameter_cross_file_summary
from vts_mst.parameter_copy_wizard import ParameterWizardContext, run_parameter_copy_wizard
from vts_mst.edit_dialog import run_edit_value
from vts_mst.json_file_io import load_json
from vts_mst.json_paths import get_at
from vts_mst.merge_apply import copy_source_leaf_to_target, set_target_leaf
from vts_mst.model_scan import ModelInfo, common_json_names, paired_json_for_hotkey_summary, scan_models
from vts_mst.model_similarity import model_groups_by_prefix, model_pairs_by_ratio
from vts_mst.paths import app_root, config_path

DARK_STYLESHEET = """
QWidget { background-color: #1e1e1e; color: #ffffff; }
QTabWidget::pane {
    border: 1px solid #444;
    border-top: none;
    background: #252525;
    top: -1px;
}
QTabBar::tab {
    background: #2a2a2a;
    color: #e8e8e8;
    border: 1px solid #444;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 18px;
    margin-right: 2px;
    min-width: 6em;
}
QTabBar::tab:selected {
    background: #252525;
    color: #ffffff;
    font-weight: bold;
    border-bottom: 1px solid #252525;
    margin-bottom: -1px;
}
QTabBar::tab:hover {
    background: #353535;
    color: #ffffff;
}
QTabBar::tab:!selected {
    color: #c0c0c0;
}
QGroupBox {
    color: #ffffff; font-size: 13px; border: 1px solid #444; border-radius: 6px;
    margin-top: 14px; padding: 12px; padding-top: 22px; font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QComboBox {
    background-color: #2d2d2d; color: #ffffff; border: 1px solid #555; border-radius: 4px;
    padding: 6px; min-height: 22px;
}
QComboBox::drop-down { border: none; }
QTableWidget { gridline-color: #444; background: #252525; alternate-background-color: #2a2a2a; }
QTableWidget::item:selected { background: #2953F0; color: #fff; }
QHeaderView::section { background: #333; color: #fff; padding: 4px; border: 1px solid #444; }
QPushButton {
    background-color: #2953F0; color: #ffffff; border: none; border-radius: 4px;
    padding: 8px 16px; font-weight: bold; min-width: 90px; min-height: 26px;
}
QPushButton:hover { background-color: #3a64ff; }
QPushButton#muted { background-color: #333; }
QPushButton#danger { background-color: #8b2942; }
QPushButton#danger:hover { background-color: #a83a55; }
QLabel#hint { color: #b0b0b0; font-size: 12px; }
QLabel#title { font-size: 16px; font-weight: bold; }
"""

COLOR_SAME = QColor("#1a3d1a")
COLOR_DIFF = QColor("#4d3d1a")
COLOR_MISS = QColor("#3d1a1a")
COLOR_TYPE = QColor("#4a1a2e")


def _row_kind_text(k: RowKind) -> str:
    return {
        RowKind.SAME: "match",
        RowKind.DIFFER: "different",
        RowKind.ONLY_A: "only source (A)",
        RowKind.ONLY_B: "only target (B)",
        RowKind.TYPE_MISMATCH: "type mismatch",
    }[k]


def _row_can_copy_from_a(k: RowKind) -> bool:
    return k in (RowKind.DIFFER, RowKind.ONLY_A, RowKind.TYPE_MISMATCH)


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._cfg = AppConfig(config_path())
        if not config_path().exists():
            self._cfg.save()
        w, h = self._cfg.window_size
        self.resize(w, h)
        self.setMinimumSize(880, 520)
        self.setWindowTitle("VTS Model Settings Tool")
        self.setStyleSheet(DARK_STYLESHEET)

        self._models: List[ModelInfo] = []
        self._src_data: Optional[dict] = None
        self._tgt_data: Optional[dict] = None
        self._current_filename: str = ""
        self._diff_rows: List[DiffRow] = []
        self._diff_display: List[DiffRow] = []
        self._src_name: str = ""
        self._tgt_name: str = ""
        self._summary_rows: List[HotkeySummaryRow] = []
        self._summary_display: List[HotkeySummaryRow] = []
        self._param_rows: List[ParameterSummaryRow] = []
        self._param_display: List[ParameterSummaryRow] = []

        self._init_ui()
        self._load_fields()
        self._on_scan(quiet=True)

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        t = QLabel("Compare and migrate on-disk VTube Studio model JSON (see PLAN.md).")
        t.setObjectName("title")
        t.setStyleSheet("background: transparent;")
        root.addWidget(t)

        path_group = QGroupBox("Live2D models folder")
        pg = QVBoxLayout(path_group)
        row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to …/StreamingAssets/Live2DModels")
        self._path_edit.textChanged.connect(self._on_path_changed)
        row.addWidget(self._path_edit, 1)
        browse = QPushButton("Browse…")
        browse.setObjectName("muted")
        browse.clicked.connect(self._browse_models_path)
        row.addWidget(browse)
        scan = QPushButton("Scan models")
        scan.clicked.connect(lambda: self._on_scan(quiet=False))
        row.addWidget(scan)
        pg.addLayout(row)
        hint = QLabel("Close VTube Studio before writing files. Backups are stored under the Backup root.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        hint.setStyleSheet("background: transparent;")
        pg.addWidget(hint)
        root.addWidget(path_group)

        sug = QGroupBox("Similar model names (double-click → set A & B)")
        sl = QVBoxLayout(sug)
        self._suggest_list = QListWidget()
        self._suggest_list.setMaximumHeight(120)
        self._suggest_list.setStyleSheet(
            "QListWidget { background: #252525; border: 1px solid #444; border-radius: 4px; }"
        )
        self._suggest_list.itemDoubleClicked.connect(self._on_suggest_activated)
        sl.addWidget(self._suggest_list)
        root.addWidget(sug)

        pick = QGroupBox("Source & target models")
        pl = QVBoxLayout(pick)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Source (A — old / reference)"))
        self._src_combo = QComboBox()
        self._src_combo.setMinimumWidth(200)
        self._src_combo.currentTextChanged.connect(self._on_model_pick_change)
        r1.addWidget(self._src_combo, 1)
        r1.addWidget(QLabel("Target (B — new)"))
        self._tgt_combo = QComboBox()
        self._tgt_combo.setMinimumWidth(200)
        self._tgt_combo.currentTextChanged.connect(self._on_model_pick_change)
        r1.addWidget(self._tgt_combo, 1)
        pl.addLayout(r1)
        root.addWidget(pick)

        self._status = QLabel(
            "Pick source & target, then use Hotkey summary / Parameter summary → Refresh, "
            "and run the copy wizards before writing. Raw JSON diff is for power users."
        )
        self._status.setObjectName("hint")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("background: transparent;")
        root.addWidget(self._status)

        self._tabs = QTabWidget()
        # --- Tab: Hotkey summary (all common JSON files)
        hk = QWidget()
        hkl = QVBoxLayout(hk)
        ht = QHBoxLayout()
        self._btn_sum_refresh = QPushButton("Refresh hotkey summary")
        self._btn_sum_refresh.clicked.connect(self._refresh_hotkey_summary)
        ht.addWidget(self._btn_sum_refresh)
        self._btn_wizard = QPushButton("Start copy wizard…")
        self._btn_wizard.setToolTip(
            "Multi-step flow: choose scope, preview writes, then confirm backup + save."
        )
        self._btn_wizard.clicked.connect(self._open_copy_wizard)
        ht.addWidget(self._btn_wizard)
        self._btn_sum_export = QPushButton("Export summary (TSV)")
        self._btn_sum_export.setObjectName("muted")
        self._btn_sum_export.clicked.connect(self._export_summary_tsv)
        ht.addWidget(self._btn_sum_export)
        ht.addStretch()
        hkl.addLayout(ht)
        self._sum_hide_match = QCheckBox("Hide rows where keybind already matches")
        self._sum_hide_match.toggled.connect(self._on_sum_filter_toggle)
        hkl.addWidget(self._sum_hide_match)
        self._summary_table = QTableWidget(0, 9)
        self._summary_table.setHorizontalHeaderLabels(
            [
                "JSON (source → target)",
                "Hotkey ID",
                "Name",
                "Toggle / file",
                "Action",
                "Keybind (A)",
                "In B?",
                "Keybind (B)",
                "Match?",
            ]
        )
        sum_hdr = self._summary_table.horizontalHeader()
        sum_hdr.setStretchLastSection(False)
        for col in range(9):
            sum_hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        for col, w in enumerate((260, 130, 120, 160, 110, 200, 56, 200, 52)):
            self._summary_table.setColumnWidth(col, w)
        self._summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._summary_table.setAlternatingRowColors(True)
        hkl.addWidget(self._summary_table, 1)
        self._tabs.addTab(hk, "Hotkey summary")

        # --- Tab: Parameter summary (ParameterSettings)
        pm = QWidget()
        pml = QVBoxLayout(pm)
        pbtn = QHBoxLayout()
        self._btn_param_refresh = QPushButton("Refresh parameter summary")
        self._btn_param_refresh.clicked.connect(self._refresh_parameter_summary)
        pbtn.addWidget(self._btn_param_refresh)
        self._btn_param_wizard = QPushButton("Start parameter copy wizard…")
        self._btn_param_wizard.setToolTip(
            "Choose which fields to copy (Input, clamps, smoothing, ranges), preview, then backup + apply."
        )
        self._btn_param_wizard.clicked.connect(self._open_parameter_copy_wizard)
        pbtn.addWidget(self._btn_param_wizard)
        self._btn_param_export = QPushButton("Export parameter summary (TSV)")
        self._btn_param_export.setObjectName("muted")
        self._btn_param_export.clicked.connect(self._export_parameter_tsv)
        pbtn.addWidget(self._btn_param_export)
        pbtn.addStretch()
        pml.addLayout(pbtn)
        self._param_hide_match = QCheckBox(
            "Hide rows where every compared field already matches"
        )
        self._param_hide_match.toggled.connect(self._on_param_filter_toggle)
        pml.addWidget(self._param_hide_match)
        self._param_table = QTableWidget(0, 17)
        self._param_table.setHorizontalHeaderLabels(
            [
                "JSON (source → target)",
                "Name",
                "OutputLive2D",
                "Input (A)",
                "Input (B)",
                "Smoothing A",
                "Smoothing B",
                "ClampIn A",
                "ClampIn B",
                "ClampOut A",
                "ClampOut B",
                "IN range A",
                "IN range B",
                "OUT range A",
                "OUT range B",
                "In B?",
                "Match?",
            ]
        )
        ph = self._param_table.horizontalHeader()
        ph.setStretchLastSection(False)
        for col in range(17):
            ph.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        for col, w in enumerate(
            (220, 120, 120, 88, 88, 56, 56, 52, 52, 52, 52, 100, 100, 100, 100, 44, 44)
        ):
            self._param_table.setColumnWidth(col, w)
        self._param_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._param_table.setAlternatingRowColors(True)
        pml.addWidget(self._param_table, 1)
        self._tabs.addTab(pm, "Parameter summary")

        # --- Tab: Raw JSON diff (single file)
        rw = QWidget()
        rwl = QVBoxLayout(rw)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("JSON file (both models)"))
        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(280)
        self._file_combo.currentTextChanged.connect(self._on_file_change)
        r2.addWidget(self._file_combo, 1)
        compare = QPushButton("Load & compare")
        compare.clicked.connect(self._compare)
        r2.addWidget(compare)
        rwl.addLayout(r2)
        self._hide_ident = QCheckBox("Hide identical rows")
        self._hide_ident.toggled.connect(self._on_filter_toggle)
        rwl.addWidget(self._hide_ident)
        r3 = QHBoxLayout()
        self._aligned_cb = QCheckBox("Align list[dict] by id (hotkeyID, name, …)")
        self._aligned_cb.setToolTip(
            "Matches array elements by id-like fields so reordered hotkeys still line up. "
            "Disable for strict index-only diff."
        )
        self._aligned_cb.toggled.connect(self._on_aligned_toggle)
        r3.addWidget(self._aligned_cb)
        r3.addWidget(QLabel("ID keys (comma):"))
        self._id_keys_edit = QLineEdit()
        self._id_keys_edit.setPlaceholderText("hotkeyID,id,name,…")
        self._id_keys_edit.setMinimumWidth(200)
        self._id_keys_edit.textChanged.connect(self._on_id_keys_change)
        self._id_keys_edit.editingFinished.connect(self._on_id_keys_finished)
        r3.addWidget(self._id_keys_edit, 1)
        r3.addWidget(QLabel("Min pair %:"))
        self._sim_edit = QLineEdit()
        self._sim_edit.setFixedWidth(50)
        self._sim_edit.textChanged.connect(self._on_sim_change)
        r3.addWidget(self._sim_edit)
        rwl.addLayout(r3)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            ["Path (leaf)", "Value (source A)", "Value (target B)", "Status"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(0, 280)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        rwl.addWidget(self._table, 1)

        act = QGroupBox("Direct actions (current file only — skips wizard)")
        al = QHBoxLayout(act)
        self._btn_copy = QPushButton("Copy A→B for selected rows")
        self._btn_copy.clicked.connect(self._apply_copy_selected)
        al.addWidget(self._btn_copy)
        self._btn_edit = QPushButton("Edit value, apply to B…")
        self._btn_edit.clicked.connect(self._apply_edited)
        al.addWidget(self._btn_edit)
        self._btn_new_sess = QPushButton("New backup session")
        self._btn_new_sess.setObjectName("muted")
        self._btn_new_sess.setToolTip(
            "Next direct write creates a new timestamped folder."
        )
        self._btn_new_sess.clicked.connect(self._new_write_session)
        al.addWidget(self._btn_new_sess)
        self._btn_export = QPushButton("Export raw table (TSV)")
        self._btn_export.setObjectName("muted")
        self._btn_export.setToolTip("Raw diff tab: path, source, target, status.")
        self._btn_export.clicked.connect(self._export_table_tsv)
        al.addWidget(self._btn_export)
        al.addStretch()
        rwl.addWidget(act)

        self._tabs.addTab(rw, "Raw JSON diff")
        root.addWidget(self._tabs, 1)

        rest = QGroupBox("Restore from backup (overwrites live file!)")
        rl = QHBoxLayout(rest)
        self._sess_combo = QComboBox()
        self._sess_combo.setMinimumWidth(220)
        self._sess_refresh = QPushButton("Refresh list")
        self._sess_refresh.setObjectName("muted")
        self._sess_refresh.clicked.connect(self._fill_restore_combos)
        rl.addWidget(QLabel("Session"))
        rl.addWidget(self._sess_combo, 1)
        rl.addWidget(self._sess_refresh)
        self._back_model = QComboBox()
        self._back_file = QComboBox()
        rl.addWidget(QLabel("Model"))
        rl.addWidget(self._back_model)
        rl.addWidget(QLabel("File"))
        rl.addWidget(self._back_file)
        self._btn_restore = QPushButton("Restore to Live2D folder")
        self._btn_restore.setObjectName("danger")
        self._btn_restore.clicked.connect(self._restore_one)
        rl.addWidget(self._btn_restore)
        root.addWidget(rest)

        self._sess_combo.currentTextChanged.connect(
            self._on_session_change_restore
        )
        self._back_model.currentTextChanged.connect(
            self._on_restore_model_fill_files
        )

    def _load_fields(self) -> None:
        self._path_edit.blockSignals(True)
        self._path_edit.setText(self._cfg.live2d_models_path)
        self._path_edit.blockSignals(False)
        self._hide_ident.setChecked(self._cfg.hide_identical_rows)
        self._aligned_cb.blockSignals(True)
        self._aligned_cb.setChecked(self._cfg.use_aligned_list_diff)
        self._aligned_cb.blockSignals(False)
        self._id_keys_edit.blockSignals(True)
        self._id_keys_edit.setText(self._cfg.id_keys_raw)
        self._id_keys_edit.blockSignals(False)
        self._sim_edit.blockSignals(True)
        self._sim_edit.setText(str(self._cfg.min_name_similarity))
        self._sim_edit.blockSignals(False)

    def _diff_opts(self) -> Any:
        return {
            "use_aligned": self._cfg.use_aligned_list_diff,
            "id_keys": self._cfg.id_keys_tuple(),
        }

    def _on_aligned_toggle(self, checked: bool) -> None:
        self._cfg.use_aligned_list_diff = checked
        self._cfg.save()
        if self._src_data is not None and self._tgt_data is not None:
            self._recompute_diff_data()

    def _on_id_keys_change(self, text: str) -> None:
        self._cfg.id_keys_raw = text.strip()
        self._cfg.save()

    def _on_id_keys_finished(self) -> None:
        if self._src_data is not None and self._tgt_data is not None:
            self._recompute_diff_data()

    def _on_sim_change(self, text: str) -> None:
        try:
            v = float(text.strip().replace(",", "."))
            if 0.0 <= v <= 1.0:
                self._cfg.set_value("Diff", "min_name_similarity", f"{v:.2f}")
                self._cfg.save()
                self._rebuild_suggestions()
        except ValueError:
            pass

    def _on_suggest_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, str) or "|" not in data:
            return
        a, b = data.split("|", 1)
        if a not in (x.name for x in self._models) or b not in (x.name for x in self._models):
            return
        self._src_combo.setCurrentText(a)
        self._tgt_combo.setCurrentText(b)

    def _rebuild_suggestions(self) -> None:
        self._suggest_list.clear()
        if not self._models:
            return
        names = [m.name for m in self._models]
        thr = self._cfg.min_name_similarity
        pairs = model_pairs_by_ratio(names, min_ratio=thr)
        for a, b, s in pairs[:80]:
            lab = f"{a}  ↔  {b}  ({s * 100:.0f}%)"
            it = QListWidgetItem(lab)
            it.setData(Qt.ItemDataRole.UserRole, f"{a}|{b}")
            self._suggest_list.addItem(it)
        for grp in model_groups_by_prefix(names)[:20]:
            if len(grp) < 2:
                continue
            lab = f"Group: {' · '.join(grp)}"
            it = QListWidgetItem(lab)
            it.setData(Qt.ItemDataRole.UserRole, f"{grp[0]}|{grp[-1]}")
            it.setToolTip("Compare first vs last in the group; edit dropdowns as needed")
            self._suggest_list.addItem(it)

    def _recompute_diff_data(self) -> None:
        if self._src_data is None or self._tgt_data is None:
            return
        o = self._diff_opts()
        self._diff_rows = diff_json_trees(
            self._src_data,
            self._tgt_data,
            use_aligned=o["use_aligned"],
            id_keys=o["id_keys"],
        )
        self._rebuild_table()

    def _export_table_tsv(self) -> None:
        if not self._diff_display:
            QMessageBox.information(self, "Export", "No rows to export — run “Load & compare” first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export diff table (TSV)",
            str(app_root() / "vts_model_diff.tsv"),
            "TSV / Text (*.tsv *.txt);;All (*)",
        )
        if not path:
            return
        try:
            lines: List[str] = [
                "path\tsource_value\ttarget_value\tstatus",
            ]
            for r in self._diff_display:
                lines.append(
                    f"{r.path_s}\t{r.value_a_str}\t{r.value_b_str}\t{_row_kind_text(r.kind)}"
                )
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
        except OSError as e:
            QMessageBox.critical(self, "Export", str(e))
            return
        self._status.setText(f"Exported {len(self._diff_display)} row(s) to {path}")

    def _live2d_path(self) -> Optional[Path]:
        p = self._path_edit.text().strip()
        if not p:
            return None
        x = Path(p)
        return x if x.is_dir() else None

    def _on_path_changed(self, text: str) -> None:
        self._cfg.live2d_models_path = text.strip()
        self._cfg.save()

    def _on_filter_toggle(self, checked: bool) -> None:
        self._cfg.hide_identical_rows = checked
        self._cfg.save()
        self._rebuild_table()

    def _on_model_pick_change(self, _: str) -> None:
        self._save_model_choices()
        self._rebuild_file_combo()
        self._auto_compare_soon()
        self._refresh_migration_summaries()

    def _on_file_change(self, text: str) -> None:
        self._cfg.last_json_file = text.strip()
        self._cfg.save()
        self._auto_compare_soon()

    def _auto_compare_soon(self) -> None:
        """If both models and file exist, load & compare (optional quick feedback)."""
        if self._src_combo.currentText() and self._tgt_combo.currentText() and self._file_combo.currentText():
            # lightweight: do not auto-run heavy compare; user clicks Load
            pass

    def _save_model_choices(self) -> None:
        self._cfg.last_source_model = self._src_combo.currentText()
        self._cfg.last_target_model = self._tgt_combo.currentText()
        self._cfg.save()

    def _browse_models_path(self) -> None:
        start = self._path_edit.text().strip() or str(app_root())
        if not os.path.isdir(start):
            start = str(app_root())
        d = QFileDialog.getExistingDirectory(self, "Select Live2DModels folder", start)
        if d:
            self._path_edit.setText(d)

    def _on_scan(self, quiet: bool) -> bool:
        self._models = []
        self._src_combo.clear()
        self._tgt_combo.clear()
        self._file_combo.clear()
        root = self._live2d_path()
        if not root:
            if not quiet:
                QMessageBox.warning(self, "Path", "Set a valid Live2D models folder.")
            return False
        self._models = scan_models(root)
        for m in self._models:
            self._src_combo.addItem(m.name)
            self._tgt_combo.addItem(m.name)
        # restore from config
        def pick(combo: QComboBox, name: str) -> None:
            if not name:
                return
            i = combo.findText(name)
            if i >= 0:
                combo.setCurrentIndex(i)

        self._src_combo.blockSignals(True)
        self._tgt_combo.blockSignals(True)
        pick(self._src_combo, self._cfg.last_source_model)
        pick(self._tgt_combo, self._cfg.last_target_model)
        self._src_combo.blockSignals(False)
        self._tgt_combo.blockSignals(False)
        self._rebuild_file_combo()
        if not quiet and not self._models:
            QMessageBox.information(
                self, "Scan", "No subfolders with JSON were found in that path."
            )
        self._rebuild_suggestions()
        self._fill_restore_combos()
        self._refresh_migration_summaries()
        return bool(self._models)

    def _rebuild_file_combo(self) -> None:
        self._file_combo.clear()
        sn = self._src_combo.currentText()
        tn = self._tgt_combo.currentText()
        if not sn or not tn or sn == tn:
            return
        a = self._find_model(sn)
        b = self._find_model(tn)
        if not a or not b:
            return
        for fn in common_json_names(a, b):
            self._file_combo.addItem(fn)
        if self._file_combo.count() == 0:
            return
        want = self._cfg.last_json_file
        if want and self._file_combo.findText(want) >= 0:
            self._file_combo.setCurrentText(want)
        else:
            a_vt, b_vt = a.vtube_file(), b.vtube_file()
            if a_vt and a_vt == b_vt and self._file_combo.findText(a_vt) >= 0:
                self._file_combo.setCurrentText(a_vt)

    def _find_model(self, name: str) -> Optional[ModelInfo]:
        for m in self._models:
            if m.name == name:
                return m
        return None

    def _compare(self) -> None:
        root = self._live2d_path()
        if not root:
            QMessageBox.warning(self, "Path", "Invalid Live2D models folder.")
            return
        sn, tn, fn = (
            self._src_combo.currentText(),
            self._tgt_combo.currentText(),
            self._file_combo.currentText(),
        )
        if not sn or not tn or sn == tn:
            QMessageBox.warning(
                self, "Models", "Pick two different model folders (source and target)."
            )
            return
        if not fn:
            QMessageBox.warning(
                self, "File", "No common JSON file between these two models."
            )
            return
        try:
            sa = load_json(root / sn / fn)
            sb = load_json(root / tn / fn)
        except OSError as e:
            QMessageBox.critical(self, "Read error", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "JSON error", str(e))
            return
        if not isinstance(sa, dict) or not isinstance(sb, dict):
            QMessageBox.warning(
                self, "Format", "This tool expects a JSON object at the root of the file."
            )
            return
        self._src_name, self._tgt_name, self._current_filename = sn, tn, fn
        self._src_data, self._tgt_data = sa, sb
        o = self._diff_opts()
        self._diff_rows = diff_json_trees(
            self._src_data,
            self._tgt_data,
            use_aligned=o["use_aligned"],
            id_keys=o["id_keys"],
        )
        self._rebuild_table()
        n = len(self._diff_display)
        self._status.setText(
            f"Compared {self._src_name} vs {self._tgt_name} — {n} table row(s) "
            f"({len(self._diff_rows)} total leaf rows)."
        )

    def _rebuild_table(self) -> None:
        hide = self._hide_ident.isChecked()
        self._diff_display = [r for r in self._diff_rows if (not hide or r.kind != RowKind.SAME)]
        self._table.setRowCount(len(self._diff_display))
        for i, r in enumerate(self._diff_display):
            bg = {
                RowKind.SAME: COLOR_SAME,
                RowKind.DIFFER: COLOR_DIFF,
                RowKind.ONLY_A: COLOR_MISS,
                RowKind.ONLY_B: COLOR_MISS,
                RowKind.TYPE_MISMATCH: COLOR_TYPE,
            }[r.kind]
            c0 = QTableWidgetItem(r.path_s)
            c1 = QTableWidgetItem(r.value_a_str)
            c2 = QTableWidgetItem(r.value_b_str)
            c3 = QTableWidgetItem(_row_kind_text(r.kind))
            for c in (c0, c1, c2, c3):
                c.setFlags(c0.flags() & ~Qt.ItemFlag.ItemIsEditable)
                c.setBackground(QBrush(bg))
            c0.setData(Qt.ItemDataRole.UserRole, r)
            self._table.setItem(i, 0, c0)
            self._table.setItem(i, 1, c1)
            self._table.setItem(i, 2, c2)
            self._table.setItem(i, 3, c3)

    def _selected_diff_rows(self) -> List[DiffRow]:
        rows: List[DiffRow] = []
        for idx in {i.row() for i in self._table.selectedIndexes()}:
            it = self._table.item(idx, 0)
            if it:
                r = it.data(Qt.ItemDataRole.UserRole)
                if r:
                    rows.append(r)
        return rows

    def _ensure_write_session(self) -> Path:
        if self._write_session is None:
            ar = app_root()
            self._write_session = create_session(
                ar, self._cfg.backup_root, f"{self._tgt_name}_{self._current_filename}"
            )
        return self._write_session

    def _new_write_session(self) -> None:
        self._write_session = None
        QMessageBox.information(
            self, "Session", "Cleared. The next write will use a new backup folder."
        )

    def _apply_copy_selected(self) -> None:
        if self._src_data is None or self._tgt_data is None or not self._current_filename:
            QMessageBox.information(self, "Compare", "Run “Load & compare” first.")
            return
        sel = self._selected_diff_rows()
        rows = [r for r in sel if _row_can_copy_from_a(r.kind)]
        if not rows:
            QMessageBox.information(
                self, "Selection",
                "Select rows that can receive a value from source (not “only target”).",
            )
            return
        root = self._live2d_path()
        if not root:
            return
        try:
            sess = self._ensure_write_session()
            backup_file(sess, root, self._tgt_name, self._current_filename)
        except OSError as e:
            QMessageBox.critical(self, "Backup failed", str(e))
            return
        for r in rows:
            try:
                copy_source_leaf_to_target(
                    self._src_data,
                    self._tgt_data,
                    r.path_in_source,
                    r.path_in_target,
                )
            except Exception as e:
                QMessageBox.critical(
                    self, f"Path {r.path_s}", f"Failed to set value: {e}"
                )
                return
        try:
            write_json_to_live(
                self._tgt_data, root, self._tgt_name, self._current_filename
            )
        except OSError as e:
            QMessageBox.critical(self, "Save", str(e))
            return
        self._resync_after_write()
        self._status.setText(
            f"Applied {len(rows)} value(s) from A to B — target file saved."
        )

    def _apply_edited(self) -> None:
        if self._tgt_data is None or not self._current_filename:
            QMessageBox.information(self, "Compare", "Run “Load & compare” first.")
            return
        sel = self._selected_diff_rows()
        if len(sel) != 1:
            QMessageBox.information(
                self, "Edit", "Select exactly one row to edit the target value."
            )
            return
        r = sel[0]
        root = self._live2d_path()
        if not root:
            return
        if r.kind == RowKind.ONLY_A and self._src_data is not None:
            cur: object = r.value_a
        else:
            try:
                cur = get_at(self._tgt_data, r.path_in_target)
            except (KeyError, IndexError, TypeError):
                cur = r.value_b if r.value_b is not None else r.value_a
        ok, newv = run_edit_value(r.path_s, cur, self)
        if not ok or newv is None:
            return
        try:
            sess = self._ensure_write_session()
            backup_file(sess, root, self._tgt_name, self._current_filename)
        except OSError as e:
            QMessageBox.critical(self, "Backup failed", str(e))
            return
        try:
            set_target_leaf(self._tgt_data, r.path_in_target, newv)
        except Exception as e:
            QMessageBox.critical(self, "Apply", str(e))
            return
        try:
            write_json_to_live(
                self._tgt_data, root, self._tgt_name, self._current_filename
            )
        except OSError as e:
            QMessageBox.critical(self, "Save", str(e))
            return
        self._resync_after_write()
        self._status.setText("Edited value applied to target — file saved.")

    def _resync_after_write(self) -> None:
        root = self._live2d_path()
        if not root or not self._current_filename or not self._tgt_name:
            return
        try:
            self._tgt_data = load_json(root / self._tgt_name / self._current_filename)
        except Exception:
            pass
        if self._src_data is not None and isinstance(self._tgt_data, dict):
            o = self._diff_opts()
            self._diff_rows = diff_json_trees(
                self._src_data,
                self._tgt_data,
                use_aligned=o["use_aligned"],
                id_keys=o["id_keys"],
            )
            self._rebuild_table()

    def _fill_restore_combos(self) -> None:
        self._sess_combo.blockSignals(True)
        self._sess_combo.clear()
        self._sess_combo.blockSignals(False)
        self._back_model.blockSignals(True)
        self._back_model.clear()
        self._back_model.blockSignals(False)
        self._back_file.clear()
        br = resolve_backup_dir(app_root(), self._cfg.backup_root)
        for p in list_sessions(br):
            self._sess_combo.addItem(p.name, p)
        self._on_session_change_restore()

    def _on_session_change_restore(self) -> None:
        self._back_model.blockSignals(True)
        self._back_model.clear()
        self._back_model.blockSignals(False)
        self._back_file.clear()
        data = self._sess_combo.currentData()
        if not data or not isinstance(data, Path):
            return
        sess: Path = data
        for sub in sorted(sess.iterdir(), key=lambda p: p.name.lower()):
            if sub.is_dir():
                self._back_model.addItem(sub.name, sub)
        self._on_restore_model_fill_files()

    def _on_restore_model_fill_files(self) -> None:
        self._back_file.clear()
        sess = self._sess_combo.currentData()
        sub = self._back_model.currentData()
        if not isinstance(sess, Path) or not isinstance(sub, Path):
            return
        for name in list_files_in_model_backup(sess, sub.name):
            self._back_file.addItem(name)

    def _restore_one(self) -> None:
        sess = self._sess_combo.currentData()
        mod = self._back_model.currentText()
        fn = self._back_file.currentText()
        root = self._live2d_path()
        if not isinstance(sess, Path) or not mod or not fn or not root:
            QMessageBox.warning(self, "Restore", "Select session, model, and file; set Live2D path.")
            return
        p = (sess / mod / fn).resolve()
        if not p.is_file():
            QMessageBox.warning(self, "Restore", f"File not in backup: {p}")
            return
        m = QMessageBox.question(
            self,
            "Overwrite",
            f"Replace live file {mod}/{fn} with this backup? VTS should be closed.",
        )
        if m != QMessageBox.StandardButton.Yes:
            return
        try:
            restore_file(sess, root, mod, fn)
        except OSError as e:
            QMessageBox.critical(self, "Restore", str(e))
            return
        QMessageBox.information(self, "Restore", f"Restored: {root / mod / fn}")
        if self._tgt_name == mod and self._current_filename == fn:
            self._resync_after_write()
        self._refresh_migration_summaries()

    def _refresh_migration_summaries(self) -> None:
        self._refresh_hotkey_summary(update_status=False)
        self._refresh_parameter_summary(update_status=False)
        npairs = len(self._hotkey_file_pairs())
        self._status.setText(
            f"Summaries refreshed — Hotkey: {len(self._summary_rows)} row(s); "
            f"Parameter: {len(self._param_rows)} row(s); "
            f"{npairs} JSON file pair(s)."
        )

    def _hotkey_file_pairs(self) -> List[tuple[str, str]]:
        sn = self._src_combo.currentText()
        tn = self._tgt_combo.currentText()
        a, b = self._find_model(sn), self._find_model(tn)
        if not a or not b or not sn or not tn or sn == tn:
            return []
        return paired_json_for_hotkey_summary(a, b)

    def _refresh_hotkey_summary(self, update_status: bool = True) -> None:
        root = self._live2d_path()
        sn, tn = self._src_combo.currentText(), self._tgt_combo.currentText()
        pairs = self._hotkey_file_pairs()
        if not root or not pairs:
            self._summary_rows = []
            self._rebuild_summary_table()
            if update_status:
                self._status.setText("Hotkey summary: no file pairs (pick two models).")
            return
        try:
            self._summary_rows = build_cross_file_summary(root, sn, tn, pairs)
        except (OSError, ValueError) as e:
            self._status.setText(f"Hotkey summary failed: {e}")
            self._summary_rows = []
        self._rebuild_summary_table()
        if update_status:
            self._status.setText(
                f"Hotkey summary: {len(self._summary_rows)} row(s) from {len(pairs)} JSON file pair(s)."
            )

    def _on_sum_filter_toggle(self, _: bool) -> None:
        self._rebuild_summary_table()

    def _rebuild_summary_table(self) -> None:
        hide = self._sum_hide_match.isChecked()
        self._summary_display = [
            r
            for r in self._summary_rows
            if not (hide and r.in_target and r.keys_match is True)
        ]
        self._summary_table.setRowCount(len(self._summary_display))
        for i, r in enumerate(self._summary_display):
            if r.in_target:
                if r.keys_match:
                    bg = COLOR_SAME
                elif r.keys_match is False:
                    bg = COLOR_DIFF
                else:
                    bg = COLOR_MISS
            else:
                bg = COLOR_MISS
            in_b = "yes" if r.in_target else "no"
            match_txt = "—"
            if r.keys_match is True:
                match_txt = "yes"
            elif r.keys_match is False:
                match_txt = "no"
            vals = [
                r.json_pair_label(),
                r.hotkey_id,
                r.name,
                r.toggle_file,
                r.action,
                r.keybind_a,
                in_b,
                r.keybind_b,
                match_txt,
            ]
            for col, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setBackground(QBrush(bg))
                it.setData(Qt.ItemDataRole.UserRole, r)
                self._summary_table.setItem(i, col, it)

    def _export_summary_tsv(self) -> None:
        if not self._summary_display:
            QMessageBox.information(self, "Export", "No summary rows — refresh the hotkey summary first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export hotkey summary (TSV)",
            str(app_root() / "vts_hotkey_summary.tsv"),
            "TSV (*.tsv);;Text (*.txt);;All (*)",
        )
        if not path:
            return
        try:
            hdr = "json_pair\thotkey_id\tname\ttoggle_file\taction\tkeybind_a\tin_target\tkeybind_b\tkeys_match\n"
            lines = [hdr]
            for r in self._summary_display:
                mt = "yes" if r.keys_match is True else ("no" if r.keys_match is False else "")
                lines.append(
                    f"{r.json_pair_label()}\t{r.hotkey_id}\t{r.name}\t{r.toggle_file}\t{r.action}\t"
                    f"{r.keybind_a}\t{'yes' if r.in_target else 'no'}\t{r.keybind_b}\t{mt}\n"
                )
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.writelines(lines)
        except OSError as e:
            QMessageBox.critical(self, "Export", str(e))
            return
        self._status.setText(f"Exported hotkey summary to {path}")

    def _open_copy_wizard(self) -> None:
        root = self._live2d_path()
        if not root:
            QMessageBox.warning(self, "Path", "Set a valid Live2D models folder.")
            return
        if not self._summary_rows:
            QMessageBox.information(
                self,
                "Summary empty",
                "Click “Refresh hotkey summary” first (Hotkey summary tab).",
            )
            return
        ctx = WizardContext(
            live2d=root,
            src_model=self._src_combo.currentText(),
            tgt_model=self._tgt_combo.currentText(),
            summary_rows=list(self._summary_rows),
            cfg=self._cfg,
            on_completed=self._refresh_migration_summaries,
        )
        run_copy_wizard(self, ctx)

    def _refresh_parameter_summary(self, update_status: bool = True) -> None:
        root = self._live2d_path()
        sn, tn = self._src_combo.currentText(), self._tgt_combo.currentText()
        pairs = self._hotkey_file_pairs()
        if not root or not pairs:
            self._param_rows = []
            self._rebuild_parameter_table()
            if update_status:
                self._status.setText("Parameter summary: no file pairs (pick two models).")
            return
        try:
            self._param_rows = build_parameter_cross_file_summary(root, sn, tn, pairs)
        except (OSError, ValueError) as e:
            self._status.setText(f"Parameter summary failed: {e}")
            self._param_rows = []
        self._rebuild_parameter_table()
        if update_status:
            self._status.setText(
                f"Parameter summary: {len(self._param_rows)} row(s) from {len(pairs)} JSON file pair(s)."
            )

    def _on_param_filter_toggle(self, _: bool) -> None:
        self._rebuild_parameter_table()

    def _rebuild_parameter_table(self) -> None:
        hide = self._param_hide_match.isChecked()
        self._param_display = [
            r
            for r in self._param_rows
            if not (hide and r.in_target and r.fields_match is True)
        ]
        self._param_table.setRowCount(len(self._param_display))
        for i, r in enumerate(self._param_display):
            if r.in_target:
                if r.fields_match:
                    bg = COLOR_SAME
                elif r.fields_match is False:
                    bg = COLOR_DIFF
                else:
                    bg = COLOR_MISS
            else:
                bg = COLOR_MISS
            in_b = "yes" if r.in_target else "no"
            match_txt = "—"
            if r.fields_match is True:
                match_txt = "yes"
            elif r.fields_match is False:
                match_txt = "no"
            vals = [
                r.json_pair_label(),
                r.name,
                r.output_live2d,
                r.input_a,
                r.input_b,
                r.smoothing_a,
                r.smoothing_b,
                r.clamp_in_a,
                r.clamp_in_b,
                r.clamp_out_a,
                r.clamp_out_b,
                r.in_range_a,
                r.in_range_b,
                r.out_range_a,
                r.out_range_b,
                in_b,
                match_txt,
            ]
            for col, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setBackground(QBrush(bg))
                it.setData(Qt.ItemDataRole.UserRole, r)
                self._param_table.setItem(i, col, it)

    def _export_parameter_tsv(self) -> None:
        if not self._param_display:
            QMessageBox.information(
                self, "Export", "No parameter rows — refresh the parameter summary first."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export parameter summary (TSV)",
            str(app_root() / "vts_parameter_summary.tsv"),
            "TSV (*.tsv);;Text (*.txt);;All (*)",
        )
        if not path:
            return
        try:
            hdr = (
                "json_pair\tname\toutput_live2d\tinput_a\tinput_b\tsmoothing_a\tsmoothing_b\t"
                "clamp_in_a\tclamp_in_b\tclamp_out_a\tclamp_out_b\t"
                "in_range_a\tin_range_b\tout_range_a\tout_range_b\tin_target\tfields_match\n"
            )
            lines = [hdr]
            for r in self._param_display:
                mt = (
                    "yes"
                    if r.fields_match is True
                    else ("no" if r.fields_match is False else "")
                )
                lines.append(
                    f"{r.json_pair_label()}\t{r.name}\t{r.output_live2d}\t{r.input_a}\t{r.input_b}\t"
                    f"{r.smoothing_a}\t{r.smoothing_b}\t{r.clamp_in_a}\t{r.clamp_in_b}\t"
                    f"{r.clamp_out_a}\t{r.clamp_out_b}\t{r.in_range_a}\t{r.in_range_b}\t"
                    f"{r.out_range_a}\t{r.out_range_b}\t{'yes' if r.in_target else 'no'}\t{mt}\n"
                )
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.writelines(lines)
        except OSError as e:
            QMessageBox.critical(self, "Export", str(e))
            return
        self._status.setText(f"Exported parameter summary to {path}")

    def _open_parameter_copy_wizard(self) -> None:
        root = self._live2d_path()
        if not root:
            QMessageBox.warning(self, "Path", "Set a valid Live2D models folder.")
            return
        if not self._param_rows:
            QMessageBox.information(
                self,
                "Summary empty",
                "Click “Refresh parameter summary” first (Parameter summary tab).",
            )
            return
        ctx = ParameterWizardContext(
            live2d=root,
            src_model=self._src_combo.currentText(),
            tgt_model=self._tgt_combo.currentText(),
            summary_rows=list(self._param_rows),
            cfg=self._cfg,
            on_completed=self._refresh_migration_summaries,
        )
        run_parameter_copy_wizard(self, ctx)

    def closeEvent(self, event: QCloseEvent) -> None:
        g = self.geometry()
        self._cfg.set_window_size(g.width(), g.height())
        self._cfg.save()
        super().closeEvent(event)
