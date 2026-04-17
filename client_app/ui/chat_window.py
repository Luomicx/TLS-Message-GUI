from __future__ import annotations

from PyQt5.QtCore import QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon as FIF,
    InfoBar,
    ListWidget,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    StrongBodyLabel,
    TextEdit,
    ToolButton,
)

from .theme import (
    WECHAT_GREEN,
    apply_app_style,
    make_avatar_placeholder,
    make_nav_button,
)


class BubbleCard(QFrame):
    def __init__(
        self,
        *,
        text: str,
        outgoing: bool,
        sender: str = "",
        is_file: bool = False,
        file_name: str = "",
        file_size_text: str = "",
        file_delivery_text: str = "",
    ) -> None:
        super().__init__()
        self.setObjectName("bubbleCard")
        self.setSizePolicy(self.sizePolicy().Maximum, self.sizePolicy().Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        self.setMinimumWidth(88)
        self.setMaximumWidth(360)

        bubble_shadow = "background:transparent;"
        if not outgoing and sender:
            sender_label = QLabel(sender, self)
            sender_label.setStyleSheet(
                "color:#888888;font-size:11px;font-weight:500;background:transparent;"
            )
            layout.addWidget(sender_label)

        if is_file:
            file_type = QLabel("文件传输", self)
            file_type.setStyleSheet(
                "color:#6B7280;font-size:11px;background:transparent;"
            )
            layout.addWidget(file_type)

            name_label = QLabel(file_name or "未命名文件", self)
            name_label.setWordWrap(True)
            name_label.setStyleSheet(
                "color:#111111;font-size:14px;font-weight:600;line-height:1.45;background:transparent;"
            )
            layout.addWidget(name_label)

            meta_text = " · ".join(
                text
                for text in [file_size_text.strip(), file_delivery_text.strip()]
                if text.strip()
            )
            if meta_text:
                meta_label = QLabel(meta_text, self)
                meta_label.setWordWrap(True)
                meta_label.setStyleSheet(
                    "color:#6B7280;font-size:11px;line-height:1.5;background:transparent;"
                )
                layout.addWidget(meta_label)

            if text.strip():
                desc_label = QLabel(text, self)
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet(
                    "color:#333333;font-size:12px;line-height:1.65;background:transparent;"
                )
                layout.addWidget(desc_label)
        else:
            body_label = QLabel(text, self)
            body_label.setWordWrap(True)
            body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            body_label.setStyleSheet(
                "color:#111111;font-size:14px;line-height:1.75;background:transparent;"
            )
            layout.addWidget(body_label)

        background = WECHAT_GREEN if outgoing else "#FFFFFF"
        border = "none" if outgoing else "1px solid #E0E0E0"
        radius = "16px 16px 4px 16px" if outgoing else "16px 16px 16px 4px"
        self.setStyleSheet(
            f"QFrame#bubbleCard {{"
            f"background:{background};"
            f"border:{border};"
            f"border-radius:{radius};"
            f"}}"
        )


class TimeDivider(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 6)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(text, self)
        label.setStyleSheet(
            "color:#999999;font-size:11px;background:transparent;padding:0 8px;"
        )
        layout.addWidget(label)


class MessageRow(QWidget):
    def __init__(
        self,
        *,
        outgoing: bool,
        sender: str,
        created_at: str,
        bubble: BubbleCard,
        avatar_text: str,
        avatar_color: str,
    ) -> None:
        super().__init__()
        self.setObjectName("messageRow")
        self.setStyleSheet("QWidget#messageRow { background:transparent; }")

        from PyQt5.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6 if outgoing else 4, 0, 8)
        root.setSpacing(4)

        avatar = make_avatar_placeholder(avatar_text, 36)
        avatar.setStyleSheet(f"background:{avatar_color};border-radius:18px;")
        avatar.setToolTip(sender)

        bubble.setMaximumWidth(340)

        bubble_wrap = QWidget(self)
        bubble_wrap.setMaximumWidth(500)
        bubble_wrap_layout = QHBoxLayout(bubble_wrap)
        bubble_wrap_layout.setContentsMargins(0, 0, 0, 0)
        bubble_wrap_layout.setSpacing(0)
        bubble_wrap_layout.addWidget(bubble)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        top_row.setAlignment(Qt.AlignTop)

        if outgoing:
            top_row.addStretch(1)
            top_row.addWidget(bubble_wrap, 0, Qt.AlignRight | Qt.AlignTop)
            top_row.addWidget(avatar, 0, Qt.AlignTop)
        else:
            top_row.addWidget(avatar, 0, Qt.AlignTop)
            top_row.addWidget(bubble_wrap, 0, Qt.AlignLeft | Qt.AlignTop)
            top_row.addStretch(1)
        root.addLayout(top_row)

        time_row = QHBoxLayout()
        time_row.setContentsMargins(0, 0, 0, 0)
        time_row.setSpacing(0)

        time_label = QLabel(created_at, self)
        time_label.setStyleSheet("color:#999999;font-size:11px;background:transparent;")

        if outgoing:
            time_row.addStretch(1)
            time_row.addWidget(time_label, 0, Qt.AlignRight)
            time_row.addSpacing(48)
        else:
            time_row.addSpacing(48)
            time_row.addWidget(time_label, 0, Qt.AlignLeft)
            time_row.addStretch(1)
        root.addLayout(time_row)


class SessionItemWidget(QWidget):
    def __init__(
        self,
        *,
        title: str,
        preview: str,
        time_text: str,
        badge_text: str,
        avatar_text: str,
        selected: bool = False,
    ) -> None:
        super().__init__()
        self.setObjectName("sessionItemCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(10)

        avatar = make_avatar_placeholder(avatar_text, 36)
        layout.addWidget(avatar, 0, Qt.AlignTop)

        center = QWidget(self)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(3)

        title_label = QLabel(title, center)
        title_label.setStyleSheet(
            "color:#1F1F1F;font-size:13px;font-weight:600;background:transparent;"
        )
        preview_label = QLabel(preview, center)
        preview_label.setStyleSheet(
            "color:#7A7A7A;font-size:11px;background:transparent;"
        )
        preview_label.setWordWrap(False)

        center_layout.addWidget(title_label)
        center_layout.addWidget(preview_label)
        layout.addWidget(center, 1)

        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        right_layout.setAlignment(Qt.AlignRight | Qt.AlignTop)

        time_label = QLabel(time_text, right)
        time_label.setStyleSheet("color:#9A9A9A;font-size:10px;background:transparent;")
        time_label.setAlignment(Qt.AlignRight)

        badge_label = QLabel(badge_text, right)
        if badge_text == "●":
            badge_label.setStyleSheet(
                "color:#FF4D4F;font-size:11px;background:transparent;font-weight:700;"
            )
        elif badge_text:
            badge_label.setStyleSheet(
                "color:white;background:#FF4D4F;border-radius:9px;"
                "font-size:10px;font-weight:600;padding:1px 6px;"
            )
        else:
            badge_label.setStyleSheet("background:transparent;")
        badge_label.setVisible(bool(badge_text))
        badge_label.setAlignment(Qt.AlignRight)

        right_layout.addWidget(time_label)
        right_layout.addWidget(badge_label, 0, Qt.AlignRight)
        right_layout.addStretch(1)
        layout.addWidget(right, 0, Qt.AlignTop)

        self.setStyleSheet(
            "QWidget#sessionItemCard {"
            + ("background:#DCDCDC;" if selected else "background:transparent;")
            + "border-radius:8px; }"
        )
        self.setMinimumHeight(52)
        self.setMaximumHeight(52)


class ChatWindow(QMainWindow):
    DEFAULT_WIDTH = 1280
    DEFAULT_HEIGHT = 820
    MIN_WIDTH = 900
    MIN_HEIGHT = 600

    NAV_WIDTH = 60
    MIDDLE_WIDTH = 248

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
        self._nav_buttons: list[ToolButton] = []
        self._current_user_nickname = "当前用户"
        self._current_user_username = ""
        self._panel_search_placeholder = {
            0: "搜索会话",
            1: "搜索好友",
            2: "筛选结果 / 回车搜索",
        }
        self._nav_selected_stylesheet = (
            "ToolButton { background:rgba(255,255,255,0.16); border:none; border-radius:6px; }"
            "ToolButton:hover { background:rgba(255,255,255,0.22); }"
        )
        self._nav_unselected_stylesheet = (
            "ToolButton { background:transparent; border:none; border-radius:6px; }"
            "ToolButton:hover { background:#3D3D3D; }"
        )
        self._message_widgets: list[QWidget] = []
        self._message_placeholder_text = "当前没有消息，请先选择会话。"

        self._build_ui()
        apply_app_style(self)
        self._sync_panel_search_placeholder()
        self._sync_send_state()
        self._apply_session_summary(None, None)
        self.switch_page(0)
        self._update_window_title()

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

    def _centered_rect(self, available: QRect, width: int, height: int) -> QRect:
        left = available.left() + max(0, (available.width() - width) // 2)
        top = available.top() + max(0, (available.height() - height) // 2)
        return QRect(left, top, width, height)

    def _build_ui(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        self.setCentralWidget(page)

        root = QHBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_nav_rail(), 0)
        root.addWidget(self._build_middle_panel(), 0)
        root.addWidget(self._build_chat_area(), 1)

    def _build_nav_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("navRail")
        rail.setFixedWidth(self.NAV_WIDTH)

        self._nav_layout = QVBoxLayout(rail)
        self._nav_layout.setContentsMargins(0, 16, 0, 16)
        self._nav_layout.setSpacing(4)
        self._nav_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._nav_avatar = make_avatar_placeholder("?", 36)
        self._nav_avatar.setCursor(Qt.PointingHandCursor)
        self._nav_avatar.mousePressEvent = lambda _e: self.profile_requested.emit()
        self._nav_layout.addWidget(self._nav_avatar, 0, Qt.AlignHCenter)
        self._nav_layout.addSpacing(20)

        self.btn_nav_chat = make_nav_button(FIF.CHAT, "聊天")
        self.btn_nav_contacts = make_nav_button(FIF.PEOPLE, "通讯录")
        self.btn_nav_search = make_nav_button(FIF.SEARCH, "搜索")
        self._nav_buttons = [
            self.btn_nav_chat,
            self.btn_nav_contacts,
            self.btn_nav_search,
        ]

        self.btn_nav_chat.clicked.connect(lambda: self.switch_page(0))
        self.btn_nav_contacts.clicked.connect(lambda: self.switch_page(1))
        self.btn_nav_search.clicked.connect(lambda: self.switch_page(2))

        for button in self._nav_buttons:
            self._nav_layout.addWidget(button, 0, Qt.AlignHCenter)

        self._nav_layout.addStretch(1)

        self.btn_profile = make_nav_button(FIF.EDIT, "个人资料")
        self.btn_profile.clicked.connect(self.profile_requested.emit)
        self._nav_layout.addWidget(self.btn_profile, 0, Qt.AlignHCenter)

        self.btn_logout = make_nav_button(FIF.SYNC, "注销")
        self.btn_logout.clicked.connect(self.logout_requested.emit)
        self._nav_layout.addWidget(self.btn_logout, 0, Qt.AlignHCenter)

        return rail

    def _build_middle_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("middlePanel")
        panel.setFixedWidth(self.MIDDLE_WIDTH)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.panel_search = SearchLineEdit(panel)
        self.panel_search.setObjectName("panelSearch")
        self.panel_search.textChanged.connect(self._handle_panel_search)
        self.panel_search.returnPressed.connect(self._handle_panel_search_submit)
        layout.addWidget(self.panel_search)

        self.middle_stack = QStackedWidget(panel)

        session_page = QWidget()
        session_layout = QVBoxLayout(session_page)
        session_layout.setContentsMargins(0, 4, 0, 0)
        session_layout.setSpacing(0)
        self.list_sessions = ListWidget(session_page)
        self.list_sessions.setObjectName("sessionList")
        self.list_sessions.setSpacing(2)
        self.list_sessions.currentItemChanged.connect(self._on_session_changed)
        self.list_sessions.itemDoubleClicked.connect(self._activate_session_from_list)
        session_layout.addWidget(self.list_sessions)
        self.middle_stack.addWidget(session_page)

        friend_page = QWidget()
        friend_layout = QVBoxLayout(friend_page)
        friend_layout.setContentsMargins(0, 4, 0, 0)
        friend_layout.setSpacing(0)
        self.list_friends = ListWidget(friend_page)
        self.list_friends.setObjectName("friendList")
        self.list_friends.setWordWrap(True)
        self.list_friends.setSpacing(2)
        self.list_friends.itemDoubleClicked.connect(self._open_friend_session)
        friend_layout.addWidget(self.list_friends)
        self.middle_stack.addWidget(friend_page)

        search_page = QWidget()
        search_layout = QVBoxLayout(search_page)
        search_layout.setContentsMargins(0, 4, 0, 0)
        search_layout.setSpacing(8)

        mode_row = QWidget(search_page)
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(6)

        self.btn_mode_nickname = PushButton(mode_row)
        self.btn_mode_nickname.setText("昵称")
        self.btn_mode_nickname.setFixedHeight(30)
        self.btn_mode_nickname.clicked.connect(lambda: self._set_search_mode("fuzzy"))

        self.btn_mode_id = PushButton(mode_row)
        self.btn_mode_id.setText("账号")
        self.btn_mode_id.setFixedHeight(30)
        self.btn_mode_id.clicked.connect(lambda: self._set_search_mode("id"))

        mode_layout.addWidget(self.btn_mode_nickname)
        mode_layout.addWidget(self.btn_mode_id)
        search_layout.addWidget(mode_row)

        self.search_input = SearchLineEdit(search_page)
        self.search_input.setPlaceholderText("输入用户名或账号后回车")
        self.search_input.returnPressed.connect(self._emit_search)
        search_layout.addWidget(self.search_input)

        self.btn_trigger_search = PrimaryPushButton(search_page)
        self.btn_trigger_search.setText("搜索")
        self.btn_trigger_search.setIcon(FIF.SEARCH)
        self.btn_trigger_search.setFixedHeight(32)
        self.btn_trigger_search.clicked.connect(self._emit_search)
        search_layout.addWidget(self.btn_trigger_search)

        self.list_search_result = ListWidget(search_page)
        self.list_search_result.setObjectName("searchResultList")
        self.list_search_result.setWordWrap(True)
        self.list_search_result.setSpacing(2)
        self.list_search_result.itemDoubleClicked.connect(
            self._emit_add_friend_from_result
        )
        search_layout.addWidget(self.list_search_result, 1)

        self.label_search_hint = CaptionLabel(search_page)
        self.label_search_hint.setStyleSheet("color:#888;")
        search_layout.addWidget(self.label_search_hint)

        self.middle_stack.addWidget(search_page)
        layout.addWidget(self.middle_stack, 1)

        self._set_search_mode("fuzzy")
        return panel

    def _build_chat_area(self) -> QWidget:
        area = QWidget()
        area.setObjectName("chatArea")

        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(area)
        header.setObjectName("chatHeader")
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)

        title_box = QWidget(header)
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(1)

        self.label_peer_title = StrongBodyLabel(title_box)
        self.label_peer_title.setText("请选择会话")

        self.label_peer_subtitle = CaptionLabel(title_box)
        self.label_peer_subtitle.setStyleSheet("color:#888;")
        self.label_peer_subtitle.setText("暂无会话 · 选择左侧联系人开始聊天")

        self.label_peer_status = CaptionLabel(title_box)
        self.label_peer_status.setStyleSheet("color:#9A9A9A;")
        self.label_peer_status.setText("消息、文件与群聊状态会在这里显示")

        title_layout.addWidget(self.label_peer_title)
        title_layout.addWidget(self.label_peer_subtitle)
        title_layout.addWidget(self.label_peer_status)
        header_layout.addWidget(title_box, 1)

        self.btn_send_file = ToolButton(header)
        self.btn_send_file.setIcon(FIF.FOLDER)
        self.btn_send_file.setToolTip("发送文件")
        self.btn_send_file.setFixedSize(36, 36)
        self.btn_send_file.clicked.connect(self._emit_send_file)

        self.btn_select_download_root = ToolButton(header)
        self.btn_select_download_root.setIcon(FIF.DOWNLOAD)
        self.btn_select_download_root.setToolTip("接收目录")
        self.btn_select_download_root.setFixedSize(36, 36)
        self.btn_select_download_root.clicked.connect(self.download_root_requested.emit)

        self.btn_group = ToolButton(header)
        self.btn_group.setIcon(FIF.PEOPLE)
        self.btn_group.setToolTip("创建群聊")
        self.btn_group.setFixedSize(36, 36)
        self.btn_group.clicked.connect(self.create_group_requested.emit)

        header_layout.addWidget(self.btn_send_file)
        header_layout.addWidget(self.btn_select_download_root)
        header_layout.addWidget(self.btn_group)
        layout.addWidget(header)

        self.message_scroll = QScrollArea(area)
        self.message_scroll.setObjectName("transcriptView")
        self.message_scroll.setWidgetResizable(True)
        self.message_scroll.setFrameShape(QFrame.NoFrame)
        self.message_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.message_scroll.setFocusPolicy(Qt.NoFocus)

        self.message_area = QWidget()
        self.message_area.setObjectName("transcriptViewport")
        self.message_layout = QVBoxLayout(self.message_area)
        self.message_layout.setContentsMargins(14, 14, 14, 14)
        self.message_layout.setSpacing(0)
        self.message_layout.addStretch(1)
        self.message_scroll.setWidget(self.message_area)
        layout.addWidget(self.message_scroll, 1)

        composer = QWidget(area)
        composer.setObjectName("composer")
        composer_layout = QVBoxLayout(composer)
        composer_layout.setContentsMargins(16, 8, 16, 8)
        composer_layout.setSpacing(6)

        toolbar = QWidget(composer)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.btn_emoji = ToolButton(toolbar)
        self.btn_emoji.setIcon(FIF.EMOJI_TAB_SYMBOLS)
        self.btn_emoji.setToolTip("表情")
        self.btn_emoji.setFixedSize(30, 30)
        self.btn_emoji.setEnabled(False)

        self.btn_file_toolbar = ToolButton(toolbar)
        self.btn_file_toolbar.setIcon(FIF.FOLDER)
        self.btn_file_toolbar.setToolTip("发送文件")
        self.btn_file_toolbar.setFixedSize(30, 30)
        self.btn_file_toolbar.clicked.connect(self._emit_send_file)

        self.btn_recv_dir_toolbar = ToolButton(toolbar)
        self.btn_recv_dir_toolbar.setIcon(FIF.DOWNLOAD)
        self.btn_recv_dir_toolbar.setToolTip("接收目录")
        self.btn_recv_dir_toolbar.setFixedSize(30, 30)
        self.btn_recv_dir_toolbar.clicked.connect(self.download_root_requested.emit)

        toolbar_layout.addWidget(self.btn_emoji)
        toolbar_layout.addWidget(self.btn_file_toolbar)
        toolbar_layout.addWidget(self.btn_recv_dir_toolbar)
        toolbar_layout.addStretch(1)
        composer_layout.addWidget(toolbar)

        self.edit_message = TextEdit(composer)
        self.edit_message.setAcceptRichText(False)
        self.edit_message.setMinimumHeight(52)
        self.edit_message.setMaximumHeight(120)
        self.edit_message.setPlaceholderText("输入消息内容...")
        composer_layout.addWidget(self.edit_message, 1)

        bottom_row = QWidget(composer)
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        self.label_runtime_status = CaptionLabel(bottom_row)
        self.label_runtime_status.setStyleSheet("color:#888;")
        self.label_runtime_status.setText("连接状态：已连接服务器 · 未选择会话")

        self.label_download_root = CaptionLabel(bottom_row)
        self.label_download_root.setStyleSheet("color:#888;")
        self.label_download_root.setText("")

        bottom_layout.addWidget(self.label_runtime_status)
        bottom_layout.addWidget(self.label_download_root, 1)
        bottom_layout.addStretch(1)

        self.btn_send = PrimaryPushButton(bottom_row)
        self.btn_send.setText("发送")
        self.btn_send.setIcon(FIF.SEND)
        self.btn_send.setFixedHeight(32)
        self.btn_send.setMinimumWidth(80)
        self.btn_send.clicked.connect(self._emit_send_message)
        bottom_layout.addWidget(self.btn_send)

        composer_layout.addWidget(bottom_row)
        layout.addWidget(composer, 0)

        self.label_current_user = CaptionLabel(area)
        self.label_current_user.hide()
        self.label_current_id = CaptionLabel(area)
        self.label_current_id.hide()
        self.label_security = CaptionLabel(area)
        self.label_security.hide()
        self.label_peer_badge = CaptionLabel(area)
        self.label_peer_badge.hide()
        self.label_peer_meta = CaptionLabel(area)
        self.label_peer_meta.hide()

        self._show_message_placeholder(self._message_placeholder_text)
        return area

    def switch_page(self, index: int) -> None:
        self.middle_stack.setCurrentIndex(index)
        self._sync_panel_search_placeholder()
        for i, button in enumerate(self._nav_buttons):
            button.setStyleSheet(
                self._nav_selected_stylesheet
                if i == index
                else self._nav_unselected_stylesheet
            )

        if index == 2:
            self.panel_search.setText(self.search_input.text())
        else:
            self.panel_search.blockSignals(True)
            self.panel_search.clear()
            self.panel_search.blockSignals(False)
            self._handle_panel_search("")

        if index == 0:
            self.list_sessions.setFocus()
        elif index == 1:
            self.list_friends.setFocus()
        else:
            self.search_input.setFocus()

        self.statusBar().showMessage(
            f"当前面板：{['会话', '好友', '搜索'][index]}", 1500
        )

    def _sync_panel_search_placeholder(self) -> None:
        self.panel_search.setPlaceholderText(
            self._panel_search_placeholder.get(self.middle_stack.currentIndex(), "搜索")
        )

    def _activate_session_from_list(self, item: QListWidgetItem) -> None:
        if item is not None:
            self.list_sessions.setCurrentItem(item)

    def _handle_panel_search(self, text: str) -> None:
        query = text.strip().lower()
        index = self.middle_stack.currentIndex()
        if index == 0:
            self._filter_session_list(query)
        elif index == 1:
            self._filter_friend_list(query)
        else:
            self._filter_search_results(query)

    def _handle_panel_search_submit(self) -> None:
        if self.middle_stack.currentIndex() == 2 and self.panel_search.text().strip():
            self.search_input.setText(self.panel_search.text().strip())
            self._emit_search()

    def _filter_session_list(self, query: str) -> None:
        for index in range(self.list_sessions.count()):
            item = self.list_sessions.item(index)
            haystack = str(item.data(Qt.UserRole + 1) or "").lower()
            item.setHidden(bool(query) and query not in haystack)

    def _filter_friend_list(self, query: str) -> None:
        for index in range(self.list_friends.count()):
            item = self.list_friends.item(index)
            haystack = f"{item.text()}\n{item.data(Qt.UserRole) or ''}".lower()
            item.setHidden(bool(query) and query not in haystack)

    def _filter_search_results(self, query: str) -> None:
        for index in range(self.list_search_result.count()):
            item = self.list_search_result.item(index)
            item.setHidden(bool(query) and query not in item.text().lower())

    def _on_session_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        raw_peer = current.data(Qt.UserRole)
        if not isinstance(raw_peer, str) or not raw_peer:
            return
        self.current_peer = raw_peer
        payload = dict(self._session_payloads.get(raw_peer) or {"username": raw_peer})
        self._apply_session_summary(raw_peer, payload)
        self._sync_send_state()
        self.session_selected.emit(raw_peer)
        self.statusBar().showMessage(f"当前会话：{raw_peer}", 3000)

    def _sync_send_state(self) -> None:
        enabled = bool(self.current_peer)
        file_enabled = enabled and not str(self.current_peer).startswith("[群]")
        self.edit_message.setEnabled(enabled)
        self.btn_send.setEnabled(enabled)
        self.btn_send_file.setEnabled(file_enabled)
        self.btn_file_toolbar.setEnabled(file_enabled)
        self.label_runtime_status.setText(self._compose_runtime_status())
        self.edit_message.setPlaceholderText(
            f"给 {self.label_peer_title.text()} 发送消息..."
            if enabled
            else "输入消息内容..."
        )

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
        is_id_mode = mode == "id"
        self.btn_mode_nickname.setEnabled(is_id_mode)
        self.btn_mode_id.setEnabled(not is_id_mode)
        self.search_input.setPlaceholderText(
            "输入账号后回车" if is_id_mode else "输入用户名/昵称后回车"
        )
        self.label_search_hint.setText(
            "当前：账号搜索，双击结果添加好友"
            if is_id_mode
            else "当前：昵称搜索，双击结果添加好友"
        )

    def _emit_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.show_notice("请输入搜索内容")
            return
        self.search_requested.emit(self._search_mode, query)

    def _emit_add_friend_from_result(self, item: QListWidgetItem) -> None:
        user_id = item.data(Qt.UserRole)
        if isinstance(user_id, int):
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
        self.panel_search.clear()
        self.search_input.clear()
        self._clear_message_widgets()
        self._refresh_nav_avatar("?")
        self._apply_session_summary(None, None)
        self._sync_send_state()

    def set_current_user(self, user: dict[str, object] | None) -> None:
        if not user:
            return
        username = str(user.get("username") or "")
        nickname = str(user.get("nickname") or username or "当前用户")
        self._current_user_username = username
        self._current_user_nickname = nickname
        self.label_current_user.setText(nickname)
        self.label_current_id.setText(f"用户名: {username}")
        self.label_security.setText("TLS 安全连接已建立")
        self._refresh_nav_avatar(nickname)
        self._update_window_title()

    def populate_friends(self, friends: list[dict[str, object]]) -> None:
        self.list_friends.clear()
        for item in friends:
            username = str(item.get("username") or "")
            nickname = str(item.get("nickname") or username)
            online = "在线" if bool(item.get("is_online")) else "离线"
            row = QListWidgetItem(f"{nickname}\n{username} · {online}")
            row.setData(Qt.UserRole, username)
            row.setToolTip(f"{nickname} ({username})")
            row.setSizeHint(QSize(0, 48))
            self.list_friends.addItem(row)
        self._filter_friend_list(self.panel_search.text().strip().lower())

    def populate_sessions(self, sessions: list[dict[str, object]]) -> None:
        current_peer = self.current_peer
        self._session_payloads.clear()
        for item in sessions:
            raw_peer = str(item.get("username") or "")
            if raw_peer:
                self._session_payloads[raw_peer] = dict(item)
        self._rebuild_session_list(selected_peer=current_peer)

    def populate_messages(self, messages: list[dict[str, object]]) -> None:
        self._render_message_list(messages)
        self._update_current_session_preview(messages)

    def populate_search_results(self, users: list[dict[str, object]]) -> None:
        self.list_search_result.clear()
        for item in users:
            username = str(item.get("username") or "")
            nickname = str(item.get("nickname") or username)
            raw_user_key = item.get("id")
            online = "在线" if bool(item.get("is_online")) else "离线"
            row = QListWidgetItem(f"{nickname}\n账号:{username} · {online}")
            row.setData(
                Qt.UserRole, int(raw_user_key) if raw_user_key is not None else -1
            )
            row.setToolTip(f"{nickname} ({username})")
            row.setSizeHint(QSize(0, 52))
            self.list_search_result.addItem(row)
        self._filter_search_results(self.panel_search.text().strip().lower())

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
        self.label_download_root.setText(f"接收目录: {display_path}")
        self.label_download_root.setToolTip(path)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.close_requested.emit()
        super().closeEvent(event)

    def _refresh_nav_avatar(self, nickname: str) -> None:
        letter = nickname[:1] if nickname else "?"
        new_avatar = make_avatar_placeholder(letter, 40)
        new_avatar.setCursor(Qt.PointingHandCursor)
        new_avatar.mousePressEvent = lambda _e: self.profile_requested.emit()
        index = self._nav_layout.indexOf(self._nav_avatar)
        if index < 0:
            return
        self._nav_layout.removeWidget(self._nav_avatar)
        self._nav_avatar.deleteLater()
        self._nav_layout.insertWidget(index, new_avatar, 0, Qt.AlignHCenter)
        self._nav_avatar = new_avatar

    def _update_window_title(self) -> None:
        base = "安全网络聊天工具 - 客户端"
        if self._current_user_nickname:
            base = f"{base} - {self._current_user_nickname}"
        self.setWindowTitle(base)

    def _update_current_session_preview(
        self, messages: list[dict[str, object]]
    ) -> None:
        if not self.current_peer or not messages:
            return
        latest = messages[-1]
        payload = self._session_payloads.get(self.current_peer)
        if payload is None:
            return
        if str(latest.get("message_type") or "text") == "file":
            preview = str(latest.get("file_name") or "[文件]")
        else:
            preview = str(latest.get("content") or "")
        payload["last_message_preview"] = self._normalize_preview(preview)
        created_at = str(latest.get("created_at") or "")
        if created_at:
            payload["last_message_at"] = created_at
        self._rebuild_session_list(selected_peer=self.current_peer)

    def _normalize_preview(self, text: str, *, limit: int = 24) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return f"{compact[:limit]}…"

    def _session_title(self, payload: dict[str, object]) -> str:
        raw_peer = str(payload.get("username") or "")
        if raw_peer.startswith("[群]"):
            return self._group_name_from_payload(payload)
        return str(payload.get("nickname") or raw_peer or "未命名会话")

    def _session_preview_text(self, payload: dict[str, object]) -> str:
        preview = str(payload.get("last_message_preview") or "").strip()
        if not preview:
            if str(payload.get("username") or "").startswith("[群]"):
                preview = f"群聊 · {len(list(payload.get('members') or []))}人"
            elif bool(payload.get("has_offline_messages")):
                preview = "有离线消息"
            elif self._unread_count(payload) > 0:
                preview = f"{self._unread_count(payload)} 条未读消息"
            else:
                preview = "暂无消息"
        return self._normalize_preview(preview)

    def _session_time_text(self, payload: dict[str, object]) -> str:
        raw = str(payload.get("last_message_at") or "").strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 12:
            return f"{digits[-6:-4]}:{digits[-4:-2]}"
        if len(digits) >= 4:
            return f"{digits[-4:-2]}:{digits[-2:]}"
        if len(raw) >= 5:
            return raw[-5:]
        return ""

    def _session_badge_text(self, payload: dict[str, object]) -> str:
        unread_count = self._unread_count(payload)
        if unread_count > 99:
            return "99+"
        if unread_count > 0:
            return str(unread_count)
        if bool(payload.get("has_offline_messages")):
            return "●"
        return ""

    def _session_avatar_text(self, payload: dict[str, object]) -> str:
        raw_peer = str(payload.get("username") or "")
        if raw_peer.startswith("[群]"):
            return "群"
        title = self._session_title(payload)
        return title[:1].upper() if title else "?"

    def _session_status_text(self, payload: dict[str, object]) -> str:
        unread_count = self._unread_count(payload)
        has_offline_messages = bool(payload.get("has_offline_messages"))
        if str(payload.get("username") or "").startswith("[群]"):
            member_count = len(list(payload.get("members") or []))
            if unread_count > 0:
                return f"群聊会话 · {member_count} 人 · {unread_count} 条未读"
            if has_offline_messages:
                return f"群聊会话 · {member_count} 人 · 有离线消息"
            return f"群聊会话 · {member_count} 人"
        online = "在线" if bool(payload.get("is_online")) else "离线"
        if unread_count > 0:
            return f"私聊会话 · {online} · {unread_count} 条未读"
        if has_offline_messages:
            return f"私聊会话 · {online} · 有离线消息"
        return f"私聊会话 · {online}"

    def _session_meta_text(self, raw_peer: str, payload: dict[str, object]) -> str:
        if raw_peer.startswith("[群]"):
            members = [str(item) for item in list(payload.get("members") or []) if item]
            if members:
                preview = "、".join(members[:4])
                suffix = "…" if len(members) > 4 else ""
                return f"成员：{preview}{suffix}"
            return "成员信息暂未同步"
        return f"用户名：{raw_peer}"

    def _session_search_text(self, raw_peer: str, payload: dict[str, object]) -> str:
        return " ".join(
            part
            for part in [
                raw_peer,
                self._session_title(payload),
                self._session_preview_text(payload),
                self._session_time_text(payload),
                self._session_badge_text(payload),
            ]
            if part
        )

    def _build_session_item_widget(
        self, raw_peer: str, payload: dict[str, object]
    ) -> QWidget:
        return SessionItemWidget(
            title=self._session_title(payload),
            preview=self._session_preview_text(payload),
            time_text=self._session_time_text(payload),
            badge_text=self._session_badge_text(payload),
            avatar_text=self._session_avatar_text(payload),
            selected=raw_peer == self.current_peer,
        )

    def _apply_session_summary(
        self, raw_peer: str | None, payload: dict[str, object] | None
    ) -> None:
        if not raw_peer or not payload:
            self.label_peer_title.setText("请选择会话")
            self.label_peer_subtitle.setText("暂无会话 · 选择左侧联系人开始聊天")
            self.label_peer_status.setText("消息、文件与群聊状态会在这里显示")
            self.label_peer_badge.setText("")
            self.label_peer_meta.setText("")
            return

        self.label_peer_title.setText(self._session_title(payload))
        self.label_peer_subtitle.setText(self._session_status_text(payload))
        self.label_peer_status.setText(self._session_meta_text(raw_peer, payload))
        self.label_peer_badge.setText(self._session_badge_text(payload))
        self.label_peer_meta.setText(self._session_meta_text(raw_peer, payload))

    def _compose_runtime_status(self) -> str:
        if not self.current_peer:
            return "连接状态：已连接服务器 · 未选择会话"
        if str(self.current_peer).startswith("[群]"):
            return "连接状态：已连接服务器 · 当前群聊仅支持文本消息"
        return "连接状态：已连接服务器 · 可发送文本和文件"

    def _group_name_from_payload(self, payload: dict[str, object]) -> str:
        nickname = str(payload.get("nickname") or "").strip()
        if nickname:
            return nickname
        raw_peer = str(payload.get("username") or "")
        if raw_peer.startswith("[群]") and "#" in raw_peer:
            return raw_peer[3:].rsplit("#", 1)[0]
        return raw_peer or "群聊"

    def _render_time_divider(self, created_at: str) -> QWidget:
        return TimeDivider(created_at)

    def _should_show_time_divider(
        self, created_at: str, previous_created_at: str | None
    ) -> bool:
        if not created_at:
            return False
        if previous_created_at is None:
            return True
        return (
            abs(
                self._timestamp_sort_value(created_at)
                - self._timestamp_sort_value(previous_created_at)
            )
            >= 500
        )

    def _format_unread_count(self, unread_count: int) -> str:
        if unread_count <= 0:
            return "无未读"
        if unread_count > 99:
            return "99+ 未读"
        return f"{unread_count} 条未读"

    def _message_outer_margin(self, outgoing: bool) -> str:
        return "14px 0 12px 0" if outgoing else "12px 0 12px 0"

    def _message_avatar_gap(self) -> int:
        return 10

    def _message_avatar_color(self, sender: str, outgoing: bool) -> str:
        return "#1677FF" if outgoing else self._avatar_color_for_text(sender)

    def _message_avatar_text(self, sender_display: str) -> str:
        return sender_display[:1].upper() if sender_display else "?"

    def _scroll_to_bottom_async(self) -> None:
        QTimer.singleShot(0, self._scroll_messages_to_bottom)

    def _set_empty_message_state(self) -> None:
        self._show_message_placeholder(self._message_placeholder_text)

    def _clear_message_state(self) -> None:
        self._clear_message_widgets()

    def _message_is_file(self, item: dict[str, object]) -> bool:
        return str(item.get("message_type") or "text") == "file"

    def _message_sender_display(self, sender: str, outgoing: bool) -> str:
        return "我" if outgoing else sender

    def _message_created_at(self, item: dict[str, object]) -> str:
        return str(item.get("created_at") or "")

    def _message_sender(self, item: dict[str, object]) -> str:
        return str(item.get("sender") or "未知用户")

    def _message_outgoing(self, item: dict[str, object]) -> bool:
        return bool(item.get("outgoing"))

    def _message_file_name(self, item: dict[str, object]) -> str:
        return str(item.get("file_name") or "")

    def _message_file_size_text(self, item: dict[str, object]) -> str:
        return str(item.get("file_size_text") or "")

    def _message_file_delivery_text(self, item: dict[str, object]) -> str:
        return str(item.get("file_delivery_text") or "")

    def _message_content_text(self, item: dict[str, object]) -> str:
        return str(item.get("content") or "")

    def _session_item_height(self) -> QSize:
        return QSize(0, 58)

    def _friend_item_height(self) -> QSize:
        return QSize(0, 42)

    def _search_item_height(self) -> QSize:
        return QSize(0, 46)

    def _session_current_payload(self) -> dict[str, object] | None:
        if not self.current_peer:
            return None
        return self._session_payloads.get(self.current_peer)

    def _sync_header_runtime(self) -> None:
        self.label_runtime_status.setText(self._compose_runtime_status())

    def _update_message_placeholder(self) -> None:
        self.edit_message.setPlaceholderText(
            f"给 {self.label_peer_title.text()} 发送消息..."
            if self.current_peer
            else "输入消息内容..."
        )

    def _refresh_after_summary(self) -> None:
        self._sync_header_runtime()
        self._update_message_placeholder()

    def _refresh_after_messages(self) -> None:
        self._sync_header_runtime()

    def _session_search_blob(self, raw_peer: str, payload: dict[str, object]) -> str:
        return self._session_search_text(raw_peer, payload)

    def _session_item_tooltip(self, raw_peer: str, payload: dict[str, object]) -> str:
        return self._session_meta_text(raw_peer, payload)

    def _apply_empty_summary(self) -> None:
        self.label_peer_title.setText("请选择会话")
        self.label_peer_subtitle.setText("暂无会话 · 选择左侧联系人开始聊天")
        self.label_peer_status.setText("消息、文件与群聊状态会在这里显示")

    def _statusbar_session_selected(self, raw_peer: str) -> None:
        self.statusBar().showMessage(f"当前会话：{raw_peer}", 3000)

    def _statusbar_panel_switched(self, index: int) -> None:
        self.statusBar().showMessage(
            f"当前面板：{['会话', '好友', '搜索'][index]}", 1500
        )

    def _statusbar_notice(self, text: str) -> None:
        self.statusBar().showMessage(text, 4500)

    def _session_has_group_prefix(self, raw_peer: str) -> bool:
        return raw_peer.startswith("[群]")

    def _current_peer_is_group(self) -> bool:
        return bool(self.current_peer) and str(self.current_peer).startswith("[群]")

    def _message_scrollbar(self):
        return self.message_scroll.verticalScrollBar()

    def _show_message_placeholder(self, text: str) -> None:
        self._clear_message_widgets()
        placeholder = CaptionLabel(self.message_area)
        placeholder.setText(text)
        placeholder.setStyleSheet("color:#999999;background:transparent;")
        self.message_layout.insertWidget(0, placeholder, 0, Qt.AlignCenter)
        self._message_widgets.append(placeholder)

    def _clear_message_widgets(self) -> None:
        for widget in self._message_widgets:
            self.message_layout.removeWidget(widget)
            widget.deleteLater()
        self._message_widgets.clear()

    def _render_message_list(self, messages: list[dict[str, object]]) -> None:
        self._clear_message_widgets()
        if not messages:
            self._show_message_placeholder(self._message_placeholder_text)
            return

        previous_created_at: str | None = None
        for item in messages:
            created_at = str(item.get("created_at") or "")
            if self._should_show_time_divider(created_at, previous_created_at):
                divider = TimeDivider(created_at)
                self.message_layout.insertWidget(
                    self.message_layout.count() - 1, divider
                )
                self._message_widgets.append(divider)

            widget = self._build_message_widget(item)
            self.message_layout.insertWidget(self.message_layout.count() - 1, widget)
            self._message_widgets.append(widget)
            previous_created_at = created_at

        QTimer.singleShot(0, self._scroll_messages_to_bottom)

    def _build_message_widget(self, item: dict[str, object]) -> QWidget:
        outgoing = bool(item.get("outgoing"))
        sender = str(item.get("sender") or "未知用户")
        sender_display = "我" if outgoing else sender
        is_file = str(item.get("message_type") or "text") == "file"

        bubble = BubbleCard(
            text=str(item.get("content") or ""),
            outgoing=outgoing,
            sender=sender_display,
            is_file=is_file,
            file_name=str(item.get("file_name") or ""),
            file_size_text=str(item.get("file_size_text") or ""),
            file_delivery_text=str(item.get("file_delivery_text") or ""),
        )

        avatar_color = "#1677FF" if outgoing else self._avatar_color_for_text(sender)
        return MessageRow(
            outgoing=outgoing,
            sender=sender_display,
            created_at=str(item.get("created_at") or ""),
            bubble=bubble,
            avatar_text=(sender_display[:1].upper() if sender_display else "?"),
            avatar_color=avatar_color,
        )

    def _scroll_messages_to_bottom(self) -> None:
        bar = self.message_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    @staticmethod
    def _avatar_color_for_text(text: str) -> str:
        colors = [
            "#1677FF",
            "#52C41A",
            "#FA8C16",
            "#722ED1",
            "#EB2F96",
            "#13C2C2",
            "#FAAD14",
            "#2F54EB",
        ]
        index = sum(ord(ch) for ch in text) % len(colors)
        return colors[index]

    def _shorten_path(self, path: str, *, limit: int = 40) -> str:
        if len(path) <= limit:
            return path
        return f"{path[:18]}...{path[-18:]}"

    def _rebuild_session_list(self, *, selected_peer: str | None) -> None:
        self.list_sessions.blockSignals(True)
        self.list_sessions.clear()
        selected_index = 0

        for payload in sorted(
            self._session_payloads.values(), key=self._session_sort_key
        ):
            raw_peer = str(payload.get("username") or "")
            item = QListWidgetItem("")
            item.setData(Qt.UserRole, raw_peer)
            item.setData(Qt.UserRole + 1, self._session_search_text(raw_peer, payload))
            item.setToolTip(self._session_meta_text(raw_peer, payload))
            item.setSizeHint(QSize(0, 58))
            self.list_sessions.addItem(item)
            self.list_sessions.setItemWidget(
                item, self._build_session_item_widget(raw_peer, payload)
            )
            if selected_peer and raw_peer == selected_peer:
                selected_index = self.list_sessions.count() - 1

        if self.list_sessions.count() == 0:
            self.list_sessions.blockSignals(False)
            self.current_peer = None
            self._apply_session_summary(None, None)
            self._sync_send_state()
            return

        self.list_sessions.setCurrentRow(selected_index)
        current_item = self.list_sessions.currentItem()
        self.list_sessions.blockSignals(False)

        if current_item is None:
            self.current_peer = None
            self._apply_session_summary(None, None)
            self._sync_send_state()
            return

        raw_peer = current_item.data(Qt.UserRole)
        if isinstance(raw_peer, str) and raw_peer:
            self.current_peer = raw_peer
            self._apply_session_summary(raw_peer, self._session_payloads.get(raw_peer))
        self._sync_send_state()
        self._filter_session_list(self.panel_search.text().strip().lower())

    def _session_sort_key(
        self, payload: dict[str, object]
    ) -> tuple[int, int, str, str]:
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
