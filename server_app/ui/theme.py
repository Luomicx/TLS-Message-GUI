from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication, QWidget


@dataclass(frozen=True)
class UiMetrics:
    scale: float
    base_font_px: int
    main_window_size: QSize
    main_window_min_size: QSize
    user_dialog_size: QSize
    user_dialog_min_size: QSize
    add_user_dialog_size: QSize
    add_user_dialog_min_width: int
    root_margin: int
    section_spacing: int
    hero_spacing: int
    card_padding: int
    search_width: int
    port_width: int
    summary_table_row_height: int
    management_table_row_height: int
    summary_avatar_size: int
    management_avatar_size: int
    preview_avatar_size: int


def _fit_to_screen(value: int, minimum: int, screen_limit: int) -> int:
    if screen_limit < minimum:
        return max(screen_limit, 480)
    return max(minimum, min(value, screen_limit))


def _scaled(value: int, scale: float) -> int:
    return max(1, int(round(value * scale)))


def _screen_scale(width: int, height: int) -> float:
    if width >= 2500 or height >= 1500:
        return 1.18
    if width >= 2200 or height >= 1400:
        return 1.12
    if width >= 1900 or height >= 1080:
        return 1.04
    if width <= 1440 or height <= 900:
        return 0.96
    return 1.0


def resolve_ui_metrics() -> UiMetrics:
    app = QApplication.instance()
    width = 1600
    height = 960
    if app is not None and app.primaryScreen() is not None:
        geometry = app.primaryScreen().availableGeometry()
        width = geometry.width()
        height = geometry.height()

    scale = _screen_scale(width, height)
    max_window_width = max(width - 80, 960)
    max_window_height = max(height - 80, 680)

    main_width = _fit_to_screen(int(width * 0.74), 1320, max_window_width)
    main_height = _fit_to_screen(int(height * 0.82), 900, max_window_height)
    user_dialog_width = _fit_to_screen(int(width * 0.60), 1180, max(width - 120, 900))
    user_dialog_height = _fit_to_screen(
        int(height * 0.74), 760, max(height - 120, 620)
    )
    add_dialog_width = _fit_to_screen(int(width * 0.34), 580, max(width - 160, 520))
    add_dialog_height = _fit_to_screen(int(height * 0.52), 500, max(height - 180, 460))

    return UiMetrics(
        scale=scale,
        base_font_px=_scaled(14, scale),
        main_window_size=QSize(main_width, main_height),
        main_window_min_size=QSize(
            _fit_to_screen(int(main_width * 0.82), 1180, main_width),
            _fit_to_screen(int(main_height * 0.82), 780, main_height),
        ),
        user_dialog_size=QSize(user_dialog_width, user_dialog_height),
        user_dialog_min_size=QSize(
            _fit_to_screen(int(user_dialog_width * 0.86), 1040, user_dialog_width),
            _fit_to_screen(int(user_dialog_height * 0.84), 660, user_dialog_height),
        ),
        add_user_dialog_size=QSize(add_dialog_width, add_dialog_height),
        add_user_dialog_min_width=_fit_to_screen(
            int(add_dialog_width * 0.88), 520, add_dialog_width
        ),
        root_margin=_scaled(28, scale),
        section_spacing=_scaled(18, scale),
        hero_spacing=_scaled(22, scale),
        card_padding=_scaled(22, scale),
        search_width=_scaled(340, scale),
        port_width=_scaled(124, scale),
        summary_table_row_height=_scaled(68, scale),
        management_table_row_height=_scaled(60, scale),
        summary_avatar_size=_scaled(56, scale),
        management_avatar_size=_scaled(48, scale),
        preview_avatar_size=_scaled(120, scale),
    )


def build_admin_stylesheet(scale: float = 1.0) -> str:
    values = {
        "base_font": _scaled(14, scale),
        "large_radius": _scaled(24, scale),
        "card_radius": _scaled(20, scale),
        "field_radius": _scaled(12, scale),
        "surface_padding_y": _scaled(10, scale),
        "surface_padding_x": _scaled(16, scale),
        "page_title": _scaled(32, scale),
        "section_title": _scaled(22, scale),
        "subtitle_font": _scaled(14, scale),
        "metric_title": _scaled(13, scale),
        "metric_value": _scaled(30, scale),
        "badge_font": _scaled(14, scale),
        "badge_padding_y": _scaled(8, scale),
        "badge_padding_x": _scaled(16, scale),
        "chip_padding_y": _scaled(6, scale),
        "chip_padding_x": _scaled(14, scale),
        "button_padding_y": _scaled(12, scale),
        "button_padding_x": _scaled(18, scale),
        "button_min_height": _scaled(44, scale),
        "field_padding_y": _scaled(9, scale),
        "field_padding_x": _scaled(12, scale),
        "field_min_height": _scaled(44, scale),
        "field_button_width": _scaled(24, scale),
        "text_radius": _scaled(16, scale),
        "header_padding_y": _scaled(12, scale),
        "header_padding_x": _scaled(14, scale),
        "groupbox_radius": _scaled(16, scale),
        "groupbox_margin_top": _scaled(16, scale),
        "groupbox_padding_top": _scaled(16, scale),
        "groupbox_title_left": _scaled(14, scale),
        "groupbox_title_padding": _scaled(6, scale),
        "checkbox_gap": _scaled(8, scale),
        "checkbox_size": _scaled(18, scale),
        "checkbox_radius": _scaled(5, scale),
        "scrollbar_size": _scaled(12, scale),
        "scrollbar_margin": _scaled(6, scale),
        "scrollbar_side_margin": _scaled(2, scale),
        "scrollbar_radius": _scaled(6, scale),
        "scrollbar_handle_min": _scaled(40, scale),
        "status_min_height": _scaled(34, scale),
    }

    template = Template(
        """
QWidget {
    background: #f3f6fb;
    color: #1f2937;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: ${base_font}px;
}

QMainWindow, QDialog {
    background: #f3f6fb;
}

QFrame#heroCard {
    background: qlineargradient(
        x1: 0,
        y1: 0,
        x2: 1,
        y2: 1,
        stop: 0 #f8fbff,
        stop: 0.5 #eef4fc,
        stop: 1 #e6eef9
    );
    border: 1px solid #d9e4f2;
    border-radius: ${large_radius}px;
}

QFrame#surfaceCard,
QFrame#statCard {
    background: #ffffff;
    border: 1px solid #d9e4f2;
    border-radius: ${card_radius}px;
}

QLabel#pageTitle {
    background: transparent;
    color: #0f172a;
    font-size: ${page_title}px;
    font-weight: 700;
}

QLabel#sectionTitle {
    background: transparent;
    color: #0f172a;
    font-size: ${section_title}px;
    font-weight: 700;
}

QLabel#pageSubtitle,
QLabel#sectionSubtitle,
QLabel#hintText,
QLabel#detailKey {
    background: transparent;
    color: #526071;
    font-size: ${subtitle_font}px;
}

QLabel#metricTitle {
    background: transparent;
    color: #526071;
    font-size: ${metric_title}px;
    font-weight: 600;
    letter-spacing: 0.5px;
}

QLabel#metricValue {
    background: transparent;
    color: #0f172a;
    font-size: ${metric_value}px;
    font-weight: 700;
}

QLabel#metricHint,
QLabel#detailValue {
    background: transparent;
    color: #334155;
}

QLabel#statusBadge {
    border-radius: 999px;
    padding: ${badge_padding_y}px ${badge_padding_x}px;
    font-size: ${badge_font}px;
    font-weight: 700;
}

QLabel#statusBadge[state="running"] {
    background: #dcfce7;
    color: #166534;
    border: 1px solid #bbf7d0;
}

QLabel#statusBadge[state="stopped"] {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
}

QLabel#softChip {
    background: rgba(255, 255, 255, 0.75);
    color: #1d4ed8;
    border: 1px solid #dbeafe;
    border-radius: 999px;
    padding: ${chip_padding_y}px ${chip_padding_x}px;
    font-weight: 600;
}

QLabel#summaryBadge {
    background: #eff6ff;
    color: #1e40af;
    border: 1px solid #dbeafe;
    border-radius: 999px;
    padding: ${chip_padding_y}px ${chip_padding_x}px;
    font-size: ${badge_font}px;
    font-weight: 600;
}

QPushButton {
    background: #eef3fb;
    color: #0f172a;
    border: 1px solid #d5deea;
    border-radius: ${field_radius}px;
    min-height: ${button_min_height}px;
    padding: ${button_padding_y}px ${button_padding_x}px;
    font-weight: 600;
}

QPushButton:hover {
    background: #e3ecf8;
    border-color: #c7d5e8;
}

QPushButton:pressed {
    background: #d7e4f5;
}

QPushButton[role="primary"] {
    background: #1d4ed8;
    color: #ffffff;
    border-color: #1d4ed8;
}

QPushButton[role="primary"]:hover {
    background: #1e40af;
    border-color: #1e40af;
}

QPushButton[role="danger"] {
    background: #c2410c;
    color: #ffffff;
    border-color: #c2410c;
}

QPushButton[role="danger"]:hover {
    background: #9a3412;
    border-color: #9a3412;
}

QPushButton[role="success"] {
    background: #0f766e;
    color: #ffffff;
    border-color: #0f766e;
}

QPushButton[role="success"]:hover {
    background: #115e59;
    border-color: #115e59;
}

QLineEdit,
QSpinBox,
QComboBox {
    background: #ffffff;
    border: 1px solid #d5deea;
    border-radius: ${field_radius}px;
    min-height: ${field_min_height}px;
    padding: ${field_padding_y}px ${field_padding_x}px;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
}

QLineEdit:focus,
QSpinBox:focus,
QComboBox:focus {
    border: 2px solid #2563eb;
}

QSpinBox::up-button,
QSpinBox::down-button,
QComboBox::drop-down {
    width: ${field_button_width}px;
    border: none;
}

QTextEdit,
QTableWidget {
    background: #ffffff;
    border: 1px solid #d9e4f2;
    border-radius: ${text_radius}px;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
    gridline-color: #e2e8f0;
}

QTextEdit {
    padding: ${surface_padding_y}px ${surface_padding_x}px;
}

QTableWidget {
    alternate-background-color: #f8fbff;
}

QHeaderView::section {
    background: #f3f7fd;
    color: #334155;
    padding: ${header_padding_y}px ${header_padding_x}px;
    border: none;
    border-bottom: 1px solid #d9e4f2;
    font-weight: 700;
}

QTableCornerButton::section {
    background: #f3f7fd;
    border: none;
    border-bottom: 1px solid #d9e4f2;
}

QGroupBox {
    background: #ffffff;
    border: 1px solid #d9e4f2;
    border-radius: ${groupbox_radius}px;
    margin-top: ${groupbox_margin_top}px;
    padding-top: ${groupbox_padding_top}px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: ${groupbox_title_left}px;
    padding: 0 ${groupbox_title_padding}px;
    color: #0f172a;
}

QCheckBox {
    spacing: ${checkbox_gap}px;
}

QCheckBox::indicator {
    width: ${checkbox_size}px;
    height: ${checkbox_size}px;
}

QCheckBox::indicator:unchecked {
    border: 1px solid #c7d2e1;
    background: #ffffff;
    border-radius: ${checkbox_radius}px;
}

QCheckBox::indicator:checked {
    border: 1px solid #1d4ed8;
    background: #1d4ed8;
    border-radius: ${checkbox_radius}px;
}

QSplitter::handle {
    background: transparent;
}

QScrollBar:vertical {
    width: ${scrollbar_size}px;
    background: transparent;
    margin: ${scrollbar_margin}px ${scrollbar_side_margin}px ${scrollbar_margin}px ${scrollbar_side_margin}px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: ${scrollbar_radius}px;
    min-height: ${scrollbar_handle_min}px;
}

QScrollBar:horizontal {
    height: ${scrollbar_size}px;
    background: transparent;
    margin: ${scrollbar_side_margin}px ${scrollbar_margin}px ${scrollbar_side_margin}px ${scrollbar_margin}px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: ${scrollbar_radius}px;
    min-width: ${scrollbar_handle_min}px;
}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {
    background: transparent;
    border: none;
}

QStatusBar {
    background: #eff4fb;
    color: #475569;
    min-height: ${status_min_height}px;
    border-top: 1px solid #d9e4f2;
}
"""
    )
    return template.substitute(values)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
