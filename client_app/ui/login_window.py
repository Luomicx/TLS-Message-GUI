from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .register_dialog import RegisterDialog
from .theme import apply_app_style, make_header_block, make_labeled_input, make_logo_badge


class LoginWindow(QMainWindow):
    login_requested = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全网络聊天工具 - 客户端登录")
        self.resize(980, 680)
        apply_app_style(self)
        self._build_ui()

    def _build_ui(self) -> None:
        page = QFrame()
        page.setObjectName("page")
        self.setCentralWidget(page)

        root = QHBoxLayout(page)
        root.setContentsMargins(48, 36, 48, 36)
        root.setSpacing(32)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(28, 28, 28, 28)
        left_layout.setSpacing(18)

        left_layout.addWidget(make_logo_badge(), 0, Qt.AlignLeft)

        brand_title = QLabel("Secure IM")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel(
            "仿微信风格的桌面聊天客户端。当前阶段先完成静态 UI，后续接入登录、聊天与安全通信。"
        )
        brand_subtitle.setObjectName("brandSubtitle")
        brand_subtitle.setWordWrap(True)

        left_layout.addWidget(brand_title)
        left_layout.addWidget(brand_subtitle)

        hint_card = QFrame()
        hint_card.setObjectName("card")
        hint_layout = QVBoxLayout(hint_card)
        hint_layout.setContentsMargins(24, 24, 24, 24)
        hint_layout.setSpacing(12)
        hint_layout.addWidget(make_header_block("当前设计目标", "先写登录、注册和主聊天窗口，图标与安全状态全部预留。"))

        for text in [
            "支持输入账号 Id 和密码登录",
            "登录失败时展示错误原因区域",
            "支持跳转注册对话框",
            "为后续 TLS / JSON 协议升级预留状态位",
        ]:
            label = QLabel(f"• {text}")
            label.setObjectName("mutedLabel")
            hint_layout.addWidget(label)

        left_layout.addWidget(hint_card)
        left_layout.addStretch(1)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(18)

        card_layout.addWidget(make_header_block("欢迎登录", "请输入账号 Id 和密码，连接到服务端后进入聊天主界面。"))

        account_box, self.edit_account = make_labeled_input("账号 Id", "请输入账号 Id")
        password_box, self.edit_password = make_labeled_input(
            "密码", "请输入密码", password=True
        )
        card_layout.addWidget(account_box)
        card_layout.addWidget(password_box)

        options_row = QHBoxLayout()
        self.chk_remember = QCheckBox("记住账号")
        status_hint = QLabel("连接状态：未连接")
        status_hint.setObjectName("mutedLabel")
        options_row.addWidget(self.chk_remember)
        options_row.addStretch(1)
        options_row.addWidget(status_hint)
        card_layout.addLayout(options_row)

        self.label_status = QLabel("")
        self.label_status.setObjectName("statusLabel")
        self.label_status.setWordWrap(True)
        card_layout.addWidget(self.label_status)

        self.btn_login = QPushButton("登录")
        self.btn_login.setObjectName("primaryButton")
        self.btn_login.clicked.connect(self._emit_login)
        card_layout.addWidget(self.btn_login)

        self.btn_register = QPushButton("注册新账号")
        self.btn_register.setObjectName("ghostButton")
        self.btn_register.clicked.connect(self.open_register_dialog)
        card_layout.addWidget(self.btn_register)

        self.btn_more = QPushButton("更多登录方式与图标后续补充")
        self.btn_more.setObjectName("textButton")
        card_layout.addWidget(self.btn_more, 0, Qt.AlignLeft)

        root.addWidget(left_panel, 1)
        root.addWidget(card, 0, Qt.AlignVCenter)

    def _emit_login(self) -> None:
        account = self.edit_account.text().strip()
        password = self.edit_password.text()

        if not account:
            self.set_status("请输入账号 Id")
            return
        if not password:
            self.set_status("请输入密码")
            return

        self.set_status("登录请求已就绪，后续接入服务端协议")
        self.login_requested.emit(account, password)

    def set_status(self, message: str, *, ok: bool = False) -> None:
        color = "#07c160" if ok else "#d14b4b"
        self.label_status.setStyleSheet(f"color: {color};")
        self.label_status.setText(message)

    def open_register_dialog(self) -> None:
        dialog = RegisterDialog(self)
        if dialog.exec_() == dialog.Accepted:
            payload = dialog.payload()
            self.edit_account.setText(payload["nickname"])
            self.set_status("注册表单已完成，可继续登录", ok=True)
