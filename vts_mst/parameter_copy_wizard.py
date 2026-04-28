"""Wizard: copy ParameterSettings fields from source model to target with preview + backup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtWidgets import (
    QCheckBox,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from vts_mst.backup_ops import create_session
from vts_mst.config_manager import AppConfig
from vts_mst.copy_planner import PlannedKeybindWrite
from vts_mst.parameter_compare import ParameterSummaryRow
from vts_mst.parameter_copy_planner import (
    ParameterCopyScope,
    execute_planned_parameter_writes,
    plan_parameter_writes,
)
from vts_mst.paths import app_root

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

WIZARD_STYLE = """
QWizard, QWizardPage { background-color: #1e1e1e; color: #ffffff; }
QLabel { color: #ffffff; }
QCheckBox { color: #ffffff; }
QTableWidget { background: #252525; gridline-color: #444; color: #fff; }
QHeaderView::section { background: #333; color: #fff; }
QPushButton { background: #2953F0; color: #fff; padding: 8px 16px; border: none; border-radius: 4px; }
"""


@dataclass
class ParameterWizardContext:
    live2d: Path
    src_model: str
    tgt_model: str
    summary_rows: List[ParameterSummaryRow]
    cfg: AppConfig
    on_completed: Optional[Callable[[], None]] = None


class ParameterCopyWizard(QWizard):
    def __init__(self, parent: Optional[QWidget], ctx: ParameterWizardContext) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._plan: List[PlannedKeybindWrite] = []
        self.setWindowTitle("Copy parameters — guided steps")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setStyleSheet(WIZARD_STYLE)

        self._page_intro = _ParamIntroPage()
        self._page_scope = _ParamScopePage()
        self._page_preview = _ParamPreviewPage(self)
        self._page_commit = _ParamCommitPage()

        self.addPage(self._page_intro)
        self.addPage(self._page_scope)
        self.addPage(self._page_preview)
        self.addPage(self._page_commit)

    def _scope(self) -> ParameterCopyScope:
        s = self._page_scope
        return ParameterCopyScope(
            copy_input=s.cb_input.isChecked(),
            copy_smoothing=s.cb_smooth.isChecked(),
            copy_clamp_input=s.cb_clamp_in.isChecked(),
            copy_clamp_output=s.cb_clamp_out.isChecked(),
            copy_input_range=s.cb_in_range.isChecked(),
            copy_output_range=s.cb_out_range.isChecked(),
        )

    def rebuild_plan(self) -> None:
        only_diff = self._page_scope.cb_only_diff.isChecked()
        self._plan = plan_parameter_writes(
            self._ctx.summary_rows, self._scope(), only_diff
        )
        self._page_preview.fill(self._plan)

    def accept(self) -> None:
        if self.currentPage() is not self._page_commit:
            super().accept()
            return
        self.rebuild_plan()
        if not self._plan:
            QMessageBox.information(
                self,
                "Nothing to do",
                "No parameter field copies match your scope. Adjust Step 2 or refresh the summary.",
            )
            return
        ctx = self._ctx
        sess = create_session(
            app_root(), ctx.cfg.backup_root, f"{ctx.tgt_model}_param_wizard"
        )
        n, err = execute_planned_parameter_writes(
            ctx.live2d, ctx.tgt_model, self._plan, sess
        )
        if err:
            QMessageBox.critical(self, "Write failed", err)
            return
        QMessageBox.information(
            self,
            "Done",
            f"Updated {n} parameter field(s).\nBackup folder:\n{sess}",
        )
        if ctx.on_completed:
            ctx.on_completed()
        super().accept()


def run_parameter_copy_wizard(
    parent: Optional[QWidget], ctx: ParameterWizardContext
) -> bool:
    w = ParameterCopyWizard(parent, ctx)
    return w.exec() == QWizard.DialogCode.Accepted


class _ParamIntroPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Step 1 — Welcome")
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "This wizard copies <b>parameter mapping fields</b> from the <b>source</b> model into "
                "the <b>target</b> for each entry in <tt>ParameterSettings</tt> that matches by "
                "<b>OutputLive2D</b> (fallback: same <b>Input</b> name).\n\n"
                "You can include: <b>Input</b> source name, <b>ClampInput</b> / <b>ClampOutput</b>, "
                "<b>Smoothing</b>, <b>InputRange</b> lower/upper, <b>OutputRange</b> lower/upper.\n\n"
                "Nothing is written until <b>Finish</b>. Close VTube Studio first."
            )
        )
        lay.addWidget(QLabel("Click <b>Next</b> to choose fields and filters."))
        lay.addStretch()


class _ParamScopePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Step 2 — What to copy")
        self.cb_only_diff = QCheckBox(
            "Only parameters that already exist in the target but differ somewhere"
        )
        self.cb_only_diff.setChecked(True)
        self.cb_input = QCheckBox("Input (tracking source name)")
        self.cb_input.setChecked(True)
        self.cb_smooth = QCheckBox("Smoothing")
        self.cb_smooth.setChecked(True)
        self.cb_clamp_in = QCheckBox("ClampInput (limit input range)")
        self.cb_clamp_in.setChecked(True)
        self.cb_clamp_out = QCheckBox("ClampOutput (limit output range)")
        self.cb_clamp_out.setChecked(True)
        self.cb_in_range = QCheckBox("Input min/max (InputRangeLower & InputRangeUpper)")
        self.cb_in_range.setChecked(True)
        self.cb_out_range = QCheckBox("Output min/max (OutputRangeLower & OutputRangeUpper)")
        self.cb_out_range.setChecked(True)
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "Parameters that exist only in the source appear in the summary but cannot receive "
                "writes in the target until a matching <tt>OutputLive2D</tt> / <tt>Input</tt> row exists."
            )
        )
        lay.addWidget(self.cb_only_diff)
        lay.addWidget(self.cb_input)
        lay.addWidget(self.cb_smooth)
        lay.addWidget(self.cb_clamp_in)
        lay.addWidget(self.cb_clamp_out)
        lay.addWidget(self.cb_in_range)
        lay.addWidget(self.cb_out_range)
        lay.addStretch()


class _ParamPreviewPage(QWizardPage):
    def __init__(self, wizard: ParameterCopyWizard) -> None:
        super().__init__()
        self._wiz = wizard
        self.setTitle("Step 3 — Preview")
        lay = QVBoxLayout(self)
        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Target JSON file", "Field / parameter"])
        self._table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._table)

    def initializePage(self) -> None:
        self._wiz.rebuild_plan()
        n = len(self._wiz._plan)
        self._hint.setText(
            f"<b>{n}</b> JSON leaf value(s) will be written in the target model "
            f"<b>{self._wiz._ctx.tgt_model}</b>."
        )

    def fill(self, plan: List[PlannedKeybindWrite]) -> None:
        self._table.setRowCount(len(plan))
        for i, p in enumerate(plan):
            self._table.setItem(i, 0, QTableWidgetItem(p.json_file))
            self._table.setItem(i, 1, QTableWidgetItem(p.label))


class _ParamCommitPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setFinalPage(True)
        self.setTitle("Step 4 — Confirm")
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "Click <b>Finish</b> to create a timestamped backup and write parameter fields into "
                "the target model’s JSON files."
            )
        )
        lay.addStretch()
