from __future__ import annotations

import html

from PyQt5.QtCore import QRect, Qt, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    InfoBar,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    TextEdit,
)

from .theme import apply_app_style, make_header_block, make_logo_badge, make_section_card


class ChatWindow(QMainWindow):
    DEFAULT_WIDTH = 1500
    DEFAULT_HEIGHT = 940
    MIN_WIDTH = 1180
    MIN_HEIGHT = 760
    SIDEBAR_WIDTH = 380

    logout_requested = pyqtSignal()
    close_requested = pyqtSignal()
    profile_requested = pyqtSignal()
    search_requested = pyqtSignal(str, str)
    add_friend_requested = pyqtSignal(int)
    send_message_requested = pyqtSignal(str, str)
    session_selected = pyqtSignal(str)
    send_file_requested = pyqtSignal(str)
    create_group_requested = pyqtSignal()
    download_root_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全网络聊天工具 - 客户端")
        self._apply_initial_window_geometry()
        self.current_peer: str | None = None
        self._session_payloads: dict[str, dict[str, object]] = {}
        self._search_mode = "fuzzy"
        self._build_ui()
        apply_app_style(self)

    def _apply_initial_window_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT)
            self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
            return

        available = screen.availableGeometry()
        target_width = min(
            max(int(available.width() * 0.72), self.DEFAULT_WIDTH),
            max(self.DEFAULT_WIDTH, available.width() - 96),
        )
        target_height = min(
            max(int(available.height() * 0.8), self.DEFAULT_HEIGHT),
            max(self.DEFAULT_HEIGHT, available.height() - 72),
        )
        min_width = min(target_width, self.MIN_WIDTH)
        min_height = min(target_height, self.MIN_HEIGHT)

        self.resize(target_width, target_height)
        self.setMinimumSize(min_width, min_height)
        self.setGeometry(self._centered_rect(available, target_width, target_height))

    def _centered_rect(
        self, available: QRect, width: int, height: int
    ) -> QRect:
        left = available.left() + max(0, (available.width() - width) // 2)
        top = available.top() + max(0, (available.height() - height) // 2)
        return QRect(left, top, width, height)

    def _build_ui(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)

        root = QHBoxLayout(page)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(18)

        root.addWidget(self._build_sidebar(), 0)
        root.addWidget(self._build_content(), 1)
        self.switch_page(0)
        self._apply_session_summary(None, None)

    def _build_sidebar(self) -> QWidget:
        panel = make_section_card()
        panel.setFixedWidth(self.SIDEBAR_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        top = QWidget(panel)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)
        top_layout.addWidget(make_logo_badge(), 0, Qt.AlignTop)

        meta = QWidget(top)
        meta_layout = QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)
        self.label_current_user = StrongBodyLabel(meta)
        self.label_current_user.setWordWrap(True)
        self.label_current_user.setText("当前用户")
        self.label_current_id = CaptionLabel(meta)
        self.label_current_id.setWordWrap(True)
        self.label_current_id.setText("Id: -")
        self.label_security = CaptionLabel(meta)
        self.label_security.setWordWrap(True)
        self.label_security.setText("安全连接已就绪")
        meta_layout.addWidget(self.label_current_user)
        meta_layout.addWidget(self.label_current_id)
        meta_layout.addWidget(self.label_security)
        top_layout.addWidget(meta, 1)
        layout.addWidget(top)

        nav = QWidget(panel)
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(10)

        self.btn_chat = PushButton(nav)
        self.btn_chat.setText("聊天")
        self.btn_chat.setIcon(FIF.CHAT)
        self.btn_friend = PushButton(nav)
        self.btn_friend.setText("好友")
        self.btn_friend.setIcon(FIF.PEOPLE)
        self.btn_search = PushButton(nav)
        self.btn_search.setText("搜索")
        self.btn_search.setIcon(FIF.SEARCH)

        self.btn_chat.clicked.connect(lambda: self.switch_page(0))
        self.btn_friend.clicked.connect(lambda: self.switch_page(1))
        self.btn_search.clicked.connect(lambda: self.switch_page(2))

        nav_layout.addWidget(self.btn_chat, 1)
        nav_layout.addWidget(self.btn_friend, 1)
        nav_layout.addWidget(self.btn_search, 1)
        layout.addWidget(nav)

        session_header = make_header_block("最近会话", "双击会话进入聊天，支持好友会话和群会话。")
        layout.addWidget(session_header)

        self.list_sessions = ListWidget(panel)
        self.list_sessions.setMinimumHeight(360)
        self.list_sessions.currentItemChanged.connect(self._on_session_changed)
        layout.addWidget(self.list_sessions, 1)

        bottom = QWidget(panel)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        top_actions = QWidget(bottom)
        top_actions_layout = QHBoxLayout(top_actions)
        top_actions_layout.setContentsMargins(0, 0, 0, 0)
        top_actions_layout.setSpacing(8)

        self.btn_create_group_sidebar = PushButton(top_actions)
        self.btn_create_group_sidebar.setText("创建群聊")
        self.btn_create_group_sidebar.setIcon(FIF.ADD)
        self.btn_create_group_sidebar.setMinimumWidth(148)
        self.btn_create_group_sidebar.setMinimumHeight(46)
        self.btn_create_group_sidebar.clicked.connect(self.create_group_requested.emit)

        self.btn_profile = PushButton(top_actions)
        self.btn_profile.setText("个人资料")
        self.btn_profile.setIcon(FIF.EDIT)
        self.btn_profile.setMinimumWidth(132)
        self.btn_profile.setMinimumHeight(46)
        self.btn_profile.clicked.connect(self.profile_requested.emit)

        self.btn_logout = PushButton(bottom)
        self.btn_logout.setText("注销")
        self.btn_logout.setIcon(FIF.SYNC)
        self.btn_logout.setMinimumHeight(46)
        self.btn_logout.clicked.connect(self.logout_requested.emit)

        top_actions_layout.addWidget(self.btn_create_group_sidebar, 1)
        top_actions_layout.addWidget(self.btn_profile, 1)

        bottom_layout.addWidget(top_actions)
        bottom_layout.addWidget(self.btn_logout)
        layout.addWidget(bottom)

        return panel

    def _build_content(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.stacked = QStackedWidget(container)
        self.page_chat = self._build_chat_page()
        self.page_friends = self._build_friends_page()
        self.page_search = self._build_search_page()

        self.stacked.addWidget(self.page_chat)
        self.stacked.addWidget(self.page_friends)
        self.stacked.addWidget(self.page_search)
        layout.addWidget(self.stacked, 1)
        return container

    def _build_chat_page(self) -> QWidget:
        page = make_section_card()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        top = QWidget(page)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        hero = CardWidget(page)
        hero.setObjectName("chatHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 20, 20, 20)
        hero_layout.setSpacing(20)

        title_box = QWidget(hero)
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)
        self.label_peer_badge = CaptionLabel(title_box)
        self.label_peer_badge.setText("未选中会话")
        self.label_peer_title = StrongBodyLabel(title_box)
        self.label_peer_title.setText("请选择会话")
        self.label_peer_subtitle = CaptionLabel(title_box)
        self.label_peer_subtitle.setWordWrap(True)
        self.label_peer_subtitle.setText("支持文本消息、文件消息与群聊消息。")
        self.label_peer_meta = CaptionLabel(title_box)
        self.label_peer_meta.setWordWrap(True)
        self.label_peer_meta.setText("群聊会显示成员信息，私聊会显示连接状态。")
        self.label_download_root = CaptionLabel(title_box)
        self.label_download_root.setWordWrap(True)
        self.label_download_root.setText("接收目录：尚未设置")
        title_layout.addWidget(self.label_peer_badge)
        title_layout.addWidget(self.label_peer_title)
        title_layout.addWidget(self.label_peer_subtitle)
        title_layout.addWidget(self.label_peer_meta)
        title_layout.addWidget(self.label_download_root)
        hero_layout.addWidget(title_box, 1)

        action_box = QWidget(hero)
        action_box.setMinimumWidth(176)
        action_layout = QVBoxLayout(action_box)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.btn_send_file = PushButton(action_box)
        self.btn_send_file.setText("发送文件")
        self.btn_send_file.setIcon(FIF.FOLDER)
        self.btn_send_file.setMinimumWidth(150)
        self.btn_send_file.setMinimumHeight(44)
        self.btn_send_file.clicked.connect(self._emit_send_file)

        self.btn_select_download_root = PushButton(action_box)
        self.btn_select_download_root.setText("接收目录")
        self.btn_select_download_root.setIcon(FIF.DOWNLOAD)
        self.btn_select_download_root.setMinimumWidth(150)
        self.btn_select_download_root.setMinimumHeight(44)
        self.btn_select_download_root.clicked.connect(
            self.download_root_requested.emit
        )

        self.btn_group = PushButton(action_box)
        self.btn_group.setText("创建群聊")
        self.btn_group.setIcon(FIF.PEOPLE)
        self.btn_group.setMinimumWidth(150)
        self.btn_group.setMinimumHeight(44)
        self.btn_group.clicked.connect(self.create_group_requested.emit)

        action_layout.addWidget(self.btn_send_file)
        action_layout.addWidget(self.btn_select_download_root)
        action_layout.addWidget(self.btn_group)
        action_layout.addStretch(1)
        hero_layout.addWidget(action_box, 0)

        top_layout.addWidget(hero, 1)
        layout.addWidget(top)

        self.message_area = TextEdit(page)
        self.message_area.setObjectName("transcriptView")
        self.message_area.setReadOnly(True)
        self.message_area.setPlaceholderText("当前没有消息，请先选择会话。")
        self.message_area.setMinimumHeight(420)
        layout.addWidget(self.message_area, 1)

        composer = CardWidget(page)
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(18, 18, 18, 18)
        composer_layout.setSpacing(12)

        composer_header = QWidget(composer)
        composer_header_layout = QHBoxLayout(composer_header)
        composer_header_layout.setContentsMargins(0, 0, 0, 0)
        composer_header_layout.setSpacing(8)
        composer_hint = CaptionLabel(composer_header)
        composer_hint.setText("发送内容会通过 TLS 通道提交到服务端。")
        composer_header_layout.addWidget(composer_hint)
        self.label_compose_tip = CaptionLabel(composer_header)
        self.label_compose_tip.setText("群聊消息会显示发送者，文件消息会记录保存位置。")
        composer_header_layout.addWidget(self.label_compose_tip)
        composer_header_layout.addStretch(1)
        composer_layout.addWidget(composer_header)

        self.edit_message = TextEdit(composer)
        self.edit_message.setMinimumHeight(170)
        self.edit_message.setMaximumHeight(240)
        self.edit_message.setPlaceholderText("输入消息内容...")
        composer_layout.addWidget(self.edit_message)

        action_row = QWidget(composer)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        self.label_runtime_status = CaptionLabel(action_row)
        self.label_runtime_status.setText("连接状态：在线")
        action_layout.addWidget(self.label_runtime_status)
        action_layout.addStretch(1)
        self.btn_send = PrimaryPushButton(action_row)
        self.btn_send.setText("发送")
        self.btn_send.setIcon(FIF.SEND)
        self.btn_send.clicked.connect(self._emit_send_message)
        action_layout.addWidget(self.btn_send)
        composer_layout.addWidget(action_row)

        layout.addWidget(composer)
        return page

    def _build_friends_page(self) -> QWidget:
        page = make_section_card()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        layout.addWidget(
            make_header_block("好友列表", "双击好友可切换会话，在线状态会随心跳自动刷新。")
        )

        self.list_friends = ListWidget(page)
        self.list_friends.itemDoubleClicked.connect(self._open_friend_session)
        layout.addWidget(self.list_friends, 1)
        return page

    def _build_search_page(self) -> QWidget:
        page = make_section_card()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        layout.addWidget(
            make_header_block("搜索与添加好友", "支持用户名模糊搜索和用户 Id 精准搜索。")
        )

        mode_row = QWidget(page)
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(8)

        self.btn_mode_nickname = PushButton(mode_row)
        self.btn_mode_nickname.setText("昵称搜索")
        self.btn_mode_nickname.setIcon(FIF.SEARCH)
        self.btn_mode_nickname.clicked.connect(lambda: self._set_search_mode("fuzzy"))

        self.btn_mode_id = PushButton(mode_row)
        self.btn_mode_id.setText("Id 搜索")
        self.btn_mode_id.setIcon(FIF.SEARCH)
        self.btn_mode_id.clicked.connect(lambda: self._set_search_mode("id"))

        self.search_input = SearchLineEdit(mode_row)
        self.search_input.setPlaceholderText("输入搜索关键词后回车")
        self.search_input.returnPressed.connect(self._emit_search)

        self.btn_trigger_search = PrimaryPushButton(mode_row)
        self.btn_trigger_search.setText("开始搜索")
        self.btn_trigger_search.setIcon(FIF.SEARCH)
        self.btn_trigger_search.clicked.connect(self._emit_search)

        mode_layout.addWidget(self.btn_mode_nickname)
        mode_layout.addWidget(self.btn_mode_id)
        mode_layout.addWidget(self.search_input, 1)
        mode_layout.addWidget(self.btn_trigger_search)
        layout.addWidget(mode_row)

        self.list_search_result = ListWidget(page)
        self.list_search_result.itemDoubleClicked.connect(self._emit_add_friend_from_result)
        layout.addWidget(self.list_search_result, 1)

        self.label_search_hint = CaptionLabel(page)
        self.label_search_hint.setText("双击搜索结果即可发送添加好友请求。")
        layout.addWidget(self.label_search_hint)

        self._set_search_mode("fuzzy")
        return page

    def switch_page(self, index: int) -> None:
        self.stacked.setCurrentIndex(index)
        pages = [self.btn_chat, self.btn_friend, self.btn_search]
        for i, button in enumerate(pages):
            button.setEnabled(i != index)

    def _on_session_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        raw_peer = current.data(Qt.UserRole)
        if not isinstance(raw_peer, str) or not raw_peer:
            raw_peer = current.text()
        self.current_peer = raw_peer
        payload = dict(self._session_payloads.get(raw_peer) or {"username": raw_peer})
        self._apply_session_summary(raw_peer, payload)
        self.session_selected.emit(raw_peer)
        self.statusBar().showMessage(f"当前会话：{raw_peer}", 4000)

    def _emit_send_message(self) -> None:
        if not self.current_peer:
            self.show_notice("请先选择会话")
            return
        text = self.edit_message.toPlainText().strip()
        if not text:
            self.show_notice("请输入消息内容")
            return
        self.send_message_requested.emit(self.current_peer, text)
        self.edit_message.clear()

    def _emit_send_file(self) -> None:
        if not self.current_peer:
            self.show_notice("请先选择会话")
            return
        self.send_file_requested.emit(self.current_peer)

    def _set_search_mode(self, mode: str) -> None:
        self._search_mode = mode
        self.btn_mode_nickname.setEnabled(mode != "fuzzy")
        self.btn_mode_id.setEnabled(mode != "id")
        hint = "当前按用户名模糊搜索" if mode == "fuzzy" else "当前按用户 Id 精准搜索"
        self.label_search_hint.setText(f"{hint}，双击搜索结果即可发送添加好友请求。")

    def _emit_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.show_notice("请输入搜索内容")
            return
        self.search_requested.emit(self._search_mode, query)

    def _emit_add_friend_from_result(self, item: QListWidgetItem) -> None:
        user_id = item.data(Qt.UserRole)
        if not isinstance(user_id, int):
            return
        self.add_friend_requested.emit(user_id)

    def _open_friend_session(self, item: QListWidgetItem) -> None:
        username = item.data(Qt.UserRole)
        if not isinstance(username, str) or not username:
            return
        for index in range(self.list_sessions.count()):
            session_item = self.list_sessions.item(index)
            if session_item.data(Qt.UserRole) == username:
                self.list_sessions.setCurrentRow(index)
                self.switch_page(0)
                return
        self.upsert_session({"username": username})
        self.list_sessions.setCurrentRow(self.list_sessions.count() - 1)
        self.switch_page(0)

    def reset_view_state(self) -> None:
        self.current_peer = None
        self._session_payloads.clear()
        self.list_sessions.clear()
        self.list_friends.clear()
        self.list_search_result.clear()
        self.search_input.clear()
        self.message_area.clear()
        self._apply_session_summary(None, None)

    def set_current_user(self, user: dict[str, object] | None) -> None:
        if not user:
            return
        username = str(user.get("username") or "")
        nickname = str(user.get("nickname") or username or "当前用户")
        self.label_current_user.setText(nickname)
        self.label_current_id.setText(f"Id/账号: {username}")
        self.label_security.setText("TLS 安全连接已建立")

    def populate_friends(self, friends: list[dict[str, object]]) -> None:
        self.list_friends.clear()
        for item in friends:
            username = str(item.get("username") or "")
            nickname = str(item.get("nickname") or username)
            online = "在线" if bool(item.get("is_online")) else "离线"
            row = QListWidgetItem(f"{nickname}  ·  {online}")
            row.setData(Qt.UserRole, username)
            self.list_friends.addItem(row)

    def populate_sessions(self, sessions: list[dict[str, object]]) -> None:
        current_peer = self.current_peer
        self._session_payloads.clear()
        for item in sessions:
            raw_peer = str(item.get("username") or "")
            if raw_peer:
                self._session_payloads[raw_peer] = dict(item)
        self._rebuild_session_list(selected_peer=current_peer)

    def populate_messages(self, messages: list[dict[str, object]]) -> None:
        html_parts: list[str] = []
        for item in messages:
            html_parts.append(self._render_message_block(item))
        self.message_area.setHtml("".join(html_parts))

    def populate_search_results(self, users: list[dict[str, object]]) -> None:
        self.list_search_result.clear()
        for item in users:
            username = str(item.get("username") or "")
            nickname = str(item.get("nickname") or username)
            user_id = item.get("id")
            online = "在线" if bool(item.get("is_online")) else "离线"
            row = QListWidgetItem(f"{nickname} · Id:{user_id} · {online}")
            row.setData(Qt.UserRole, int(user_id) if user_id is not None else -1)
            self.list_search_result.addItem(row)

    def upsert_session(self, friend: dict[str, object]) -> None:
        raw_peer = str(friend.get("username") or "")
        if not raw_peer:
            return
        merged = dict(self._session_payloads.get(raw_peer) or {})
        merged.update(friend)
        self._session_payloads[raw_peer] = merged
        self._rebuild_session_list(selected_peer=self.current_peer or raw_peer)

    def clear_session_attention(self, raw_peer: str) -> None:
        payload = self._session_payloads.get(raw_peer)
        if payload is None:
            return
        payload["unread_count"] = 0
        payload["has_offline_messages"] = False
        self._rebuild_session_list(selected_peer=self.current_peer or raw_peer)

    def show_notice(self, text: str) -> None:
        self.statusBar().showMessage(text, 4500)
        InfoBar.info("提示", text, parent=self, duration=1500)

    def set_download_root(self, path: str) -> None:
        display_path = self._shorten_path(path)
        self.label_download_root.setText(f"接收目录：{display_path}")
        self.label_download_root.setToolTip(path)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.close_requested.emit()
        super().closeEvent(event)

    def _format_session_label(self, payload: dict[str, object]) -> str:
        raw_peer = str(payload.get("username") or "")
        unread_count = self._unread_count(payload)
        has_offline_messages = bool(payload.get("has_offline_messages"))
        if raw_peer.startswith("[群]"):
            group_name = self._group_name_from_payload(payload)
            members = list(payload.get("members") or [])
            count = len(members)
            suffix = self._session_attention_suffix(
                unread_count=unread_count,
                has_offline_messages=has_offline_messages,
            )
            if count > 0:
                return f"{group_name}  ·  群聊 · {count}人{suffix}"
            return f"{group_name}  ·  群聊{suffix}"
        nickname = str(payload.get("nickname") or raw_peer)
        online = "在线" if bool(payload.get("is_online")) else "离线"
        suffix = self._session_attention_suffix(
            unread_count=unread_count,
            has_offline_messages=has_offline_messages,
        )
        return f"{nickname}  ·  {online}{suffix}"

    def _apply_session_summary(
        self, raw_peer: str | None, payload: dict[str, object] | None
    ) -> None:
        if not raw_peer or not payload:
            self.label_peer_badge.setText("未选中会话")
            self.label_peer_title.setText("请选择会话")
            self.label_peer_subtitle.setText("支持文本消息、文件消息与群聊消息。")
            self.label_peer_meta.setText("群聊会显示成员信息，私聊会显示连接状态。")
            self.btn_send_file.setEnabled(False)
            return
        unread_count = self._unread_count(payload)
        is_group = raw_peer.startswith("[群]")
        if is_group:
            members = [str(item) for item in list(payload.get("members") or []) if item]
            member_text = "、".join(members[:6])
            extra = "…" if len(members) > 6 else ""
            member_count = len(members)
            badge = "群聊会话"
            if unread_count > 0:
                badge = f"群聊会话 · {self._format_unread_count(unread_count)}"
            elif bool(payload.get("has_offline_messages")):
                badge = "群聊会话 · 离线消息"
            self.label_peer_badge.setText(badge)
            self.label_peer_title.setText(self._group_name_from_payload(payload))
            self.label_peer_subtitle.setText(
                f"共 {member_count} 位成员，群消息会在气泡顶部显示发送者。"
            )
            if member_text:
                self.label_peer_meta.setText(f"成员：{member_text}{extra}")
            else:
                self.label_peer_meta.setText("成员信息暂未同步。")
            self.btn_send_file.setEnabled(False)
        else:
            nickname = str(payload.get("nickname") or raw_peer)
            online = "在线" if bool(payload.get("is_online")) else "离线"
            badge = "好友私聊"
            if unread_count > 0:
                badge = f"好友私聊 · {self._format_unread_count(unread_count)}"
            elif bool(payload.get("has_offline_messages")):
                badge = "好友私聊 · 离线消息"
            self.label_peer_badge.setText(badge)
            self.label_peer_title.setText(nickname)
            self.label_peer_subtitle.setText("当前为好友私聊会话，可发送文本与文件。")
            self.label_peer_meta.setText(f"账号：{raw_peer} · 当前状态：{online}")
            self.btn_send_file.setEnabled(True)

    def _group_name_from_payload(self, payload: dict[str, object]) -> str:
        nickname = str(payload.get("nickname") or "").strip()
        if nickname:
            return nickname
        raw_peer = str(payload.get("username") or "")
        if raw_peer.startswith("[群]") and "#" in raw_peer:
            return raw_peer[3:].rsplit("#", 1)[0]
        return raw_peer or "群聊"

    def _render_message_block(self, item: dict[str, object]) -> str:
        outgoing = bool(item.get("outgoing"))
        sender = "我" if outgoing else str(item.get("sender") or "未知用户")
        created_at = html.escape(str(item.get("created_at", "")))
        sender_html = html.escape(sender)
        message_type = str(item.get("message_type") or "text")
        align = "right" if outgoing else "left"
        shell_bg = "#1677FF" if outgoing else "#FFFFFF"
        shell_color = "white" if outgoing else "#111827"
        border_radius = "20px 20px 6px 20px" if outgoing else "20px 20px 20px 6px"
        border_style = (
            "border:none;"
            if outgoing
            else "border:1px solid rgba(148, 163, 184, 0.24);"
        )
        body_html = ""
        if message_type == "file":
            file_name = html.escape(str(item.get("file_name") or "未命名文件"))
            size_text = html.escape(str(item.get("file_size_text") or ""))
            delivery_text = html.escape(str(item.get("file_delivery_text") or ""))
            content = html.escape(str(item.get("content", ""))).replace("\n", "<br>")
            body_html = (
                "<div style='font-size:12px;letter-spacing:0.8px;opacity:0.88;margin-bottom:8px;'>"
                "文件传输</div>"
                f"<div style='font-size:15px;font-weight:700;margin-bottom:6px;'>{file_name}</div>"
                f"<div style='font-size:12px;opacity:0.84;margin-bottom:6px;'>{size_text}</div>"
                f"<div style='font-size:12px;opacity:0.88;line-height:1.6;'>{delivery_text}</div>"
            )
            if content:
                body_html += (
                    "<div style='margin-top:8px;font-size:12px;opacity:0.84;line-height:1.6;'>"
                    f"{content}</div>"
                )
        else:
            content = html.escape(str(item.get("content", ""))).replace("\n", "<br>")
            body_html = f"<div style='font-size:14px;line-height:1.72;'>{content}</div>"
        return (
            f"<div style='text-align:{align};margin:14px 0;'>"
            f"<div style='font-size:12px;color:#64748B;margin-bottom:4px;'>{sender_html} · {created_at}</div>"
            f"<div style='display:inline-block;max-width:76%;background:{shell_bg};color:{shell_color};"
            f"padding:12px 16px;border-radius:{border_radius};box-shadow:0 12px 24px rgba(15, 23, 42, 0.08);"
            f"{border_style}'>"
            f"{body_html}</div></div>"
        )

    def _shorten_path(self, path: str, *, limit: int = 56) -> str:
        if len(path) <= limit:
            return path
        head = path[:24]
        tail = path[-24:]
        return f"{head}...{tail}"

    def _rebuild_session_list(self, *, selected_peer: str | None) -> None:
        self.list_sessions.blockSignals(True)
        self.list_sessions.clear()
        selected_index = 0
        for payload in sorted(
            self._session_payloads.values(),
            key=self._session_sort_key,
        ):
            item = QListWidgetItem(self._format_session_label(payload))
            raw_peer = str(payload.get("username") or "")
            item.setData(Qt.UserRole, raw_peer)
            self.list_sessions.addItem(item)
            if selected_peer and raw_peer == selected_peer:
                selected_index = self.list_sessions.count() - 1

        if self.list_sessions.count() == 0:
            self.current_peer = None
            self.list_sessions.blockSignals(False)
            self._apply_session_summary(None, None)
            return

        self.list_sessions.setCurrentRow(selected_index)
        current_item = self.list_sessions.currentItem()
        self.list_sessions.blockSignals(False)

        if current_item is None:
            self.current_peer = None
            self._apply_session_summary(None, None)
            return
        raw_peer = current_item.data(Qt.UserRole)
        if not isinstance(raw_peer, str) or not raw_peer:
            raw_peer = current_item.text()
        self.current_peer = raw_peer
        self._apply_session_summary(raw_peer, self._session_payloads.get(raw_peer))

    def _session_sort_key(self, payload: dict[str, object]) -> tuple[int, int, str, str]:
        unread_count = self._unread_count(payload)
        has_offline_messages = bool(payload.get("has_offline_messages"))
        attention_rank = 0 if unread_count > 0 or has_offline_messages else 1
        has_activity = 0 if str(payload.get("last_message_at") or "").strip() else 1
        last_message_at = str(payload.get("last_message_at") or "")
        display_name = str(payload.get("nickname") or payload.get("username") or "")
        return (
            attention_rank,
            has_activity,
            f"{99999999999999 - self._timestamp_sort_value(last_message_at):014d}",
            display_name.lower(),
        )

    def _session_attention_suffix(
        self, *, unread_count: int, has_offline_messages: bool
    ) -> str:
        if unread_count > 0:
            return f"  ·  {self._format_unread_count(unread_count)}"
        if has_offline_messages:
            return "  ·  离线消息"
        return ""

    def _format_unread_count(self, unread_count: int) -> str:
        if unread_count <= 0:
            return "无未读"
        if unread_count > 99:
            return "99+ 未读"
        return f"{unread_count} 条未读"

    def _unread_count(self, payload: dict[str, object]) -> int:
        try:
            return max(0, int(payload.get("unread_count") or 0))
        except (TypeError, ValueError):
            return 0

    def _timestamp_sort_value(self, value: str) -> int:
        digits = "".join(ch for ch in value if ch.isdigit())
        if not digits:
            return 0
        try:
            return int(digits)
        except ValueError:
            return 0
