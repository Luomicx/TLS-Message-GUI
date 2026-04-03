from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .theme import apply_app_style, make_header_block, make_labeled_input


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("注册账号")
        self.resize(420, 460)
        apply_app_style(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)

        root.addWidget(
            make_header_block(
                "创建新账号",
                "请输入昵称和密码。当前阶段先完成界面与本地校验，后续再接入注册协议。",
            )
        )

        nickname_box, self.edit_nickname = make_labeled_input("昵称", "请输入昵称")
        password_box, self.edit_password = make_labeled_input(
            "密码", "请输入密码", password=True
        )
        confirm_box, self.edit_confirm = make_labeled_input(
            "确认密码", "请再次输入密码", password=True
        )

        root.addWidget(nickname_box)
        root.addWidget(password_box)
        root.addWidget(confirm_box)

        self.chk_agree = QCheckBox("我已阅读并同意后续的安全聊天使用约定（占位）")
        root.addWidget(self.chk_agree)

        self.label_result = QLabel("")
        self.label_result.setObjectName("statusLabel")
        self.label_result.setWordWrap(True)
        root.addWidget(self.label_result)

        buttons = QDialogButtonBox()
        self.btn_submit = QPushButton("注册")
        self.btn_submit.setObjectName("primaryButton")
        self.btn_cancel = QPushButton("返回登录")
        self.btn_cancel.setObjectName("ghostButton")

        buttons.addButton(self.btn_submit, QDialogButtonBox.AcceptRole)
        buttons.addButton(self.btn_cancel, QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_submit(self) -> None:
        nickname = self.edit_nickname.text().strip()
        password = self.edit_password.text()
        confirm = self.edit_confirm.text()

        if not nickname:
            self.label_result.setText("昵称不能为空")
            return
        if not password:
            self.label_result.setText("密码不能为空")
            return
        if password != confirm:
            self.label_result.setText("两次输入的密码不一致")
            return
        if not self.chk_agree.isChecked():
            self.label_result.setText("请先勾选使用约定占位项")
            return

        self.label_result.setStyleSheet("color: #07c160;")
        self.label_result.setText("界面校验通过，后续接入服务端注册协议")
        self.accept()

    def payload(self) -> dict[str, str]:
        return {
            "nickname": self.edit_nickname.text().strip(),
            "password": self.edit_password.text(),
        }
