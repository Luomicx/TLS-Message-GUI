from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QAction,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QToolBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..db import Database
from ..network import ServerController
from .avatar import make_placeholder_avatar, pixmap_from_avatar_blob
from .user_management_dialog import UserManagementDialog


class MainWindow(QMainWindow):
    def __init__(self, *, db: Database):
        super().__init__()
        self.db = db
        self.server_controller = ServerController(db=db)
        self.server_controller.log_signal.connect(self.append_log)

        self.setWindowTitle("安全网络聊天工具 - 服务器")
        self.resize(1000, 700)

        self._build_toolbar()
        self._build_central()

        self.refresh_unlocked_users()
        self.append_log("UI initialized")

    def _build_toolbar(self) -> None:
        tb = QToolBar("toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_user_mgmt = QAction("用户管理", self)
        self.act_user_mgmt.triggered.connect(self.open_user_mgmt)
        tb.addAction(self.act_user_mgmt)

        tb.addSeparator()

        tb.addWidget(QLabel("监听端口:"))
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(8000)
        self.spin_port.setFixedWidth(90)
        tb.addWidget(self.spin_port)

        self.act_start = QAction(self)
        self.act_start.setIcon(self.style().standardIcon(self.style().SP_MediaPlay))
        self.act_start.triggered.connect(self.toggle_start)
        tb.addAction(self.act_start)

    def _build_central(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.list_users = QListWidget()
        self.list_users.setViewMode(QListWidget.IconMode)
        self.list_users.setResizeMode(QListWidget.Adjust)
        self.list_users.setMovement(QListWidget.Static)
        self.list_users.setIconSize(QSize(64, 64))
        self.list_users.setSpacing(16)
        self.list_users.setWordWrap(True)
        self.list_users.setMaximumHeight(220)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        layout.addWidget(self.list_users)
        layout.addWidget(self.log, 1)
        self.setCentralWidget(root)

    def _log_color(self, msg: str) -> QColor:
        upper_msg = msg.upper()
        if any(token in upper_msg for token in ["失败", "错误", "FAIL", "ERR"]):
            return QColor("#d32f2f")
        if any(token in upper_msg for token in ["成功", "OK"]):
            return QColor("#2e7d32")
        if any(token in upper_msg for token in ["注销", "停止", "STOPPED"]):
            return QColor("#ef6c00")
        if any(token in upper_msg for token in ["启动", "STARTED", "登录", "LOGIN"]):
            return QColor("#1565c0")
        return QColor("#333333")

    def append_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(self._log_color(msg))
        cursor.insertText(f"[{ts}] {msg}\n", fmt)

        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def toggle_start(self) -> None:
        if self.server_controller.is_running():
            self.server_controller.stop()
            self.spin_port.setEnabled(True)
            self.act_start.setIcon(self.style().standardIcon(self.style().SP_MediaPlay))
            self.append_log("Server stopped")
            return

        port = int(self.spin_port.value())
        try:
            self.server_controller.start(port)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"启动服务失败: {e}")
            return

        self.spin_port.setEnabled(False)
        self.act_start.setIcon(self.style().standardIcon(self.style().SP_MediaStop))
        self.append_log(f"Server started on port {port}")

    def open_user_mgmt(self) -> None:
        dlg = UserManagementDialog(parent=self, db=self.db)
        dlg.exec_()
        self.refresh_unlocked_users()

    def refresh_unlocked_users(self) -> None:
        self.list_users.clear()
        rows = self.db.list_unlocked_users()
        for row in rows:
            avatar_blob = row["avatar"]
            if avatar_blob:
                pm = pixmap_from_avatar_blob(avatar_blob)
            else:
                pm = make_placeholder_avatar(row["username"])
            icon = QIcon(pm)

            item = QListWidgetItem(icon, str(row["username"]))
            item.setTextAlignment(Qt.AlignHCenter)
            item.setData(Qt.UserRole, int(row["id"]))
            self.list_users.addItem(item)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.server_controller.is_running():
            self.server_controller.stop()
        super().closeEvent(event)
