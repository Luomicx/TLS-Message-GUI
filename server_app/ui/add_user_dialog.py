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
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..db import ALLOWED_ENCODINGS
from .theme import build_admin_stylesheet, repolish, resolve_ui_metrics


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui_metrics = resolve_ui_metrics()
        self.setWindowTitle("新增用户")
        self.resize(self.ui_metrics.add_user_dialog_size)
        self.setMinimumWidth(self.ui_metrics.add_user_dialog_min_width)
        self.setStyleSheet(build_admin_stylesheet(self.ui_metrics.scale))

        self._avatar_bytes: bytes | None = None

        self.edit_username = QLineEdit()
        self.edit_username.setPlaceholderText("请输入登录用户名")

        self.edit_password = QLineEdit()
        self.edit_password.setPlaceholderText("请输入初始密码")
        self.edit_password.setEchoMode(QLineEdit.Password)

        self.chk_locked = QCheckBox("创建后立即锁定账号")

        self.lbl_avatar = QLabel("未选择头像")
        self.lbl_avatar.setFixedSize(
            self.ui_metrics.preview_avatar_size,
            self.ui_metrics.preview_avatar_size,
        )
        self.lbl_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_avatar.setWordWrap(True)
        self.lbl_avatar.setStyleSheet(
            f"background: #f8fbff; border: 1px dashed #c7d5e8; border-radius: {max(18, int(self.ui_metrics.preview_avatar_size * 0.16))}px;"
        )

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        root.setSpacing(self.ui_metrics.section_spacing)

        title = QLabel("新增后台用户")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("填写基础资料后即可创建账号，编码规则支持多选。")
        subtitle.setObjectName("sectionSubtitle")
        subtitle.setWordWrap(True)

        form_card = QFrame()
        form_card.setObjectName("surfaceCard")
        form_layout = QHBoxLayout(form_card)
        form_layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        form_layout.setSpacing(self.ui_metrics.section_spacing)

        left_col = QVBoxLayout()
        left_col.setSpacing(self.ui_metrics.section_spacing)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(max(14, self.ui_metrics.section_spacing // 2))
        form.setVerticalSpacing(max(14, self.ui_metrics.section_spacing // 2))
        form.addRow("用户名", self.edit_username)
        form.addRow("初始密码", self.edit_password)
        form.addRow("", self.chk_locked)
        left_col.addLayout(form)

        hint = QLabel("建议为演示或教学账号设置清晰的用户名，便于后续在后台检索。")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        left_col.addWidget(hint)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(max(12, self.ui_metrics.section_spacing // 2))

        avatar_title = QLabel("头像预览")
        avatar_title.setObjectName("metricTitle")
        right_col.addWidget(avatar_title)
        right_col.addWidget(self.lbl_avatar, 0, Qt.AlignCenter)

        btn_choose = QPushButton("上传头像")
        btn_choose.clicked.connect(self.choose_avatar)
        btn_choose.setProperty("role", "success")
        repolish(btn_choose)
        right_col.addWidget(btn_choose)
        right_col.addStretch(1)

        form_layout.addLayout(left_col, 1)
        form_layout.addLayout(right_col)

        enc_box = QGroupBox("编码规则")
        enc_layout = QHBoxLayout(enc_box)
        enc_layout.setContentsMargins(
            max(14, self.ui_metrics.section_spacing // 2),
            max(20, self.ui_metrics.section_spacing),
            max(14, self.ui_metrics.section_spacing // 2),
            max(14, self.ui_metrics.section_spacing // 2),
        )
        enc_layout.setSpacing(max(16, self.ui_metrics.section_spacing // 2))
        self.enc_checks: dict[str, QCheckBox] = {}
        for token in ["base64", "hex", "caesar"]:
            checkbox = QCheckBox(token)
            self.enc_checks[token] = checkbox
            enc_layout.addWidget(checkbox)
        enc_layout.addStretch(1)

        note = QLabel("未勾选时表示该账号默认不启用内容编码。")
        note.setObjectName("hintText")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        ok_button.setText("创建用户")
        cancel_button.setText("取消")
        ok_button.setProperty("role", "primary")
        repolish(ok_button)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(form_card)
        root.addWidget(enc_box)
        root.addWidget(note)
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
        selected = Path(path)
        try:
            data = selected.read_bytes()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"无法读取文件: {exc}")
            return

        pm = QPixmap()
        if not pm.loadFromData(data):
            QMessageBox.warning(self, "错误", "不是有效的图片文件")
            return

        self._avatar_bytes = data
        self.lbl_avatar.setText("")
        self.lbl_avatar.setPixmap(
            pm.scaled(
                int(self.ui_metrics.preview_avatar_size * 0.82),
                int(self.ui_metrics.preview_avatar_size * 0.82),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
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

        rule = [name for name, checkbox in self.enc_checks.items() if checkbox.isChecked()]
        bad = [token for token in rule if token not in ALLOWED_ENCODINGS]
        if bad:
            QMessageBox.warning(self, "提示", "编码规则选择无效")
            return

        self.accept()

    def payload(self) -> dict:
        username = self.edit_username.text().strip()
        password = self.edit_password.text()
        locked = 1 if self.chk_locked.isChecked() else 0
        encoding_rule = [
            name for name, checkbox in self.enc_checks.items() if checkbox.isChecked()
        ]
        return {
            "username": username,
            "password": password,
            "avatar": self._avatar_bytes,
            "locked": locked,
            "encoding_rule": encoding_rule,
        }
