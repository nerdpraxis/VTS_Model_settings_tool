"""
VTS Model Settings Tool — entry point.

Standalone utility for comparing/migrating VTube Studio on-disk model JSON.
See README.md for usage; PLAN.md for design notes.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from vts_mst.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    # Windows "windowsvista" style often ignores QTabBar colors → invisible tab text on dark UI.
    app.setStyle("Fusion")
    app.setApplicationName("VTS Model Settings Tool")
    app.setOrganizationName("VTSModelSettingsTool")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
