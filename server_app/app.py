from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from .db import Database
from .ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

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
