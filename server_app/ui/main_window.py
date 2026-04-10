from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont, QIcon, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..db import Database, normalize_encoding_rule
from ..network import ServerController
from .avatar import make_placeholder_avatar, pixmap_from_avatar_blob
from .theme import build_admin_stylesheet, repolish, resolve_ui_metrics
from .user_management_dialog import UserManagementDialog


class MainWindow(QMainWindow):
    def __init__(self, *, db: Database):
        super().__init__()
        self.db = db
        self.ui_metrics = resolve_ui_metrics()
        self.server_controller = ServerController(db=db)
        self.server_controller.log_signal.connect(self.append_log)

        self._cached_users: list[dict[str, Any]] = []
        self._stat_value_labels: dict[str, QLabel] = {}
        self._stat_hint_labels: dict[str, QLabel] = {}
        self._detail_value_labels: dict[str, QLabel] = {}

        self.setWindowTitle("安全网络聊天工具 - 服务器控制台")
        self.resize(self.ui_metrics.main_window_size)
        self.setMinimumSize(self.ui_metrics.main_window_min_size)
        self.setStyleSheet(build_admin_stylesheet(self.ui_metrics.scale))

        self._build_central()
        self.statusBar().showMessage("控制台已就绪")

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(3000)
        self.refresh_timer.timeout.connect(self.refresh_dashboard)
        self.refresh_timer.start()

        self._update_server_controls(running=False)
        self.append_log("控制台已初始化，等待服务启动")
        self.refresh_dashboard()

    def _build_central(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(
            self.ui_metrics.root_margin,
            self.ui_metrics.root_margin,
            self.ui_metrics.root_margin,
            self.ui_metrics.root_margin - 6,
        )
        root_layout.setSpacing(self.ui_metrics.section_spacing)

        root_layout.addWidget(self._build_hero_card())
        root_layout.addWidget(self._build_metric_row())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_user_overview_panel())
        splitter.addWidget(self._build_sidebar_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes(
            [
                int(self.ui_metrics.main_window_size.width() * 0.64),
                int(self.ui_metrics.main_window_size.width() * 0.36),
            ]
        )
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)

    def _build_hero_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("heroCard")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
        )
        layout.setSpacing(self.ui_metrics.hero_spacing)

        intro_layout = QVBoxLayout()
        intro_layout.setSpacing(max(8, self.ui_metrics.section_spacing // 2))

        title = QLabel("服务器后台控制台")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "集中查看服务状态、账号概览和运行日志，适合日常运维与教学演示。"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(max(10, self.ui_metrics.section_spacing // 2))
        chip_row.setContentsMargins(0, max(4, self.ui_metrics.section_spacing // 4), 0, 0)
        for text in ("TLS 加密传输", "SQLite 本地数据", "用户后台管理"):
            chip = QLabel(text)
            chip.setObjectName("softChip")
            chip_row.addWidget(chip)
        chip_row.addStretch(1)

        intro_layout.addWidget(title)
        intro_layout.addWidget(subtitle)
        intro_layout.addLayout(chip_row)
        intro_layout.addStretch(1)

        control_layout = QVBoxLayout()
        control_layout.setSpacing(max(12, self.ui_metrics.section_spacing // 2))

        status_row = QHBoxLayout()
        status_row.addStretch(1)
        self.lbl_server_state = QLabel()
        self.lbl_server_state.setObjectName("statusBadge")
        status_row.addWidget(self.lbl_server_state)
        control_layout.addLayout(status_row)

        control_row = QHBoxLayout()
        control_row.setSpacing(max(10, self.ui_metrics.section_spacing // 2))

        port_hint = QLabel("监听端口")
        port_hint.setObjectName("hintText")
        control_row.addWidget(port_hint)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(8000)
        self.spin_port.setAlignment(Qt.AlignCenter)
        self.spin_port.setFixedWidth(self.ui_metrics.port_width)
        control_row.addWidget(self.spin_port)

        self.btn_toggle = QPushButton("启动服务")
        self.btn_toggle.setIcon(self.style().standardIcon(self.style().SP_MediaPlay))
        self.btn_toggle.clicked.connect(self.toggle_start)
        control_row.addWidget(self.btn_toggle)

        self.btn_manage_users = QPushButton("用户管理")
        self.btn_manage_users.setIcon(
            self.style().standardIcon(self.style().SP_FileDialogDetailedView)
        )
        self.btn_manage_users.clicked.connect(self.open_user_mgmt)
        control_row.addWidget(self.btn_manage_users)

        self.btn_refresh = QPushButton("刷新面板")
        self.btn_refresh.setIcon(
            self.style().standardIcon(self.style().SP_BrowserReload)
        )
        self.btn_refresh.clicked.connect(self.refresh_dashboard)
        control_row.addWidget(self.btn_refresh)

        control_layout.addLayout(control_row)
        control_layout.addStretch(1)

        layout.addLayout(intro_layout, 1)
        layout.addLayout(control_layout)
        return card

    def _build_metric_row(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(max(14, self.ui_metrics.section_spacing - 2))

        cards = [
            ("total_users", "注册账号", "数据库中的全部账号", "#1d4ed8"),
            ("online_users", "在线会话", "当前实时在线连接", "#0f766e"),
            ("locked_users", "锁定账号", "连续失败或被禁用账号", "#c2410c"),
            ("message_total", "历史消息", "包含私聊、群聊与文件会话", "#0369a1"),
        ]
        for key, title, hint, accent in cards:
            layout.addWidget(self._create_metric_card(key, title, hint, accent), 1)

        return widget

    def _create_metric_card(
        self, key: str, title_text: str, hint_text: str, accent: str
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(max(8, self.ui_metrics.section_spacing // 2))

        accent_bar = QFrame()
        accent_bar.setFixedSize(
            int(self.ui_metrics.summary_avatar_size * 0.82),
            max(6, int(round(6 * self.ui_metrics.scale))),
        )
        accent_bar.setStyleSheet(
            f"background: {accent}; border: none; border-radius: 3px;"
        )

        title = QLabel(title_text)
        title.setObjectName("metricTitle")

        value = QLabel("--")
        value.setObjectName("metricValue")

        hint = QLabel(hint_text)
        hint.setObjectName("metricHint")
        hint.setWordWrap(True)

        layout.addWidget(accent_bar, 0, Qt.AlignLeft)
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(hint)
        layout.addStretch(1)

        self._stat_value_labels[key] = value
        self._stat_hint_labels[key] = hint
        return card

    def _build_user_overview_panel(self) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(self.ui_metrics.section_spacing)

        header_row = QHBoxLayout()
        header_row.setSpacing(max(12, self.ui_metrics.section_spacing // 2))

        title_layout = QVBoxLayout()
        title_layout.setSpacing(max(4, self.ui_metrics.section_spacing // 4))
        title = QLabel("账号总览")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("统一查看账号状态、编码策略与最近活跃时间")
        subtitle.setObjectName("sectionSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_row.addLayout(title_layout, 1)

        header_actions = QHBoxLayout()
        header_actions.setSpacing(max(10, self.ui_metrics.section_spacing // 2))
        self.edit_user_search = QLineEdit()
        self.edit_user_search.setPlaceholderText("搜索用户名、昵称或用户 ID")
        self.edit_user_search.setClearButtonEnabled(True)
        self.edit_user_search.textChanged.connect(self._apply_user_filter)
        self.edit_user_search.setFixedWidth(self.ui_metrics.search_width)
        header_actions.addWidget(self.edit_user_search)

        self.lbl_user_summary = QLabel("等待加载")
        self.lbl_user_summary.setObjectName("summaryBadge")
        header_actions.addWidget(self.lbl_user_summary)
        header_row.addLayout(header_actions)
        layout.addLayout(header_row)

        self.table_users = QTableWidget(0, 5)
        self.table_users.setHorizontalHeaderLabels(
            ["用户", "昵称", "状态", "编码规则", "最近活跃"]
        )
        self.table_users.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_users.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_users.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_users.setAlternatingRowColors(True)
        self.table_users.setShowGrid(False)
        self.table_users.setIconSize(
            QSize(
                self.ui_metrics.summary_avatar_size,
                self.ui_metrics.summary_avatar_size,
            )
        )
        self.table_users.verticalHeader().setVisible(False)
        self.table_users.verticalHeader().setDefaultSectionSize(
            self.ui_metrics.summary_table_row_height
        )
        self.table_users.horizontalHeader().setHighlightSections(False)
        self.table_users.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_users.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.table_users.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.table_users.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.table_users.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        self.table_users.itemDoubleClicked.connect(self.open_user_mgmt)
        layout.addWidget(self.table_users, 1)

        hint = QLabel("支持快速检索，双击任意账号可进入完整用户管理窗口。")
        hint.setObjectName("hintText")
        layout.addWidget(hint)
        return card

    def _build_sidebar_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.ui_metrics.section_spacing)

        layout.addWidget(self._build_service_detail_card())
        layout.addWidget(self._build_log_card(), 1)
        return widget

    def _build_service_detail_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(self.ui_metrics.section_spacing)

        title = QLabel("服务概览")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("聚合运行状态、数据库信息和内容规模")
        subtitle.setObjectName("sectionSubtitle")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(max(18, self.ui_metrics.section_spacing))
        form.setVerticalSpacing(max(12, self.ui_metrics.section_spacing // 2))

        detail_rows = [
            ("service_state", "运行状态"),
            ("host", "监听地址"),
            ("port", "监听端口"),
            ("tls", "传输安全"),
            ("group_total", "群聊数量"),
            ("file_total", "文件消息"),
            ("database", "数据库"),
            ("last_refresh", "最近刷新"),
        ]
        for key, text in detail_rows:
            label = QLabel(text)
            label.setObjectName("detailKey")
            value = QLabel("--")
            value.setObjectName("detailValue")
            value.setWordWrap(True)
            form.addRow(label, value)
            self._detail_value_labels[key] = value

        tip = QLabel(
            "管理建议：账号改动建议通过“用户管理”执行，日志面板适合观察登录、注销和消息流转。"
        )
        tip.setObjectName("hintText")
        tip.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addWidget(tip)
        return card

    def _build_log_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(self.ui_metrics.section_spacing)

        header_row = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_layout.setSpacing(max(4, self.ui_metrics.section_spacing // 4))

        title = QLabel("运行日志")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("显示服务启动、认证、消息发送等事件")
        subtitle.setObjectName("sectionSubtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_row.addLayout(title_layout, 1)

        btn_clear = QPushButton("清空日志")
        btn_clear.setIcon(
            self.style().standardIcon(self.style().SP_DialogResetButton)
        )
        btn_clear.clicked.connect(self.clear_logs)
        header_row.addWidget(btn_clear)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setAcceptRichText(False)
        self.log.document().setMaximumBlockCount(500)

        layout.addLayout(header_row)
        layout.addWidget(self.log, 1)
        return card

    def _log_color(self, msg: str) -> QColor:
        upper_msg = msg.upper()
        if any(token in upper_msg for token in ["失败", "错误", "FAIL", "ERR"]):
            return QColor("#c2410c")
        if any(token in upper_msg for token in ["成功", "OK"]):
            return QColor("#15803d")
        if any(token in upper_msg for token in ["注销", "停止", "STOPPED"]):
            return QColor("#b45309")
        if any(token in upper_msg for token in ["启动", "STARTED", "登录", "LOGIN"]):
            return QColor("#1d4ed8")
        return QColor("#334155")

    def append_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(self._log_color(msg))
        cursor.insertText(f"[{ts}] {msg}\n", fmt)

        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()
        self.statusBar().showMessage(msg, 5000)

    def _update_server_controls(self, *, running: bool) -> None:
        self.spin_port.setEnabled(not running)

        if running:
            self.lbl_server_state.setText("服务运行中")
            self.lbl_server_state.setProperty("state", "running")
            self.btn_toggle.setText("停止服务")
            self.btn_toggle.setIcon(
                self.style().standardIcon(self.style().SP_MediaStop)
            )
            self.btn_toggle.setProperty("role", "danger")
        else:
            self.lbl_server_state.setText("服务已停止")
            self.lbl_server_state.setProperty("state", "stopped")
            self.btn_toggle.setText("启动服务")
            self.btn_toggle.setIcon(
                self.style().standardIcon(self.style().SP_MediaPlay)
            )
            self.btn_toggle.setProperty("role", "primary")

        repolish(self.lbl_server_state)
        repolish(self.btn_toggle)

    def _set_metric(self, key: str, value: str, hint: str | None = None) -> None:
        label = self._stat_value_labels[key]
        label.setText(value)
        if hint is not None:
            self._stat_hint_labels[key].setText(hint)

    def _set_detail(self, key: str, value: str) -> None:
        self._detail_value_labels[key].setText(value)

    def refresh_dashboard(self) -> None:
        rows = self.db.list_users()
        metrics = self.db.get_dashboard_metrics()
        online_usernames = set(self.server_controller.online_usernames())

        mapped_users: list[dict[str, Any]] = []
        for row in rows:
            username = str(row["username"])
            nickname = str(row["nickname"] or "").strip() or username
            encoding_items = normalize_encoding_rule(str(row["encoding_rule"]))
            encoding_text = " / ".join(encoding_items) if encoding_items else "未配置"
            is_locked = int(row["locked"]) != 0
            is_online = username in online_usernames
            last_seen_raw = str(row["last_seen_at"] or "").strip()
            last_seen = last_seen_raw or ("当前在线" if is_online else "暂无记录")

            avatar_blob = row["avatar"]
            if avatar_blob:
                icon = QIcon(
                    pixmap_from_avatar_blob(
                        bytes(avatar_blob), size=self.ui_metrics.summary_avatar_size
                    )
                )
            else:
                icon = QIcon(
                    make_placeholder_avatar(
                        username, size=self.ui_metrics.summary_avatar_size
                    )
                )

            if is_locked:
                status_text = "已锁定"
                status_color = QColor("#b45309")
                status_order = 2
            elif is_online:
                status_text = "在线"
                status_color = QColor("#15803d")
                status_order = 0
            else:
                status_text = "离线"
                status_color = QColor("#64748b")
                status_order = 1

            mapped_users.append(
                {
                    "id": int(row["id"]),
                    "icon": icon,
                    "username": username,
                    "nickname": nickname,
                    "status": status_text,
                    "status_color": status_color,
                    "status_order": status_order,
                    "encoding": encoding_text,
                    "last_seen": last_seen,
                    "created_at": str(row["created_at"]),
                }
            )

        mapped_users.sort(
            key=lambda item: (int(item["status_order"]), str(item["username"]).lower())
        )
        self._cached_users = mapped_users
        self._apply_user_filter()

        total_users = metrics["total_users"]
        locked_users = metrics["locked_users"]
        online_users = len(online_usernames)
        unlocked_users = max(total_users - locked_users, 0)

        self._set_metric("total_users", str(total_users), f"可用账号 {unlocked_users} 个")
        if total_users > 0:
            online_hint = f"在线率 {online_users / total_users:.0%}"
        else:
            online_hint = "暂无在线连接"
        self._set_metric("online_users", str(online_users), online_hint)
        self._set_metric("locked_users", str(locked_users), "建议定期人工复核")
        self._set_metric(
            "message_total",
            str(metrics["message_total"]),
            f"群聊 {metrics['group_total']} / 文件 {metrics['file_total']}",
        )

        running = self.server_controller.is_running()
        listening_port = self.server_controller.listening_port()
        self._set_detail("service_state", "运行中" if running else "未启动")
        self._set_detail("host", self.server_controller.host)
        self._set_detail(
            "port",
            str(listening_port) if listening_port is not None else f"待启动（默认 {self.spin_port.value()}）",
        )
        self._set_detail("tls", "TLS 已启用" if running else "服务启动后启用 TLS")
        self._set_detail("group_total", str(metrics["group_total"]))
        self._set_detail("file_total", str(metrics["file_total"]))
        self._set_detail("database", str(self.db.path.name))
        self._set_detail("last_refresh", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self._update_server_controls(running=running)

    def _apply_user_filter(self) -> None:
        query = self.edit_user_search.text().strip().lower()
        if not query:
            filtered = list(self._cached_users)
        else:
            filtered = [
                item
                for item in self._cached_users
                if query in str(item["username"]).lower()
                or query in str(item["nickname"]).lower()
                or query in str(item["id"])
            ]

        self.table_users.setRowCount(len(filtered))
        bold_font = QFont()
        bold_font.setBold(True)

        for row_index, item in enumerate(filtered):
            user_item = QTableWidgetItem(item["icon"], str(item["username"]))
            user_item.setFont(bold_font)
            user_item.setData(Qt.UserRole, int(item["id"]))
            user_item.setToolTip(
                f"用户 ID: {item['id']}\n创建时间: {item['created_at']}"
            )
            self.table_users.setItem(row_index, 0, user_item)

            nickname_text = str(item["nickname"])
            nickname_item = QTableWidgetItem(
                nickname_text if nickname_text != str(item["username"]) else "未单独设置"
            )
            self.table_users.setItem(row_index, 1, nickname_item)

            status_item = QTableWidgetItem(str(item["status"]))
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QBrush(item["status_color"]))
            self.table_users.setItem(row_index, 2, status_item)

            encoding_item = QTableWidgetItem(str(item["encoding"]))
            encoding_item.setTextAlignment(Qt.AlignCenter)
            self.table_users.setItem(row_index, 3, encoding_item)

            last_seen_item = QTableWidgetItem(str(item["last_seen"]))
            last_seen_item.setTextAlignment(Qt.AlignCenter)
            self.table_users.setItem(row_index, 4, last_seen_item)

        self.lbl_user_summary.setText(
            f"展示 {len(filtered)} / {len(self._cached_users)} 个账号"
        )

    def toggle_start(self) -> None:
        if self.server_controller.is_running():
            self.server_controller.stop()
            self.append_log("服务已停止")
            self.refresh_dashboard()
            return

        port = int(self.spin_port.value())
        try:
            self.server_controller.start(port)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"启动服务失败: {exc}")
            return

        self.append_log(f"服务已启动，监听端口 {port}")
        self.refresh_dashboard()

    def open_user_mgmt(self, *_args: object) -> None:
        dialog = UserManagementDialog(parent=self, db=self.db)
        dialog.exec_()
        self.refresh_dashboard()

    def clear_logs(self) -> None:
        self.log.clear()
        self.statusBar().showMessage("日志已清空", 3000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.refresh_timer.stop()
        if self.server_controller.is_running():
            self.server_controller.stop()
        super().closeEvent(event)
