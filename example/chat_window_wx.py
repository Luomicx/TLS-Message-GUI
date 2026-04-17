import sys
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QFont, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QFrame,
    QMainWindow,
    QPushButton,
    QLineEdit,
    QSpacerItem,
)


class AvatarLabel(QLabel):
    def __init__(self, size=42, color="#888888", text=""):
        super().__init__()
        self._size = size
        self.setFixedSize(size, size)
        self.setText(text)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {color};
                border-radius: {size // 2}px;
                color: white;
                font-weight: bold;
                font-size: 14px;
            }}
        """
        )


class BubbleWidget(QFrame):
    def __init__(self, text="", bg="#3A3A3A", fg="#FFFFFF", max_width=420):
        super().__init__()
        self.setObjectName("bubble")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        label.setOpenExternalLinks(True)
        label.setMaximumWidth(max_width)
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {fg};
                font-size: 15px;
                line-height: 1.5;
                background: transparent;
            }}
        """
        )
        layout.addWidget(label)

        self.setStyleSheet(
            f"""
            QFrame#bubble {{
                background: {bg};
                border-radius: 16px;
            }}
        """
        )


class LinkCardBubble(QFrame):
    def __init__(self, url, title, subtitle, bg="#4A4A4A", fg="#FFFFFF", max_width=430):
        super().__init__()
        self.setObjectName("linkBubble")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(10)

        url_label = QLabel(
            f"<a href='{url}' style='color:#EAEAEA; text-decoration:none;'>{url}</a>"
        )
        url_label.setOpenExternalLinks(True)
        url_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        url_label.setStyleSheet(
            """
            QLabel {
                color: #EAEAEA;
                font-size: 14px;
                background: transparent;
            }
        """
        )
        url_label.setMaximumWidth(max_width)
        root.addWidget(url_label)

        card = QFrame()
        card.setObjectName("previewCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            """
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: 600;
                background: transparent;
            }
        """
        )

        sub_label = QLabel(subtitle)
        sub_label.setWordWrap(True)
        sub_label.setStyleSheet(
            """
            QLabel {
                color: #E5E5E5;
                font-size: 13px;
                background: transparent;
            }
        """
        )

        card_layout.addWidget(title_label)
        card_layout.addWidget(sub_label)
        root.addWidget(card)

        self.setStyleSheet(
            f"""
            QFrame#linkBubble {{
                background: {bg};
                border-radius: 18px;
            }}
            QFrame#previewCard {{
                background: #5A5A5A;
                border-radius: 12px;
            }}
        """
        )


class SystemTipWidget(QWidget):
    def __init__(self, text):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 14, 0, 14)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(text)
        label.setStyleSheet(
            """
            QLabel {
                background: rgba(0, 0, 0, 120);
                color: #CFCFCF;
                border-radius: 12px;
                padding: 6px 14px;
                font-size: 13px;
            }
        """
        )
        layout.addWidget(label)


class MessageItem(QWidget):
    def __init__(
        self, side="left", name="", content_widget=None, avatar_text="", role_tag=None
    ):
        super().__init__()

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 8, 14, 8)
        root.setSpacing(10)

        avatar_color = "#B0B0B0" if side == "left" else "#6B4EFF"
        avatar = AvatarLabel(size=42, color=avatar_color, text=avatar_text)

        name_label = QLabel(name)
        name_label.setStyleSheet(
            """
            QLabel {
                color: #9FA3A9;
                font-size: 13px;
                background: transparent;
            }
        """
        )

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)

        if role_tag:
            tag = QLabel(role_tag)
            tag.setStyleSheet(
                """
                QLabel {
                    background: #007ACC;
                    color: white;
                    border-radius: 8px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                }
            """
            )
            name_row.addWidget(tag)

        name_row.addWidget(name_label)
        name_row.addStretch()

        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(4)
        content_col.addLayout(name_row)
        if content_widget:
            content_col.addWidget(content_widget)

        content_wrap = QWidget()
        content_wrap.setLayout(content_col)

        if side == "left":
            root.addWidget(avatar, 0, Qt.AlignTop)
            root.addWidget(content_wrap, 0, Qt.AlignLeft)
            root.addStretch()
        else:
            root.addStretch()
            root.addWidget(content_wrap, 0, Qt.AlignRight)
            root.addWidget(avatar, 0, Qt.AlignTop)


class ChatArea(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: #1E1F22;")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(2)
        self.layout.addStretch()

    def add_widget(self, widget):
        # 插入到 stretch 之前
        self.layout.insertWidget(self.layout.count() - 1, widget)

    def add_text_message(self, side, name, text, avatar_text="", role_tag=None):
        bubble = BubbleWidget(text=text, bg="#3B3D42" if side == "left" else "#3F4046")
        item = MessageItem(
            side=side,
            name=name,
            content_widget=bubble,
            avatar_text=avatar_text,
            role_tag=role_tag,
        )
        self.add_widget(item)

    def add_link_message(
        self, side, name, url, title, subtitle, avatar_text="", role_tag=None
    ):
        bubble = LinkCardBubble(url=url, title=title, subtitle=subtitle, bg="#4A4A4A")
        item = MessageItem(
            side=side,
            name=name,
            content_widget=bubble,
            avatar_text=avatar_text,
            role_tag=role_tag,
        )
        self.add_widget(item)

    def add_system_tip(self, text):
        self.add_widget(SystemTipWidget(text))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt 聊天界面示例")
        self.resize(1200, 760)

        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 消息滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet(
            """
            QScrollArea {
                background: #1E1F22;
                border: none;
            }
            QScrollBar:vertical {
                background: #1E1F22;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4B4D52;
                min-height: 30px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        )

        self.chat_area = ChatArea()
        self.scroll.setWidget(self.chat_area)

        # 输入区域
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(64)
        bottom_bar.setStyleSheet(
            """
            QFrame {
                background: #25262A;
                border-top: 1px solid #2F3136;
            }
            QLineEdit {
                background: #34363B;
                color: white;
                border: none;
                border-radius: 18px;
                padding: 10px 14px;
                font-size: 14px;
            }
            QPushButton {
                background: #4C84FF;
                color: white;
                border: none;
                border-radius: 16px;
                padding: 8px 18px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #6696FF;
            }
        """
        )
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 12, 16, 12)
        bottom_layout.setSpacing(10)

        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入消息...")
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self.send_demo_message)

        bottom_layout.addWidget(self.input_edit)
        bottom_layout.addWidget(send_btn)

        main_layout.addWidget(self.scroll)
        main_layout.addWidget(bottom_bar)

        self.load_demo_messages()

    def load_demo_messages(self):
        self.chat_area.add_text_message(
            side="left",
            name="王志博",
            text="https://api.siliconflow.cn/v1",
            avatar_text="王",
        )

        self.chat_area.add_text_message(
            side="right",
            name="Evandyr",
            text="vscode下载插件roocode",
            avatar_text="E",
            role_tag="LV20 管理员",
        )

        self.chat_area.add_link_message(
            side="right",
            name="Evandyr",
            url="https://cloud.siliconflow.cn/i/LPPWSNp8",
            title="硅基流动统一登录",
            subtitle="硅基流动用户系统，统一登录 SSO",
            avatar_text="E",
            role_tag="LV20 管理员",
        )

        self.chat_area.add_system_tip("你撤回了一条消息")

        self.chat_area.add_text_message(
            side="right",
            name="Evandyr",
            text="登录注册完成实名认证领取代金券，创建API密钥",
            avatar_text="E",
            role_tag="LV20 管理员",
        )

        self.scroll_to_bottom()

    def send_demo_message(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.chat_area.add_text_message(
            side="right", name="我", text=text, avatar_text="我"
        )
        self.input_edit.clear()
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        QApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
