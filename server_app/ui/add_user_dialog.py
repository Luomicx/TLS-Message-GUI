from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..db import ALLOWED_ENCODINGS


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加用户")
        self.resize(420, 240)

        self._avatar_bytes: bytes | None = None

        self.edit_username = QLineEdit()
        self.edit_password = QLineEdit()
        self.edit_password.setEchoMode(QLineEdit.Password)

        self.chk_locked = QCheckBox("锁定")

        self.lbl_avatar = QLabel("(no avatar)")
        self.lbl_avatar.setFixedSize(72, 72)
        self.lbl_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_avatar.setStyleSheet("border: 1px solid #ccc;")

        btn_choose = QPushButton("选择头像...")
        btn_choose.clicked.connect(self.choose_avatar)

        avatar_row = QHBoxLayout()
        avatar_row.addWidget(self.lbl_avatar)
        avatar_row.addWidget(btn_choose, 1)

        enc_box = QGroupBox("编码规则")
        enc_layout = QHBoxLayout(enc_box)
        self.enc_checks: dict[str, QCheckBox] = {}
        for token in ["base64", "hex", "caesar"]:
            cb = QCheckBox(token)
            self.enc_checks[token] = cb
            enc_layout.addWidget(cb)

        form = QFormLayout()
        form.addRow("用户名:", self.edit_username)
        form.addRow("密码:", self.edit_password)
        form.addRow("头像:", avatar_row)
        form.addRow("", self.chk_locked)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(enc_box)
        root.addWidget(buttons)

    def choose_avatar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择头像",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*.*)",
        )
        if not path:
            return
        p = Path(path)
        try:
            data = p.read_bytes()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
            return

        pm = QPixmap()
        if not pm.loadFromData(data):
            QMessageBox.warning(self, "错误", "不是有效的图片文件")
            return

        self._avatar_bytes = data
        self.lbl_avatar.setPixmap(
            pm.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _on_accept(self) -> None:
        username = self.edit_username.text().strip()
        password = self.edit_password.text()

        if not username:
            QMessageBox.warning(self, "提示", "用户名不能为空")
            return
        if not password:
            QMessageBox.warning(self, "提示", "密码不能为空")
            return

        rule = [k for k, cb in self.enc_checks.items() if cb.isChecked()]
        bad = [t for t in rule if t not in ALLOWED_ENCODINGS]
        if bad:
            QMessageBox.warning(self, "提示", "编码规则选择无效")
            return

        self.accept()

    def payload(self) -> dict:
        username = self.edit_username.text().strip()
        password = self.edit_password.text()
        locked = 1 if self.chk_locked.isChecked() else 0
        encoding_rule = [k for k, cb in self.enc_checks.items() if cb.isChecked()]
        return {
            "username": username,
            "password": password,
            "avatar": self._avatar_bytes,
            "locked": locked,
            "encoding_rule": encoding_rule,
        }
