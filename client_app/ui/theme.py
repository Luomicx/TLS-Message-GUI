from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
    Theme,
    TitleLabel,
    ToolButton,
    TransparentPushButton,
    setFont,
    setTheme,
    setThemeColor,
)

FONT_SIZE_SMALL = 13
FONT_SIZE_NORMAL = 14
FONT_SIZE_LARGE = 15
FONT_SIZE_XLARGE = 17

WECHAT_GREEN = "#95EC69"

_current_font_size = FONT_SIZE_NORMAL
_theme_initialized = False
LOGO_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "北华航天工业学院-logo-512px.png"
)

TLineEdit = TypeVar("TLineEdit", LineEdit, PasswordLineEdit)


class ThemeController(QObject):
    theme_changed = pyqtSignal()


theme_controller = ThemeController()


def initialize_fluent_theme() -> None:
    global _theme_initialized
    if _theme_initialized:
        return
    setTheme(Theme.LIGHT)
    # 使用干净现代的亮蓝色作为主色调（类似企业微信或钉钉的蓝白分割）
    setThemeColor("#1677FF")
    _theme_initialized = True


def apply_app_style(widget: QWidget) -> None:
    initialize_fluent_theme()
    widget.setStyleSheet(_window_stylesheet())
    _apply_font_recursive(widget)


def _apply_font_recursive(widget: QWidget) -> None:
    setFont(widget, get_font_size())
    for child in widget.findChildren(QWidget):
        setFont(child, get_font_size())


def get_font_size() -> int:
    return _current_font_size


def set_font_size(size: int) -> None:
    global _current_font_size
    if size == _current_font_size:
        return
    _current_font_size = size
    theme_controller.theme_changed.emit()


def make_font_size_combo() -> tuple[QWidget, QComboBox]:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    combo = ComboBox()
    combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    combo.addItem("90%", userData=FONT_SIZE_SMALL)
    combo.addItem("100%", userData=FONT_SIZE_NORMAL)
    combo.addItem("110%", userData=FONT_SIZE_LARGE)
    combo.addItem("120%", userData=FONT_SIZE_XLARGE)

    values = [FONT_SIZE_SMALL, FONT_SIZE_NORMAL, FONT_SIZE_LARGE, FONT_SIZE_XLARGE]
    current = get_font_size()
    combo.setCurrentIndex(values.index(current) if current in values else 1)
    combo.currentIndexChanged.connect(
        lambda index: set_font_size(combo.itemData(index))
    )

    layout.addWidget(combo)
    return container, combo


def make_logo_badge(size: int = 64) -> QWidget:
    card = CardWidget()
    card.setFixedSize(size, size)
    layout = QVBoxLayout(card)
    inner_padding = max(2, size // 24)
    layout.setContentsMargins(inner_padding, inner_padding, inner_padding, inner_padding)
    layout.setSpacing(0)

    logo = QLabel(card)
    logo.setAlignment(Qt.AlignCenter)
    pixmap = QPixmap(str(LOGO_PATH))
    if not pixmap.isNull():
        available_size = min(
            size - inner_padding * 2,
            pixmap.width(),
            pixmap.height(),
        )
        logo.setPixmap(
            pixmap.scaled(
                available_size,
                available_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
    else:
        fallback = TitleLabel(card)
        fallback.setAlignment(Qt.AlignCenter)
        fallback.setText("SI")
        fallback.setStyleSheet(
            f"color: #1677FF; font-size: {max(18, int(size * 0.32))}px; font-weight: 700;"
        )
        layout.addStretch(1)
        layout.addWidget(fallback)
        layout.addStretch(1)
        card.setObjectName("brandBadge")
        return card

    layout.addStretch(1)
    layout.addWidget(logo)
    layout.addStretch(1)
    card.setObjectName("brandBadge")
    card.setToolTip("北华航天工业学院")
    return card


def make_icon_placeholder(text: str, size: int = 28) -> QWidget:
    button = ToolButton()
    button.setIcon(FIF.CHAT)
    button.setText(text)
    button.setFixedSize(size + 10, size + 10)
    return button


_AVATAR_COLORS = [
    "#1677FF", "#52C41A", "#FA8C16", "#722ED1",
    "#EB2F96", "#13C2C2", "#FAAD14", "#2F54EB",
]


def _avatar_color_for(text: str) -> str:
    idx = sum(ord(ch) for ch in text) % len(_AVATAR_COLORS)
    return _AVATAR_COLORS[idx]


def make_avatar_placeholder(text: str, size: int = 40) -> QWidget:
    container = QWidget()
    container.setFixedSize(size, size)
    color = _avatar_color_for(text)
    letter = text[0].upper() if text else "?"
    container.setStyleSheet(
        f"background:{color};border-radius:{size // 2}px;"
    )
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    label = QLabel(container)
    label.setAlignment(Qt.AlignCenter)
    label.setText(letter)
    label.setStyleSheet(
        f"color:white;font-size:{int(size * 0.45)}px;font-weight:bold;background:transparent;"
    )
    layout.addWidget(label)
    container.setAttribute(Qt.WA_TransparentForMouseEvents)
    return container


def make_nav_button(icon: FIF, tooltip: str) -> ToolButton:
    btn = ToolButton()
    btn.setIcon(icon)
    btn.setToolTip(tooltip)
    btn.setFixedSize(42, 42)
    btn.setStyleSheet(
        "ToolButton { background:transparent; border:none; border-radius:6px; }"
        "ToolButton:hover { background:#3D3D3D; }"
        "ToolButton[navSelected='true'] { background:#3D3D3D; }"
    )
    return btn


def make_header_block(title: str, subtitle: str) -> QWidget:
    block = QWidget()
    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)  # 缩减间距，使其更紧凑

    title_label = TitleLabel(block)
    title_label.setWordWrap(True)
    title_label.setText(title)

    subtitle_label = CaptionLabel(block)  # 微信的副标题通常更小、颜色更淡
    subtitle_label.setStyleSheet("color: #999999;")
    subtitle_label.setWordWrap(True)
    subtitle_label.setText(subtitle)

    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return block


def make_labeled_input(
    label_text: str, placeholder: str, *, password: bool = False
) -> tuple[QWidget, TLineEdit]:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    label = BodyLabel(container)
    label.setWordWrap(True)
    label.setText(label_text)

    edit: TLineEdit
    if password:
        edit = PasswordLineEdit(container)
    else:
        edit = LineEdit(container)
    edit.setPlaceholderText(placeholder)
    edit.setMinimumHeight(40)  # 高度适度调低，符合桌面端习惯

    layout.addWidget(label)
    layout.addWidget(edit)
    return container, edit


def make_primary_action(text: str, icon=FIF.SEND) -> PrimaryPushButton:
    button = PrimaryPushButton()
    button.setText(text)
    button.setIcon(icon)
    button.setMinimumHeight(40)
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return button


def make_secondary_action(text: str, icon=FIF.ADD) -> PushButton:
    button = PushButton()
    button.setText(text)
    button.setIcon(icon)
    button.setMinimumHeight(40)
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return button


def make_link_action(text: str, icon=FIF.LINK) -> TransparentPushButton:
    button = TransparentPushButton()
    button.setText(text)
    button.setIcon(icon)
    button.setMinimumHeight(40)
    button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return button


def make_section_card() -> CardWidget:
    card = CardWidget()
    card.setObjectName("sectionCard")
    return card


def wrap_in_panel(widget: QWidget) -> QFrame:
    panel = QFrame()
    panel.setObjectName("panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    return panel


def make_checkbox(text: str) -> CheckBox:
    box = CheckBox()
    box.setText(text)
    return box


def _window_stylesheet() -> str:
    return """
    QMainWindow, QDialog {
        background: #F5F5F5;
    }
    QFrame#page, QWidget#page {
        background: transparent;
    }

    /* 导航栏 */
    QWidget#navRail {
        background: #2E2E2E;
        border-right: 1px solid #1A1A1A;
    }

    /* 中间面板 */
    QWidget#middlePanel {
        background: #E7E7E7;
        border-right: 1px solid #D0D0D0;
    }

    /* 聊天区 */
    QWidget#chatArea {
        background: #F5F5F5;
    }

    /* 侧边栏/功能区的卡片 */
    CardWidget#sectionCard {
        background: #FFFFFF;
        border: 1px solid #EBEBEB;
        border-radius: 6px;
    }

    /* Logo 徽标 */
    CardWidget#brandBadge {
        background: transparent;
        border: none;
        border-radius: 6px;
    }

    /* 聊天页面的顶部信息栏 */
    QWidget#chatHeader {
        background: #F5F5F5;
        border-bottom: 1px solid #D9D9D9;
    }

    /* 聊天记录展示区 */
    TextEdit#transcriptView {
        background: #F5F5F5;
        border: none;
        border-radius: 0px;
        padding: 12px;
        selection-background-color: #1677FF;
        selection-color: #FFFFFF;
    }

    /* 输入区 */
    QWidget#composer {
        background: #F5F5F5;
        border-top: 1px solid #D9D9D9;
    }

    /* 中间面板搜索框 */
    SearchLineEdit#panelSearch {
        background: #E7E7E7;
        border: none;
        border-radius: 4px;
    }

    /* 隐藏额外的面板背景 */
    QFrame#panel {
        background: transparent;
    }

    /* 底部状态栏 */
    QStatusBar {
        background: #F5F5F5;
        border-top: 1px solid #D9D9D9;
        color: #666666;
    }

    /* 中间面板列表项 hover */
    QListWidget#sessionList, QListWidget#friendList, QListWidget#searchResultList {
        background: #E7E7E7;
        border: none;
        outline: none;
    }
    QListWidget#sessionList::item:hover,
    QListWidget#friendList::item:hover,
    QListWidget#searchResultList::item:hover {
        background: #D9D9D9;
    }
    QListWidget#sessionList::item:selected,
    QListWidget#friendList::item:selected,
    QListWidget#searchResultList::item:selected {
        background: #C9C9C9;
    }
    """
