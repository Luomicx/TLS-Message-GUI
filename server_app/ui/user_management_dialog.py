from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..db import Database, normalize_encoding_rule
from .add_user_dialog import AddUserDialog
from .avatar import make_placeholder_avatar, pixmap_from_avatar_blob

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
        self.setWindowTitle("用户管理")
        self.resize(900, 520)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["用户ID", "用户名", "头像", "密码", "编码规则", "锁定", "创建时间"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self.add_user)
        btn_del = QPushButton("删除")
        btn_del.clicked.connect(self.delete_selected)
        btn_exit = QPushButton("退出")
        btn_exit.clicked.connect(self.accept)

        btn_col = QVBoxLayout()
        btn_col.addWidget(btn_add)
        btn_col.addWidget(btn_del)
        btn_col.addStretch(1)
        btn_col.addWidget(btn_exit)

        root = QHBoxLayout(self)
        root.addWidget(self.table, 1)
        root.addLayout(btn_col)

        self.reload()

    def reload(self) -> None:
        rows = self.db.list_users()

        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            for row in rows:
                self._append_row(row)
        finally:
            self.table.blockSignals(False)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(COL_AVATAR, 70)
        self.table.setColumnWidth(COL_PASSWORD, 80)
        self.table.setColumnWidth(COL_LOCKED, 60)
        self.table.verticalHeader().setDefaultSectionSize(48)

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
            pixmap_from_avatar_blob(avatar_blob)
            if avatar_blob
            else make_placeholder_avatar(username)
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
        dlg = AddUserDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        payload = dlg.payload()
        try:
            with self.db.connect() as conn:
                self.db.insert_user(conn, **payload)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "提示", "用户名已存在")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(e))
            return

        self.reload()

    def delete_selected(self) -> None:
        user_id = self._selected_user_id()
        if user_id is None:
            return

        ok = QMessageBox.question(self, "确认", f"确定删除用户ID={user_id} ?")
        if ok != QMessageBox.Yes:
            return

        try:
            self.db.delete_user(user_id)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(e))
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
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", f"无法读取文件: {e}")
            return

        pm = pixmap_from_avatar_blob(data)
        if pm.isNull():
            QMessageBox.warning(self, "错误", "不是有效的图片文件")
            return

        try:
            self.db.update_avatar(user_id, data)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(e))
            return

        it = self.table.item(row, COL_AVATAR)
        it.setIcon(QIcon(pm))
        it.setData(Qt.UserRole, data)

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
                _ = normalize_encoding_rule(new_text)
                self.db.update_encoding_rule(user_id, new_text)
                normalized = ",".join(normalize_encoding_rule(new_text))
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

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "提示", "用户名已存在")
            self._revert_item(item)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "错误", str(e))
            self._revert_item(item)
