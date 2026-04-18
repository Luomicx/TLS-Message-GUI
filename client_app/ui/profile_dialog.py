from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon as FIF, InfoBar, LineEdit

from .theme import (
    apply_app_style,
    make_header_block,
    make_labeled_input,
    make_link_action,
    make_logo_badge,
    make_primary_action,
    make_section_card,
)


class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("个人资料")
        self.resize(660, 760)
        self.setMinimumSize(620, 700)
        self._build_ui()
        apply_app_style(self)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(14)

        header = QWidget(self)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        header_layout.addWidget(make_logo_badge(72), 0, Qt.AlignHCenter)
        header_layout.addWidget(
            make_header_block(
                "个人资料设置",
                "",
            )
        )
        root.addWidget(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")

        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 6, 0)
        content_layout.setSpacing(14)

        profile_card = make_section_card()
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(22, 22, 22, 22)
        profile_layout.setSpacing(14)

        profile_title = BodyLabel(profile_card)
        profile_title.setText("基础资料")
        self.edit_account = LineEdit(profile_card)
        self.edit_account.setReadOnly(True)
        self.edit_account.setPlaceholderText("当前登录账号")
        self.edit_account.setMinimumHeight(46)

        account_row = QWidget(profile_card)
        account_layout = QVBoxLayout(account_row)
        account_layout.setContentsMargins(0, 0, 0, 0)
        account_layout.setSpacing(8)
        account_label = CaptionLabel(account_row)
        account_label.setText("账号")
        account_layout.addWidget(account_label)
        account_layout.addWidget(self.edit_account)

        nickname_row, self.edit_nickname = make_labeled_input(
            "昵称", "请输入新的显示昵称"
        )

        profile_layout.addWidget(profile_title)
        profile_layout.addWidget(account_row)
        profile_layout.addWidget(nickname_row)

        password_card = make_section_card()
        password_layout = QVBoxLayout(password_card)
        password_layout.setContentsMargins(22, 22, 22, 22)
        password_layout.setSpacing(14)

        password_title = BodyLabel(password_card)
        password_title.setText("密码修改")
        current_password_row, self.edit_current_password = make_labeled_input(
            "当前密码", "如需改密请输入当前密码", password=True
        )
        new_password_row, self.edit_new_password = make_labeled_input(
            "新密码", "请输入新密码", password=True
        )
        confirm_password_row, self.edit_confirm_password = make_labeled_input(
            "确认新密码", "请再次输入新密码", password=True
        )

        password_layout.addWidget(password_title)
        password_layout.addWidget(current_password_row)
        password_layout.addWidget(new_password_row)
        password_layout.addWidget(confirm_password_row)

        recovery_card = make_section_card()
        recovery_layout = QVBoxLayout(recovery_card)
        recovery_layout.setContentsMargins(22, 22, 22, 22)
        recovery_layout.setSpacing(14)

        recovery_title = BodyLabel(recovery_card)
        recovery_title.setText("找回信息")
        recovery_question_row, self.edit_recovery_question = make_labeled_input(
            "安全问题", "例如：你的小学班主任是谁？"
        )
        recovery_answer_row, self.edit_recovery_answer = make_labeled_input(
            "安全答案", "请输入新的找回答案", password=True
        )

        recovery_layout.addWidget(recovery_title)
        recovery_layout.addWidget(recovery_question_row)
        recovery_layout.addWidget(recovery_answer_row)

        self.label_status = CaptionLabel(content)
        self.label_status.setWordWrap(True)
        self.label_status.setMinimumHeight(24)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(12)

        self.btn_save = make_primary_action("保存设置", FIF.SAVE)
        self.btn_cancel = make_link_action("取消")
        self.btn_save.setFixedHeight(42)
        self.btn_cancel.setFixedHeight(42)
        self.btn_save.clicked.connect(self._submit)
        self.btn_cancel.clicked.connect(self.reject)

        button_layout.addWidget(self.btn_save, 1)
        button_layout.addWidget(self.btn_cancel, 1)

        content_layout.addWidget(profile_card)
        content_layout.addWidget(password_card)
        content_layout.addWidget(recovery_card)
        content_layout.addWidget(self.label_status)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        root.addWidget(button_row)

    def load_profile(
        self,
        *,
        username: str,
        nickname: str,
        recovery_question: str = "",
    ) -> None:
        self.edit_account.setText(username)
        self.edit_nickname.setText(nickname)
        self.edit_recovery_question.setText(recovery_question)

    def _set_status(self, text: str, *, ok: bool) -> None:
        color = "#0F8C4C" if ok else "#C42B1C"
        self.label_status.setStyleSheet(f"color: {color};")
        self.label_status.setText(text)
        if ok:
            InfoBar.success("资料设置", text, parent=self, duration=1600)
        else:
            InfoBar.error("资料设置", text, parent=self, duration=2200)

    def _submit(self) -> None:
        payload = self.payload()
        if not payload["nickname"]:
            self._set_status("昵称不能为空", ok=False)
            return

        has_password_change = any(
            payload[key]
            for key in ("current_password", "new_password", "confirm_password")
        )
        if has_password_change:
            if not payload["current_password"]:
                self._set_status("修改密码时必须填写当前密码", ok=False)
                return
            if not payload["new_password"]:
                self._set_status("请输入新密码", ok=False)
                return
            if payload["new_password"] != payload["confirm_password"]:
                self._set_status("两次输入的新密码不一致", ok=False)
                return

        has_recovery_change = bool(payload["recovery_question"] or payload["recovery_answer"])
        if has_recovery_change:
            if not payload["recovery_question"]:
                self._set_status("请输入安全问题", ok=False)
                return
            if not payload["recovery_answer"]:
                self._set_status("请输入安全答案", ok=False)
                return

        self.accept()

    def payload(self) -> dict[str, str]:
        return {
            "username": self.edit_account.text().strip(),
            "nickname": self.edit_nickname.text().strip(),
            "current_password": self.edit_current_password.text(),
            "new_password": self.edit_new_password.text(),
            "confirm_password": self.edit_confirm_password.text(),
            "recovery_question": self.edit_recovery_question.text().strip(),
            "recovery_answer": self.edit_recovery_answer.text(),
        }
