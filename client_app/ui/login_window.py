from __future__ import annotations

from collections.abc import Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import BodyLabel, CaptionLabel, InfoBar

from .register_dialog import RegisterDialog
from .theme import (
    apply_app_style,
    make_checkbox,
    make_header_block,
    make_labeled_input,
    make_link_action,
    make_logo_badge,
    make_primary_action,
    make_section_card,
)


class RecoverPasswordDialog(QDialog):
    def __init__(
        self,
        parent=None,
        question_loader: Callable[[str], dict] | None = None,
    ):
        super().__init__(parent)
        self.question_loader = question_loader
        self.setWindowTitle("找回密码")
        self.resize(460, 500)
        self.setMinimumWidth(420)
        apply_app_style(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        root.addWidget(
            make_header_block(
                "重置登录密码",
                "请输入账号、找回问题、找回答案和新密码。该流程会调用服务端的密码找回接口。",
            )
        )

        card = make_section_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        account_box, self.edit_account = make_labeled_input("账号", "请输入账号")

        question_box = QWidget(card)
        question_layout = QVBoxLayout(question_box)
        question_layout.setContentsMargins(0, 0, 0, 0)
        question_layout.setSpacing(8)

        question_label = CaptionLabel(question_box)
        question_label.setText("安全问题")

        self.combo_question = QComboBox(question_box)
        self.combo_question.setEnabled(False)
        self.combo_question.addItem("请先输入账号并加载安全问题", "")

        self.btn_load_question = make_link_action("加载安全问题")
        self.btn_load_question.clicked.connect(self._load_questions)

        question_layout.addWidget(question_label)
        question_layout.addWidget(self.combo_question)
        question_layout.addWidget(self.btn_load_question, 0, Qt.AlignLeft)

        answer_box, self.edit_answer = make_labeled_input(
            "找回答案", "请输入找回答案", password=True
        )
        new_password_box, self.edit_new_password = make_labeled_input(
            "新密码", "请输入新密码", password=True
        )

        self.edit_account.editingFinished.connect(self._load_questions)

        card_layout.addWidget(account_box)
        card_layout.addWidget(question_box)
        card_layout.addWidget(answer_box)
        card_layout.addWidget(new_password_box)

        self.label_result = CaptionLabel(card)
        self.label_result.setWordWrap(True)
        self.label_result.setStyleSheet("color:#666666; font-size:12px;")
        card_layout.addWidget(self.label_result)

        button_row = QWidget(card)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 4, 0, 0)
        button_layout.setSpacing(10)

        self.btn_submit = make_primary_action("立即重置")
        self.btn_cancel = make_link_action("取消")
        self.btn_submit.clicked.connect(self._on_submit)
        self.btn_cancel.clicked.connect(self.reject)

        button_layout.addWidget(self.btn_submit, 1)
        button_layout.addWidget(self.btn_cancel, 1)
        card_layout.addWidget(button_row)

        root.addWidget(card, 1)

    def _load_questions(self) -> None:
        account = self.edit_account.text().strip()
        if not account:
            self._set_result("请先输入账号", ok=False)
            self._reset_question_combo("请先输入账号并加载安全问题")
            return
        if not callable(self.question_loader):
            self._set_result("当前未配置找回问题加载器", ok=False)
            return

        response = self.question_loader(account)
        if not response.get("ok", False):
            self._set_result(str(response.get("message", "找回问题加载失败")), ok=False)
            self._reset_question_combo("未找到可用安全问题")
            return

        questions = [
            str(item).strip()
            for item in list(response.get("data", {}).get("questions") or [])
            if str(item).strip()
        ]
        if not questions:
            self._set_result("该账号未设置安全问题", ok=False)
            self._reset_question_combo("未找到可用安全问题")
            return

        self.combo_question.clear()
        for question in questions:
            self.combo_question.addItem(question, question)
        self.combo_question.setEnabled(True)
        self._set_result("已加载该账号的安全问题", ok=True)

    def _reset_question_combo(self, placeholder: str) -> None:
        self.combo_question.clear()
        self.combo_question.addItem(placeholder, "")
        self.combo_question.setEnabled(False)

    def _on_submit(self) -> None:
        if not self.payload()["account"]:
            self._set_result("账号不能为空", ok=False)
            return
        if not self.payload()["question"]:
            self._set_result("找回问题不能为空", ok=False)
            return
        if not self.payload()["answer"]:
            self._set_result("找回答案不能为空", ok=False)
            return
        if not self.payload()["new_password"]:
            self._set_result("新密码不能为空", ok=False)
            return
        self.accept()

    def _set_result(self, text: str, *, ok: bool) -> None:
        color = "#0F8C4C" if ok else "#C42B1C"
        self.label_result.setStyleSheet(f"color: {color}; font-size:12px;")
        self.label_result.setText(text)

    def payload(self) -> dict[str, str]:
        return {
            "account": self.edit_account.text().strip(),
            "question": str(self.combo_question.currentData() or "").strip(),
            "answer": self.edit_answer.text(),
            "new_password": self.edit_new_password.text(),
        }


class LoginWindow(QMainWindow):
    login_requested = pyqtSignal(str, str)
    recover_password_requested = pyqtSignal(str, str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全网络聊天工具 - 客户端登录")
        self.resize(520, 620)
        self.setMinimumSize(460, 560)

        self.register_submitter: Callable[[str, str, str, str], dict] | None = None
        self.recovery_question_loader: Callable[[str], dict] | None = None

        apply_app_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)

        root = QVBoxLayout(page)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(0)

        shell = QWidget(page)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        auth_card = make_section_card()
        auth_card.setFixedWidth(410)
        auth_card.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        card_outer = QVBoxLayout(auth_card)
        card_outer.setContentsMargins(28, 24, 28, 22)
        card_outer.setSpacing(0)

        # 顶部品牌区：保留 logo，但整体更收紧，更像现代桌面应用
        brand_box = QWidget(auth_card)
        brand_layout = QVBoxLayout(brand_box)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(6)

        logo_badge = make_logo_badge()
        brand_layout.addWidget(logo_badge, 0, Qt.AlignHCenter)

        brand_title = BodyLabel("Secure IM", brand_box)
        brand_title.setAlignment(Qt.AlignCenter)
        brand_title.setStyleSheet(
            "font-size: 24px; font-weight: 800; letter-spacing: 0.5px;"
        )

        brand_subtitle = CaptionLabel("欢迎回来，登录后继续使用安全聊天服务", brand_box)
        brand_subtitle.setAlignment(Qt.AlignCenter)
        brand_subtitle.setWordWrap(True)
        brand_subtitle.setStyleSheet(
            "font-size: 12px; color: #7A7A7A; line-height: 1.5;"
        )

        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_subtitle)

        card_outer.addWidget(brand_box)
        card_outer.addSpacing(16)

        # 表单区
        form_box = QWidget(auth_card)
        form_layout = QVBoxLayout(form_box)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        account_box, self.edit_account = make_labeled_input("账号", "请输入账号")
        password_box, self.edit_password = make_labeled_input(
            "密码", "请输入密码", password=True
        )

        form_layout.addWidget(account_box)
        form_layout.addWidget(password_box)

        # 选项行：记住账号 + 连接状态
        options = QWidget(form_box)
        options_layout = QHBoxLayout(options)
        options_layout.setContentsMargins(0, 2, 0, 0)
        options_layout.setSpacing(8)

        self.chk_remember = make_checkbox("记住账号")

        status_wrap = QWidget(options)
        status_wrap_layout = QHBoxLayout(status_wrap)
        status_wrap_layout.setContentsMargins(0, 0, 0, 0)
        status_wrap_layout.setSpacing(6)
        status_wrap_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        connect_dot = CaptionLabel("●", status_wrap)
        connect_dot.setStyleSheet("color:#9AA0A6; font-size:11px;")

        self.label_connect = CaptionLabel(status_wrap)
        self.label_connect.setText("待连接")
        self.label_connect.setStyleSheet("color:#7D7D7D; font-size:12px;")

        status_wrap_layout.addWidget(connect_dot)
        status_wrap_layout.addWidget(self.label_connect)

        options_layout.addWidget(self.chk_remember, 0, Qt.AlignLeft)
        options_layout.addStretch(1)
        options_layout.addWidget(status_wrap, 0, Qt.AlignRight)

        form_layout.addWidget(options)

        # 状态区：固定最小高度，避免提示出现时界面跳动
        self.label_status = CaptionLabel(form_box)
        self.label_status.setWordWrap(True)
        self.label_status.setAlignment(Qt.AlignCenter)
        self.label_status.setMinimumHeight(22)
        self.label_status.setStyleSheet("color:#888888; font-size:12px;")
        form_layout.addWidget(self.label_status)

        self.label_attempt_warning = BodyLabel(form_box)
        self.label_attempt_warning.setWordWrap(True)
        self.label_attempt_warning.setAlignment(Qt.AlignCenter)
        self.label_attempt_warning.hide()
        form_layout.addWidget(self.label_attempt_warning)

        card_outer.addWidget(form_box)
        card_outer.addSpacing(14)

        # 主操作按钮
        self.btn_login = make_primary_action("登 录")
        self.btn_login.setFixedHeight(40)
        self.btn_login.clicked.connect(self._emit_login)
        card_outer.addWidget(self.btn_login)

        # 底部辅助链接
        links_widget = QWidget(auth_card)
        links_layout = QHBoxLayout(links_widget)
        links_layout.setContentsMargins(0, 8, 0, 0)
        links_layout.setSpacing(8)

        self.btn_register = make_link_action("注册新账号")
        self.btn_register.clicked.connect(self.open_register_dialog)

        self.btn_recover = make_link_action("忘记密码")
        self.btn_recover.clicked.connect(self.open_recover_dialog)

        links_layout.addWidget(self.btn_register, 0, Qt.AlignLeft)
        links_layout.addStretch(1)
        links_layout.addWidget(self.btn_recover, 0, Qt.AlignRight)

        card_outer.addWidget(links_widget)

        shell_layout.addWidget(auth_card, 0, Qt.AlignCenter)
        root.addWidget(shell, 1, Qt.AlignCenter)

    def _emit_login(self) -> None:
        account = self.edit_account.text().strip()
        password = self.edit_password.text()
        self.set_attempt_warning(None)

        if not account:
            self.set_status("请输入账号")
            return
        if not password:
            self.set_status("请输入密码")
            return

        self.set_status("正在提交登录请求...")
        self.login_requested.emit(account, password)

    def set_status(self, message: str, *, ok: bool = False) -> None:
        color = "#0F8C4C" if ok else "#C42B1C"
        weight = 500 if ok else 600
        self.label_status.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: {weight};"
        )
        self.label_status.setText(message)

        if message.startswith("正在"):
            InfoBar.info("状态", message, parent=self, duration=1200)
            return
        if ok:
            InfoBar.success("状态", message, parent=self, duration=1800)
        else:
            InfoBar.error("状态", message, parent=self, duration=2200)

    def set_attempt_warning(self, remaining_attempts: int | None) -> None:
        if remaining_attempts is None:
            self.label_attempt_warning.hide()
            self.label_attempt_warning.clear()
            return

        self.label_attempt_warning.setStyleSheet(
            "background-color: #FFF4CE; "
            "color: #8A4600; "
            "border: 1px solid #F1C87A; "
            "border-radius: 10px; "
            "padding: 8px 10px; "
            "font-size: 12px; "
            "font-weight: 700;"
        )
        self.label_attempt_warning.setText(
            f"密码错误。再失败 {remaining_attempts} 次，账号将被锁定。"
        )
        self.label_attempt_warning.show()

    def open_register_dialog(self) -> None:
        dialog = RegisterDialog(self)
        if dialog.exec_() != dialog.Accepted:
            return

        payload = dialog.payload()
        if callable(self.register_submitter):
            response = self.register_submitter(
                payload["nickname"],
                payload["password"],
                payload["question"],
                payload["answer"],
            )
            if response.get("ok", False):
                self.edit_account.setText(payload["nickname"])
                self.set_status(
                    str(response.get("message", "注册成功，可继续登录")), ok=True
                )
            else:
                self.set_status(str(response.get("message", "注册失败")), ok=False)
            return

        self.edit_account.setText(payload["nickname"])
        self.set_status("注册表单已完成，可继续登录", ok=True)

    def open_recover_dialog(self) -> None:
        dialog = RecoverPasswordDialog(
            self,
            question_loader=self.recovery_question_loader,
        )
        if dialog.exec_() != dialog.Accepted:
            return

        payload = dialog.payload()
        self.recover_password_requested.emit(
            payload["account"],
            payload["question"],
            payload["answer"],
            payload["new_password"],
        )
