from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel

from .theme import (
    apply_app_style,
    make_checkbox,
    make_header_block,
    make_labeled_input,
    make_logo_badge,
    make_primary_action,
    make_secondary_action,
    make_section_card,
)


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("注册账号")
        self.resize(560, 620)
        self.setMinimumSize(520, 580)
        apply_app_style(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 26)
        root.setSpacing(16)

        header = QWidget(self)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        header_layout.addWidget(make_logo_badge(72), 0, Qt.AlignHCenter)
        header_layout.addWidget(
            make_header_block(
                "创建新账号",
                "",
            )
        )

        root.addWidget(header)

        card = make_section_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        nickname_box, self.edit_nickname = make_labeled_input("用户名", "请输入账号 Id")
        password_box, self.edit_password = make_labeled_input(
            "密码", "请输入密码", password=True
        )
        confirm_box, self.edit_confirm = make_labeled_input(
            "确认密码", "请再次输入密码", password=True
        )
        question_box, self.edit_question = make_labeled_input(
            "安全问题", "请输入用于找回密码的安全问题"
        )
        answer_box, self.edit_answer = make_labeled_input(
            "安全答案", "请输入安全答案", password=True
        )
        card_layout.addWidget(nickname_box)
        card_layout.addWidget(password_box)
        card_layout.addWidget(confirm_box)
        card_layout.addWidget(question_box)
        card_layout.addWidget(answer_box)

        self.chk_agree = make_checkbox("我已阅读并同意安全聊天使用约定")
        card_layout.addWidget(self.chk_agree)

        self.label_result = CaptionLabel(card)
        self.label_result.setWordWrap(True)
        self.label_result.setMinimumHeight(22)
        card_layout.addWidget(self.label_result)

        button_row = QWidget(card)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 4, 0, 0)
        button_layout.setSpacing(10)

        self.btn_submit = make_primary_action("注册")
        self.btn_cancel = make_secondary_action("返回登录")
        self.btn_submit.setFixedHeight(42)
        self.btn_cancel.setFixedHeight(42)
        self.btn_submit.clicked.connect(self._on_submit)
        self.btn_cancel.clicked.connect(self.reject)

        button_layout.addWidget(self.btn_submit, 1)
        button_layout.addWidget(self.btn_cancel, 1)
        card_layout.addWidget(button_row)

        root.addWidget(card, 1)

    def _on_submit(self) -> None:
        nickname = self.edit_nickname.text().strip()
        password = self.edit_password.text()
        confirm = self.edit_confirm.text()
        question = self.edit_question.text().strip()
        answer = self.edit_answer.text()

        if not nickname:
            self._set_result("用户名不能为空", ok=False)
            return
        if not password:
            self._set_result("密码不能为空", ok=False)
            return
        if password != confirm:
            self._set_result("两次输入的密码不一致", ok=False)
            return
        if not question:
            self._set_result("安全问题不能为空", ok=False)
            return
        if not answer.strip():
            self._set_result("安全答案不能为空", ok=False)
            return
        if not self.chk_agree.isChecked():
            self._set_result("请先勾选使用约定", ok=False)
            return

        self._set_result("本地校验通过，正在提交注册", ok=True)
        self.accept()

    def _set_result(self, text: str, *, ok: bool) -> None:
        color = "#0F8C4C" if ok else "#C42B1C"
        self.label_result.setStyleSheet(f"color: {color};")
        self.label_result.setText(text)

    def payload(self) -> dict[str, str]:
        return {
            "nickname": self.edit_nickname.text().strip(),
            "password": self.edit_password.text(),
            "question": self.edit_question.text().strip(),
            "answer": self.edit_answer.text(),
        }
