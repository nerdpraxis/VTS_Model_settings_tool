"""Multi-step wizard: preview planned keyCombination copies before writing to disk."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional

from PyQt6.QtCore import Qt
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
from vts_mst.copy_planner import PlannedKeybindWrite, execute_planned_keybinds, plan_keybind_writes
from vts_mst.hotkey_compare import HotkeySummaryRow
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
class WizardContext:
    live2d: Path
    src_model: str
    tgt_model: str
    summary_rows: List[HotkeySummaryRow]
    cfg: AppConfig
    on_completed: Optional[Callable[[], None]] = None


class CopyWizard(QWizard):
    def __init__(self, parent: Optional[QWidget], ctx: WizardContext) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._plan: List[PlannedKeybindWrite] = []
        self.setWindowTitle("Copy keybinds — guided steps")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setStyleSheet(WIZARD_STYLE)

        self._page_intro = _IntroPage()
        self._page_scope = _ScopePage()
        self._page_preview = _PreviewPage(self)
        self._page_commit = _CommitPage()

        self.addPage(self._page_intro)
        self.addPage(self._page_scope)
        self.addPage(self._page_preview)
        self.addPage(self._page_commit)

    def rebuild_plan(self) -> None:
        only_diff = self._page_scope.cb_only_diff.isChecked()
        self._plan = plan_keybind_writes(self._ctx.summary_rows, only_diff)
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
                "No keybind copies match your scope. Adjust Step 2 or build a fresh hotkey summary.",
            )
            return
        ctx = self._ctx
        sess = create_session(app_root(), ctx.cfg.backup_root, f"{ctx.tgt_model}_wizard")
        n, err = execute_planned_keybinds(
            ctx.live2d, ctx.src_model, ctx.tgt_model, self._plan, sess
        )
        if err:
            QMessageBox.critical(self, "Write failed", err)
            return
        QMessageBox.information(
            self,
            "Done",
            f"Updated {n} keybind field(s).\nBackup folder:\n{sess}",
        )
        if ctx.on_completed:
            ctx.on_completed()
        super().accept()


def run_copy_wizard(parent: Optional[QWidget], ctx: WizardContext) -> bool:
    w = CopyWizard(parent, ctx)
    return w.exec() == QWizard.DialogCode.Accepted


class _IntroPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Step 1 — Welcome")
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "This wizard copies <b>keyboard bindings</b> from your <b>source</b> model into the "
                "<b>target</b> model: either <tt>keyCombination</tt> (API-style JSON) or on-disk "
                "<tt>Triggers</tt> (Trigger1/2/3, ScreenButton), only where the same hotkey "
                "(matching ID, or name+toggle file) exists in both.\n\n"
                "Nothing is written until you click <b>Finish</b> on the last step. "
                "Close VTube Studio first."
            )
        )
        lay.addWidget(QLabel("Click <b>Next</b> to choose what to include."))
        lay.addStretch()


class _ScopePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Step 2 — What to copy")
        self.cb_only_diff = QCheckBox(
            "Only hotkeys that already exist in the target but have a different keybind"
        )
        self.cb_only_diff.setChecked(True)
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "Hotkeys that exist only in the source appear in the summary table but cannot be "
                "synced by this wizard (adding new array entries is not implemented yet)."
            )
        )
        lay.addWidget(self.cb_only_diff)
        lay.addStretch()


class _PreviewPage(QWizardPage):
    def __init__(self, wizard: CopyWizard) -> None:
        super().__init__()
        self._wiz = wizard
        self.setTitle("Step 3 — Preview")
        lay = QVBoxLayout(self)
        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        lay.addWidget(self._hint)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["JSON file", "Hotkey / toggle"])
        self._table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self._table)

    def initializePage(self) -> None:
        self._wiz.rebuild_plan()
        n = len(self._wiz._plan)
        self._hint.setText(
            f"<b>{n}</b> keybind field(s) will be updated in the target model "
            f"<b>{self._wiz._ctx.tgt_model}</b>."
        )

    def fill(self, plan: List[PlannedKeybindWrite]) -> None:
        self._table.setRowCount(len(plan))
        for i, p in enumerate(plan):
            self._table.setItem(i, 0, QTableWidgetItem(p.json_file))
            self._table.setItem(i, 1, QTableWidgetItem(p.label))


class _CommitPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setFinalPage(True)
        self.setTitle("Step 4 — Confirm")
        lay = QVBoxLayout(self)
        lay.addWidget(
            QLabel(
                "Click <b>Finish</b> to create a timestamped backup and write keybinds into the "
                "target model’s JSON files."
            )
        )
        lay.addStretch()
