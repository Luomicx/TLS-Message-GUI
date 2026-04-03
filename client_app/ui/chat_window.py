from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .theme import apply_app_style, make_header_block, make_icon_placeholder, make_logo_badge


class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("安全网络聊天工具 - 客户端")
        self.resize(1220, 760)
        apply_app_style(self)
        self._build_ui()
        self._load_mock_data()

    def _build_ui(self) -> None:
        page = QFrame()
        page.setObjectName("page")
        self.setCentralWidget(page)

        root = QHBoxLayout(page)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        self.sidebar = self._build_sidebar()
        self.content = self._build_content()

        root.addWidget(self.sidebar, 0)
        root.addWidget(self.content, 1)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        panel.setFixedWidth(320)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(make_logo_badge())

        user_block = QVBoxLayout()
        name = QLabel("当前用户")
        name.setObjectName("sectionTitle")
        name.setStyleSheet("font-size: 18px;")
        user_id = QLabel("Id: 10001")
        user_id.setObjectName("mutedLabel")
        security = QLabel("安全状态占位")
        security.setObjectName("securityTag")
        user_block.addWidget(name)
        user_block.addWidget(user_id)
        user_block.addWidget(security, 0, Qt.AlignLeft)
        header.addLayout(user_block, 1)

        layout.addLayout(header)

        nav_row = QHBoxLayout()
        self.btn_chat = QPushButton("聊天")
        self.btn_chat.setObjectName("primaryButton")
        self.btn_friend = QPushButton("好友")
        self.btn_friend.setObjectName("ghostButton")
        self.btn_search = QPushButton("搜索")
        self.btn_search.setObjectName("ghostButton")
        self.btn_chat.clicked.connect(lambda: self.switch_page(0))
        self.btn_friend.clicked.connect(lambda: self.switch_page(1))
        self.btn_search.clicked.connect(lambda: self.switch_page(2))
        nav_row.addWidget(self.btn_chat)
        nav_row.addWidget(self.btn_friend)
        nav_row.addWidget(self.btn_search)
        layout.addLayout(nav_row)

        section_title = QLabel("最近会话")
        section_title.setObjectName("mutedLabel")
        layout.addWidget(section_title)

        self.list_sessions = QListWidget()
        self.list_sessions.setObjectName("sessionList")
        self.list_sessions.currentRowChanged.connect(self._on_session_changed)
        layout.addWidget(self.list_sessions, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(make_icon_placeholder("退", 24))
        bottom.addWidget(QLabel("注销并返回登录页"))
        bottom.addStretch(1)
        self.btn_logout = QPushButton("注销")
        self.btn_logout.setObjectName("ghostButton")
        bottom.addWidget(self.btn_logout)
        layout.addLayout(bottom)
        return panel

    def _build_content(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.stacked = QStackedWidget()
        self.page_chat = self._build_chat_page()
        self.page_friends = self._build_friends_page()
        self.page_search = self._build_search_page()
        self.stacked.addWidget(self.page_chat)
        self.stacked.addWidget(self.page_friends)
        self.stacked.addWidget(self.page_search)

        layout.addWidget(self.stacked, 1)
        return container

    def _build_chat_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("张三")
        title.setObjectName("sectionTitle")
        title.setStyleSheet("font-size: 20px;")
        subtitle = QLabel("在线状态占位 · 最近一次活跃 10:24")
        subtitle.setObjectName("mutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch(1)
        top.addWidget(make_icon_placeholder("语", 24))
        top.addWidget(make_icon_placeholder("图", 24))
        layout.addLayout(top)

        divider = QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)

        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        self.message_area.setStyleSheet(
            "background: #f8fafb; border: 1px solid #e3e9ee; border-radius: 18px; padding: 12px;"
        )
        layout.addWidget(self.message_area, 1)

        editor_card = QFrame()
        editor_card.setObjectName("card")
        editor_card.setStyleSheet(
            "QFrame#card { background: rgba(255,255,255,248); border: 1px solid #e3e9ee; border-radius: 18px; }"
        )
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(16, 16, 16, 16)
        editor_layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.addWidget(make_icon_placeholder("表", 24))
        toolbar.addWidget(make_icon_placeholder("附", 24))
        toolbar.addWidget(make_icon_placeholder("图", 24))
        toolbar.addStretch(1)
        draft_hint = QLabel("消息加密状态占位")
        draft_hint.setObjectName("securityTag")
        toolbar.addWidget(draft_hint)
        editor_layout.addLayout(toolbar)

        self.edit_message = QTextEdit()
        self.edit_message.setPlaceholderText("输入消息内容，后续将通过服务端转发")
        self.edit_message.setFixedHeight(120)
        self.edit_message.setStyleSheet(
            "background: #f8fafb; border: 1px solid #d8e0e6; border-radius: 14px; padding: 10px;"
        )
        editor_layout.addWidget(self.edit_message)

        action_row = QHBoxLayout()
        state = QLabel("连接状态：未连接")
        state.setObjectName("mutedLabel")
        action_row.addWidget(state)
        action_row.addStretch(1)
        self.btn_send = QPushButton("发送")
        self.btn_send.setObjectName("primaryButton")
        action_row.addWidget(self.btn_send)
        editor_layout.addLayout(action_row)

        layout.addWidget(editor_card)
        return page

    def _build_friends_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(make_header_block("好友列表", "展示已有好友、在线状态和后续聊天入口。"))

        self.list_friends = QListWidget()
        self.list_friends.setStyleSheet(
            "background: #f8fafb; border: 1px solid #e3e9ee; border-radius: 18px; padding: 8px;"
        )
        layout.addWidget(self.list_friends, 1)

        footer = QHBoxLayout()
        footer.addWidget(QLabel("双击好友可切换到聊天窗口（交互预留）"))
        footer.addStretch(1)
        self.btn_add_friend = QPushButton("添加好友")
        self.btn_add_friend.setObjectName("ghostButton")
        footer.addWidget(self.btn_add_friend)
        layout.addLayout(footer)
        return page

    def _build_search_page(self) -> QWidget:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            make_header_block(
                "搜索与添加好友",
                "支持昵称模糊搜索和 Id 精准搜索。当前先完成静态结构与空状态展示。",
            )
        )

        search_bar = QHBoxLayout()
        self.btn_mode_nickname = QPushButton("昵称搜索")
        self.btn_mode_nickname.setObjectName("primaryButton")
        self.btn_mode_id = QPushButton("Id 搜索")
        self.btn_mode_id.setObjectName("ghostButton")
        self.btn_trigger_search = QPushButton("开始搜索")
        self.btn_trigger_search.setObjectName("ghostButton")
        search_bar.addWidget(self.btn_mode_nickname)
        search_bar.addWidget(self.btn_mode_id)
        search_bar.addStretch(1)
        search_bar.addWidget(self.btn_trigger_search)
        layout.addLayout(search_bar)

        self.list_search_result = QListWidget()
        self.list_search_result.setStyleSheet(
            "background: #f8fafb; border: 1px solid #e3e9ee; border-radius: 18px; padding: 8px;"
        )
        layout.addWidget(self.list_search_result, 1)

        state = QLabel("空状态：请输入昵称或 Id 后开始搜索")
        state.setObjectName("mutedLabel")
        layout.addWidget(state)
        return page

    def _load_mock_data(self) -> None:
        for session in ["张三", "李四", "项目讨论组", "安全测试"]:
            self.list_sessions.addItem(QListWidgetItem(session))

        for friend in ["张三  · 在线", "李四  · 离线", "王五  · 忙碌"]:
            self.list_friends.addItem(QListWidgetItem(friend))

        for result in [
            "昵称: 小明 · Id: 10010 · 可添加",
            "昵称: 测试用户 · Id: 10025 · 等待服务端搜索协议",
        ]:
            self.list_search_result.addItem(QListWidgetItem(result))

        self.list_sessions.setCurrentRow(0)
        self.message_area.setHtml(
            """
            <div style='color:#8a97a3; text-align:center; margin:12px 0;'>10:24</div>
            <div style='margin: 10px 0; text-align:left;'>
              <span style='display:inline-block; background:#ffffff; border:1px solid #e1e8ed; border-radius:14px; padding:10px 14px;'>你好，聊天窗口 UI 已经搭好了。</span>
            </div>
            <div style='margin: 10px 0; text-align:right;'>
              <span style='display:inline-block; background:#dff6e8; border:1px solid #c9ead8; border-radius:14px; padding:10px 14px;'>收到，接下来接入通信协议。</span>
            </div>
            """
        )

    def switch_page(self, index: int) -> None:
        self.stacked.setCurrentIndex(index)
        self.btn_chat.setObjectName("ghostButton")
        self.btn_friend.setObjectName("ghostButton")
        self.btn_search.setObjectName("ghostButton")
        if index == 0:
            self.btn_chat.setObjectName("primaryButton")
        elif index == 1:
            self.btn_friend.setObjectName("primaryButton")
        else:
            self.btn_search.setObjectName("primaryButton")
        apply_app_style(self)

    def _on_session_changed(self, row: int) -> None:
        if row < 0:
            return
        name = self.list_sessions.item(row).text()
        self.statusBar().showMessage(f"当前会话：{name}")
