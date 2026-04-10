from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..db import Database, normalize_encoding_rule
from .add_user_dialog import AddUserDialog
from .avatar import make_placeholder_avatar, pixmap_from_avatar_blob
from .theme import build_admin_stylesheet, repolish, resolve_ui_metrics

COL_ID = 0
COL_USERNAME = 1
COL_AVATAR = 2
COL_PASSWORD = 3
COL_ENCODING = 4
COL_LOCKED = 5
COL_CREATED = 6


class UserManagementDialog(QDialog):
    def __init__(self, *, parent=None, db: Database):
        super().__init__(parent)
        self.db = db
        self.ui_metrics = resolve_ui_metrics()

        self.setWindowTitle("用户管理")
        self.resize(self.ui_metrics.user_dialog_size)
        self.setMinimumSize(self.ui_metrics.user_dialog_min_size)
        self.setStyleSheet(build_admin_stylesheet(self.ui_metrics.scale))

        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        root.setSpacing(self.ui_metrics.section_spacing)

        header_card = self._build_header_card()
        table_card = self._build_table_card()

        root.addWidget(header_card)
        root.addWidget(table_card, 1)

    def _build_header_card(self):
        from PyQt5.QtWidgets import QFrame

        card = QFrame()
        card.setObjectName("surfaceCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(self.ui_metrics.section_spacing)

        title = QLabel("账号管理中心")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("支持筛选、编辑、锁定和头像维护，适合作为管理员日常操作入口。")
        subtitle.setObjectName("sectionSubtitle")
        subtitle.setWordWrap(True)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(max(10, self.ui_metrics.section_spacing // 2))
        self.lbl_total_badge = QLabel("总账号 0")
        self.lbl_total_badge.setObjectName("summaryBadge")
        self.lbl_active_badge = QLabel("正常 0")
        self.lbl_active_badge.setObjectName("summaryBadge")
        self.lbl_locked_badge = QLabel("锁定 0")
        self.lbl_locked_badge.setObjectName("summaryBadge")
        self.lbl_visible_badge = QLabel("显示 0 / 0")
        self.lbl_visible_badge.setObjectName("summaryBadge")
        for widget in (
            self.lbl_total_badge,
            self.lbl_active_badge,
            self.lbl_locked_badge,
            self.lbl_visible_badge,
        ):
            badge_row.addWidget(widget)
        badge_row.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setSpacing(max(10, self.ui_metrics.section_spacing // 2))

        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("搜索用户 ID、用户名或编码规则")
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._apply_filters)
        self.edit_search.setMinimumWidth(self.ui_metrics.search_width)
        action_row.addWidget(self.edit_search, 1)

        self.combo_status = QComboBox()
        self.combo_status.addItem("全部状态", "all")
        self.combo_status.addItem("仅正常", "active")
        self.combo_status.addItem("仅锁定", "locked")
        self.combo_status.currentIndexChanged.connect(self._apply_filters)
        action_row.addWidget(self.combo_status)

        btn_add = QPushButton("新增用户")
        btn_add.setIcon(self.style().standardIcon(self.style().SP_FileDialogNewFolder))
        btn_add.clicked.connect(self.add_user)
        btn_add.setProperty("role", "primary")
        repolish(btn_add)
        action_row.addWidget(btn_add)

        btn_delete = QPushButton("删除用户")
        btn_delete.setIcon(self.style().standardIcon(self.style().SP_TrashIcon))
        btn_delete.clicked.connect(self.delete_selected)
        btn_delete.setProperty("role", "danger")
        repolish(btn_delete)
        action_row.addWidget(btn_delete)

        btn_reload = QPushButton("刷新列表")
        btn_reload.setIcon(self.style().standardIcon(self.style().SP_BrowserReload))
        btn_reload.clicked.connect(self.reload)
        btn_reload.setProperty("role", "success")
        repolish(btn_reload)
        action_row.addWidget(btn_reload)

        btn_close = QPushButton("关闭")
        btn_close.setIcon(self.style().standardIcon(self.style().SP_DialogCloseButton))
        btn_close.clicked.connect(self.accept)
        action_row.addWidget(btn_close)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(badge_row)
        layout.addLayout(action_row)
        return card

    def _build_table_card(self):
        from PyQt5.QtWidgets import QFrame

        card = QFrame()
        card.setObjectName("surfaceCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
            self.ui_metrics.card_padding,
            self.ui_metrics.card_padding - 4,
        )
        layout.setSpacing(max(12, self.ui_metrics.section_spacing // 2))

        tip = QLabel(
            "双击头像列可以更换头像；双击用户名、密码或编码规则列可直接编辑；锁定列通过勾选切换。"
        )
        tip.setObjectName("hintText")
        tip.setWordWrap(True)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["用户 ID", "用户名", "头像", "密码", "编码规则", "锁定", "创建时间"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setIconSize(
            QSize(
                self.ui_metrics.management_avatar_size,
                self.ui_metrics.management_avatar_size,
            )
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(
            self.ui_metrics.management_table_row_height
        )
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(tip)
        layout.addWidget(self.table, 1)
        return card

    def reload(self) -> None:
        rows = self.db.list_users()

        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            for row in rows:
                self._append_row(row)
        finally:
            self.table.blockSignals(False)

        self.table.setColumnWidth(COL_AVATAR, self.ui_metrics.management_avatar_size + 28)
        self.table.setColumnWidth(COL_PASSWORD, max(86, int(94 * self.ui_metrics.scale)))
        self.table.setColumnWidth(COL_LOCKED, max(64, int(72 * self.ui_metrics.scale)))

        self._refresh_summary_badges()
        self._apply_filters()

    def _append_row(self, row_data: sqlite3.Row) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        user_id = int(row_data["id"])
        username = str(row_data["username"])
        avatar_blob = row_data["avatar"]
        encoding_json = str(row_data["encoding_rule"])
        locked = int(row_data["locked"])
        created_at = str(row_data["created_at"])

        it_id = QTableWidgetItem(str(user_id))
        it_id.setFlags(it_id.flags() & ~Qt.ItemIsEditable)
        it_id.setData(Qt.UserRole, user_id)
        self.table.setItem(row, COL_ID, it_id)

        it_name = QTableWidgetItem(username)
        it_name.setData(Qt.UserRole, username)
        self.table.setItem(row, COL_USERNAME, it_name)

        pm = (
            pixmap_from_avatar_blob(
                bytes(avatar_blob), size=self.ui_metrics.management_avatar_size
            )
            if avatar_blob
            else make_placeholder_avatar(
                username, size=self.ui_metrics.management_avatar_size
            )
        )
        it_avatar = QTableWidgetItem("")
        it_avatar.setIcon(QIcon(pm))
        it_avatar.setFlags(it_avatar.flags() & ~Qt.ItemIsEditable)
        it_avatar.setData(
            Qt.UserRole, b"" if avatar_blob is None else bytes(avatar_blob)
        )
        self.table.setItem(row, COL_AVATAR, it_avatar)

        it_pwd = QTableWidgetItem("******")
        it_pwd.setData(Qt.UserRole, "******")
        self.table.setItem(row, COL_PASSWORD, it_pwd)

        it_enc = QTableWidgetItem(self._encoding_json_to_text(encoding_json))
        it_enc.setData(Qt.UserRole, it_enc.text())
        self.table.setItem(row, COL_ENCODING, it_enc)

        it_lock = QTableWidgetItem("")
        it_lock.setFlags(
            (it_lock.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable
        )
        it_lock.setCheckState(Qt.Checked if locked else Qt.Unchecked)
        it_lock.setData(Qt.UserRole, locked)
        self.table.setItem(row, COL_LOCKED, it_lock)

        it_created = QTableWidgetItem(created_at)
        it_created.setFlags(it_created.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, COL_CREATED, it_created)

    def _encoding_json_to_text(self, encoding_json: str) -> str:
        try:
            rule = normalize_encoding_rule(encoding_json)
        except Exception:
            return ""
        return ",".join(rule)

    def _refresh_summary_badges(self) -> None:
        total = self.table.rowCount()
        locked = 0
        for row in range(total):
            item = self.table.item(row, COL_LOCKED)
            if item is not None and item.checkState() == Qt.Checked:
                locked += 1
        active = max(total - locked, 0)

        self.lbl_total_badge.setText(f"总账号 {total}")
        self.lbl_active_badge.setText(f"正常 {active}")
        self.lbl_locked_badge.setText(f"锁定 {locked}")

    def _apply_filters(self) -> None:
        query = self.edit_search.text().strip().lower()
        status = str(self.combo_status.currentData() or "all")
        visible = 0

        for row in range(self.table.rowCount()):
            id_item = self.table.item(row, COL_ID)
            username_item = self.table.item(row, COL_USERNAME)
            encoding_item = self.table.item(row, COL_ENCODING)
            lock_item = self.table.item(row, COL_LOCKED)

            username = username_item.text().lower() if username_item else ""
            user_id = id_item.text().lower() if id_item else ""
            encoding = encoding_item.text().lower() if encoding_item else ""
            is_locked = lock_item.checkState() == Qt.Checked if lock_item else False

            match_query = (
                not query
                or query in username
                or query in user_id
                or query in encoding
            )
            match_status = (
                status == "all"
                or (status == "active" and not is_locked)
                or (status == "locked" and is_locked)
            )
            is_visible = match_query and match_status
            self.table.setRowHidden(row, not is_visible)
            if is_visible:
                visible += 1

        self.lbl_visible_badge.setText(f"显示 {visible} / {self.table.rowCount()}")

    def _selected_user_id(self) -> int | None:
        items = self.table.selectedItems()
        if not items:
            return None
        row = items[0].row()
        it_id = self.table.item(row, COL_ID)
        if not it_id:
            return None
        return int(it_id.data(Qt.UserRole))

    def add_user(self) -> None:
        dialog = AddUserDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        payload = dialog.payload()
        try:
            with self.db.connect() as conn:
                self.db.insert_user(conn, **payload)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "提示", "用户名已存在")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(exc))
            return

        self.reload()

    def delete_selected(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            QMessageBox.information(self, "提示", "请先选择要删除的用户")
            return

        ok = QMessageBox.question(self, "确认", f"确定删除用户 ID={user_id} 吗？")
        if ok != QMessageBox.Yes:
            return

        try:
            self.db.delete_user(user_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(exc))
            return

        self.reload()

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        if col != COL_AVATAR:
            return
        user_id = int(self.table.item(row, COL_ID).data(Qt.UserRole))

        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择头像",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*.*)",
        )
        if not path:
            return

        try:
            data = Path(path).read_bytes()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"无法读取文件: {exc}")
            return

        pm = pixmap_from_avatar_blob(data, size=self.ui_metrics.management_avatar_size)
        if pm.isNull():
            QMessageBox.warning(self, "错误", "不是有效的图片文件")
            return

        try:
            self.db.update_avatar(user_id, data)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(exc))
            return

        item = self.table.item(row, COL_AVATAR)
        item.setIcon(QIcon(pm))
        item.setData(Qt.UserRole, data)

    def _revert_item(self, item: QTableWidgetItem) -> None:
        old = item.data(Qt.UserRole)
        self.table.blockSignals(True)
        try:
            if item.column() == COL_LOCKED:
                item.setCheckState(Qt.Checked if int(old) else Qt.Unchecked)
            else:
                item.setText(str(old) if old is not None else "")
        finally:
            self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        row = item.row()
        col = item.column()
        user_id = int(self.table.item(row, COL_ID).data(Qt.UserRole))

        try:
            if col == COL_USERNAME:
                new_username = item.text().strip()
                self.db.update_username(user_id, new_username)
                item.setData(Qt.UserRole, new_username)
                avatar_item = self.table.item(row, COL_AVATAR)
                if avatar_item is not None and not avatar_item.data(Qt.UserRole):
                    avatar_item.setIcon(
                        QIcon(
                            make_placeholder_avatar(
                                new_username,
                                size=self.ui_metrics.management_avatar_size,
                            )
                        )
                    )

            elif col == COL_PASSWORD:
                new_pwd = item.text()
                if new_pwd.strip() in ("", "******"):
                    self._revert_item(item)
                    return
                self.db.update_password(user_id, new_pwd)
                self.table.blockSignals(True)
                try:
                    item.setText("******")
                    item.setData(Qt.UserRole, "******")
                finally:
                    self.table.blockSignals(False)

            elif col == COL_ENCODING:
                new_text = item.text()
                normalized = ",".join(normalize_encoding_rule(new_text))
                self.db.update_encoding_rule(user_id, new_text)
                self.table.blockSignals(True)
                try:
                    item.setText(normalized)
                    item.setData(Qt.UserRole, normalized)
                finally:
                    self.table.blockSignals(False)

            elif col == COL_LOCKED:
                locked = 1 if item.checkState() == Qt.Checked else 0
                self.db.update_locked(user_id, locked)
                item.setData(Qt.UserRole, locked)

            else:
                return

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "提示", "用户名已存在")
            self._revert_item(item)
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(exc))
            self._revert_item(item)
            return

        self._refresh_summary_badges()
        self._apply_filters()
