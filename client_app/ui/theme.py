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

FONT_SIZE_SMALL = 16
FONT_SIZE_NORMAL = 18
FONT_SIZE_LARGE = 20
FONT_SIZE_XLARGE = 22

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
    combo.addItem("100%", userData=FONT_SIZE_SMALL)
    combo.addItem("115%", userData=FONT_SIZE_NORMAL)
    combo.addItem("130%", userData=FONT_SIZE_LARGE)
    combo.addItem("145%", userData=FONT_SIZE_XLARGE)

    values = [FONT_SIZE_SMALL, FONT_SIZE_NORMAL, FONT_SIZE_LARGE, FONT_SIZE_XLARGE]
    current = get_font_size()
    combo.setCurrentIndex(values.index(current) if current in values else 1)
    combo.currentIndexChanged.connect(
        lambda index: set_font_size(combo.itemData(index))
    )

    layout.addWidget(combo)
    return container, combo


def make_logo_badge() -> QWidget:
    card = CardWidget()
    card.setFixedSize(64, 64)  # 微信头像通常更小更紧凑
    layout = QVBoxLayout(card)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(0)

    logo = QLabel(card)
    logo.setAlignment(Qt.AlignCenter)
    pixmap = QPixmap(str(LOGO_PATH))
    if not pixmap.isNull():
        logo.setPixmap(
            pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
    else:
        fallback = TitleLabel(card)
        fallback.setAlignment(Qt.AlignCenter)
        fallback.setText("SI")
        fallback.setStyleSheet("color: #1677FF;")
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
    # 这是实现微信蓝白风格的核心
    return """
    QMainWindow, QDialog {
        background: #FFFFFF; /* 全局底层纯白 */
    }
    QFrame#page, QWidget#page {
        background: transparent;
    }
    
    /* 侧边栏/功能区的卡片：纯白，加极淡的边框区分 */
    CardWidget#sectionCard {
        background: #FFFFFF;
        border: 1px solid #EBEBEB;
        border-radius: 6px; /* 减小圆角，显得更专业干练 */
    }
    
    /* Logo 徽标：去底色，融入背景 */
    CardWidget#brandBadge {
        background: transparent;
        border: none;
        border-radius: 6px;
    }
    
    /* 聊天页面的顶部信息栏：白底，底部有一条细线分割 */
    CardWidget#chatHero {
        background: #FFFFFF;
        border: none;
        border-bottom: 1px solid #EBEBEB;
        border-radius: 0px; 
    }
    
    /* 聊天记录展示区：微信特色的浅灰底色，无边框 */
    TextEdit#transcriptView {
        background: #F5F6F7; /* 微信常用的浅灰底色 */
        border: none;
        border-radius: 0px;
        padding: 16px;
        selection-background-color: #1677FF;
        selection-color: #FFFFFF;
    }
    
    /* 隐藏额外的面板背景 */
    QFrame#panel {
        background: transparent;
    }
    
    /* 底部状态栏融入界面 */
    QStatusBar {
        background: #FFFFFF;
        border-top: 1px solid #EBEBEB;
        color: #666666;
    }
    """
