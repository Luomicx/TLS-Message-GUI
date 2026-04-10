from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from .db import Database
from .ui import MainWindow
from .ui.theme import build_admin_stylesheet, resolve_ui_metrics


def main() -> int:
    app = QApplication(sys.argv)
    ui_metrics = resolve_ui_metrics()
    app.setStyleSheet(build_admin_stylesheet(ui_metrics.scale))

    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "server.db"

    db = Database(db_path)
    db.init_schema()
    db.ensure_seed_users()

    win = MainWindow(db=db)
    win.show()

    return app.exec_()
