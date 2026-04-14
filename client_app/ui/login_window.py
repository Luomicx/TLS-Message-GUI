from __future__ import annotations

from collections.abc import Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QMainWindow,
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
        self.resize(460, 480)
        apply_app_style(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(18)

        root.addWidget(
            make_header_block(
                "重置登录密码",
                "请输入账号、找回问题、找回答案和新密码。该流程会调用服务端的密码找回接口。",
            )
        )

        card = make_section_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(16)

        account_box, self.edit_account = make_labeled_input("账号", "请输入账号 Id")
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
        card_layout.addWidget(self.label_result)

        button_row = QWidget(card)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 6, 0, 0)
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
            self._set_result("请先输入账号 Id", ok=False)
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
        self.label_result.setStyleSheet(f"color: {color};")
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
        # 优化点：缩小外层窗口尺寸，适配单栏居中卡片，消除巨大留白
        self.resize(520, 680)
        self.setMinimumSize(480, 620)

        self.register_submitter: Callable[[str, str, str, str], dict] | None = None
        self.recovery_question_loader: Callable[[str], dict] | None = None
        apply_app_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)

        # 根布局：全域居中对齐
        root = QHBoxLayout(page)
        # 适当的外边距，让卡片不要紧贴窗口边缘
        root.setContentsMargins(24, 24, 24, 24)
        root.setAlignment(Qt.AlignCenter)

        # 核心登录卡片设计：去除硬编码的高度限制，让其自适应内容
        auth_card = make_section_card()
        auth_card.setFixedWidth(420)

        auth_layout = QVBoxLayout(auth_card)
        auth_layout.setContentsMargins(36, 48, 36, 42)
        auth_layout.setSpacing(20)

        # ================== 顶部：LOGO 与品牌区 ==================
        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(0)

        # 获取原生 LOGO，不再暴力强制改变其内部大小以防溢出
        logo_badge = make_logo_badge()

        # 安全地将 LOGO 水平居中
        logo_layout.addWidget(logo_badge, 0, Qt.AlignCenter)

        # 强制加入垂直防重叠安全距离
        logo_layout.addSpacing(24)

        # 品牌大标题
        brand_title = BodyLabel("Secure IM", auth_card)
        brand_title.setAlignment(Qt.AlignCenter)
        brand_title.setStyleSheet(
            "font-size: 28px; font-weight: 800; letter-spacing: 1px;"
        )

        welcome_subtitle = CaptionLabel("欢迎回来，请输入您的凭据", auth_card)
        welcome_subtitle.setAlignment(Qt.AlignCenter)
        welcome_subtitle.setStyleSheet("font-size: 14px; color: #777777;")

        logo_layout.addWidget(brand_title)
        logo_layout.addSpacing(8)
        logo_layout.addWidget(welcome_subtitle)

        auth_layout.addLayout(logo_layout)
        auth_layout.addSpacing(16)  # 与表单区域拉开距离

        # ================== 中部：输入表单与状态区 ==================
        account_box, self.edit_account = make_labeled_input("账号 Id", "请输入账号")
        password_box, self.edit_password = make_labeled_input(
            "密码", "请输入密码", password=True
        )
        auth_layout.addWidget(account_box)
        auth_layout.addWidget(password_box)

        # 记住账号与连接状态
        options = QWidget(auth_card)
        options_layout = QHBoxLayout(options)
        options_layout.setContentsMargins(0, 0, 0, 0)
        self.chk_remember = make_checkbox("记住账号")
        self.label_connect = CaptionLabel(options)
        self.label_connect.setText("待连接")
        self.label_connect.setStyleSheet("color: #888888;")
        options_layout.addWidget(self.chk_remember)
        options_layout.addStretch(1)
        options_layout.addWidget(self.label_connect)
        auth_layout.addWidget(options)

        # 动态状态提示
        self.label_status = CaptionLabel(auth_card)
        self.label_status.setWordWrap(True)
        self.label_status.setAlignment(Qt.AlignCenter)
        auth_layout.addWidget(self.label_status)

        self.label_attempt_warning = BodyLabel(auth_card)
        self.label_attempt_warning.setWordWrap(True)
        self.label_attempt_warning.setAlignment(Qt.AlignCenter)
        self.label_attempt_warning.hide()
        auth_layout.addWidget(self.label_attempt_warning)

        # ================== 底部：操作按钮与辅助链接 ==================
        auth_layout.addStretch(1)

        self.btn_login = make_primary_action("登  录")
        self.btn_login.setFixedHeight(42)
        self.btn_login.clicked.connect(self._emit_login)
        auth_layout.addWidget(self.btn_login)

        # 底部链接均分排列
        links_widget = QWidget(auth_card)
        links_layout = QHBoxLayout(links_widget)
        links_layout.setContentsMargins(4, 12, 4, 0)

        self.btn_register = make_link_action("注册新账号")
        self.btn_register.clicked.connect(self.open_register_dialog)

        self.btn_recover = make_link_action("忘记密码")
        self.btn_recover.clicked.connect(self.open_recover_dialog)

        links_layout.addWidget(self.btn_register)
        links_layout.addStretch(1)
        links_layout.addWidget(self.btn_recover)

        auth_layout.addWidget(links_widget)

        root.addWidget(auth_card)

    def _emit_login(self) -> None:
        account = self.edit_account.text().strip()
        password = self.edit_password.text()
        self.set_attempt_warning(None)

        if not account:
            self.set_status("请输入账号 Id")
            return
        if not password:
            self.set_status("请输入密码")
            return

        self.set_status("正在提交登录请求...")
        self.login_requested.emit(account, password)

    def set_status(self, message: str, *, ok: bool = False) -> None:
        color = "#0F8C4C" if ok else "#C42B1C"
        weight = 600 if not ok else 500
        self.label_status.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: {weight};"
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
            "background-color: #FFF4CE; color: #8A4600; "
            "border: 1px solid #F1C87A; border-radius: 10px; "
            "padding: 10px 12px; font-size: 15px; font-weight: 700;"
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
