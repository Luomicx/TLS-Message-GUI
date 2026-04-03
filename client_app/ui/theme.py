from __future__ import annotations

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import ComboBox, Theme, setFont, setTheme

FONT_SIZE_SMALL = 16
FONT_SIZE_NORMAL = 18
FONT_SIZE_LARGE = 20
FONT_SIZE_XLARGE = 22

_current_font_size = FONT_SIZE_NORMAL


class ThemeController(QObject):
    theme_changed = pyqtSignal()


theme_controller = ThemeController()


def initialize_fluent_theme() -> None:
    setTheme(Theme.LIGHT)


def apply_app_style(widget: QWidget) -> None:
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
