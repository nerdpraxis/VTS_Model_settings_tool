"""Edit a JSON value (scalar or small structure) before applying to target."""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class JsonValueEditDialog(QDialog):
    """
    Edit value as JSON text. Returns (accepted, python_value).
    """

    def __init__(
        self,
        title: str,
        path_label: str,
        initial_value: Any,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 360)
        self._result: Any = None
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(path_label))
        self._edit = QTextEdit()
        self._edit.setStyleSheet(
            "QTextEdit { background: #2d2d2d; color: #fff; border: 1px solid #555; }"
        )
        if isinstance(initial_value, (dict, list)):
            text = json.dumps(initial_value, ensure_ascii=False, indent=2)
        else:
            text = json.dumps(initial_value, ensure_ascii=False)
        self._edit.setPlainText(text)
        lay.addWidget(self._edit)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _ok(self) -> None:
        raw = self._edit.toPlainText().strip()
        try:
            self._result = json.loads(raw)
        except json.JSONDecodeError as e:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self, "Invalid JSON", str(e), QMessageBox.StandardButton.Ok
            )
            return
        self.accept()

    def value(self) -> Any:
        return self._result


def run_edit_value(
    path_s: str, initial: Any, parent=None
) -> Tuple[bool, Optional[Any]]:
    d = JsonValueEditDialog("Edit value", path_s, initial, parent)
    if d.exec() != QDialog.DialogCode.Accepted:
        return False, None
    return True, d.value()
