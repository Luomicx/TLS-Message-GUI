from __future__ import annotations

import base64
from collections import defaultdict
from pathlib import Path
from typing import cast
import sys
import time

from PyQt5.QtCore import QObject, QTimer, Qt
from PyQt5.QtWidgets import QApplication

from .network import ClientController
from .ui import ChatWindow, LoginWindow


ERROR_MESSAGE_MAP = {
    "invalid_credentials": "账号或密码错误，请重新输入",
    "user_not_found": "未找到符合条件的用户",
    "user_locked": "该账号已被锁定，请联系管理员",
    "user_exists": "该用户名已存在，请更换后重试",
    "already_friend": "对方已经是你的好友，无需重复添加",
    "friend_not_found": "未找到该好友或会话",
    "cannot_add_self": "不能将自己添加为好友",
    "invalid_request": "请求参数无效，请检查输入后重试",
    "server_error": "服务器内部处理失败，请稍后重试",
    "network_error": "网络连接失败，请检查服务器状态后重试",
    "force_logout": "你的账号已在其他终端登录，当前会话已下线",
    "nickname_empty": "昵称不能为空",
    "recovery_not_set": "该账号尚未设置密码找回信息",
    "recovery_mismatch": "找回问题或答案不正确",
    "recovery_required": "注册时必须设置安全问题和答案",
    "not_authenticated": "当前登录会话已失效，请重新登录",
    "server_update_required": "服务端未加载找回问题接口，请重启服务端后重试",
    "group_name_empty": "群名称不能为空",
    "group_member_not_found": "群成员不存在，请检查邀请列表",
    "not_group_member": "你不是该群成员",
    "invalid_file": "文件无效或为空",
}


class ClientApplication:
    IDLE_REFRESH_INTERVAL_MS = 2000
    PRESENCE_REFRESH_INTERVAL_MS = 6000
    BACKOFF_DELAYS = (2.0, 4.0, 8.0, 15.0)

    def __init__(self):
        self.client_controller = ClientController()
        self.current_user: dict[str, object] | None = None
        self.login_window = LoginWindow()
        self.chat_window = ChatWindow()
        self.download_root = (
            Path(__file__).resolve().parent.parent / "downloads" / "received"
        )
        self._shutting_down = False
        self._skip_next_server_logout = False
        self.active_user_key: str | None = None
        self.active_peer_key: str | None = None
        self.previous_last_seen_at: str | None = None
        self.last_loaded_message_id = 0
        self.last_loaded_file_id = 0
        self.last_inbox_message_id = 0
        self.last_inbox_file_id = 0
        self.group_last_loaded_message_ids: dict[int, int] = {}
        self.session_catalog: dict[str, dict[str, object]] = {}
        self.current_rendered_messages: list[dict[str, object]] = []
        self._rendered_message_keys: set[str] = set()
        self._received_file_ids: set[int] = set()
        self._received_file_paths: dict[int, Path] = {}
        self.refresh_generation = 0
        self.message_request_token = 0
        self.presence_request_token = 0
        self.message_refresh_in_flight = False
        self.presence_refresh_in_flight = False
        self.last_success_at: float | None = None
        self.consecutive_failure_count = 0
        self.backoff_until: float | None = None
        self.full_refresh_required = True
        self.idle_refresh_enabled = False
        self._last_presence_refresh_at: float | None = None
        self._refresh_timer = QTimer(cast(QObject, self.chat_window))
        self._refresh_timer.setInterval(self.IDLE_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._on_refresh_timer_tick)
        self.login_window.register_submitter = self.register_user
        self.login_window.recovery_question_loader = self.get_recovery_questions
        self.login_window.login_requested.connect(self.open_chat)
        self.login_window.recover_password_requested.connect(self.recover_password_from_login)
        self.chat_window.logout_requested.connect(self.back_to_login)
        self.chat_window.close_requested.connect(self._handle_chat_window_close)
        self.chat_window.search_requested.connect(self.search_users)
        self.chat_window.add_friend_requested.connect(self.add_friend)
        self.chat_window.send_message_requested.connect(self.send_message)
        self.chat_window.session_selected.connect(self.load_messages)
        self.chat_window.send_file_requested.connect(self.send_file_from_dialog)
        self.chat_window.create_group_requested.connect(self.create_group_from_dialog)
        self.chat_window.download_root_requested.connect(self.choose_download_root)
        self.chat_window.profile_requested.connect(self.open_profile_dialog)
        self.client_controller.forced_logout.connect(self._on_forced_logout)
        app = QApplication.instance()
        if app is not None and hasattr(app, "aboutToQuit"):
            app.aboutToQuit.connect(self.shutdown)

    def start(self) -> int:
        self.login_window.show()
        return QApplication.instance().exec_()

    def _resolve_user_message(self, response: dict, *, default_message: str) -> str:
        if response.get("ok", False):
            return str(response.get("message", default_message))
        code = str(response.get("code", "")).strip()
        if code == "invalid_credentials":
            remaining_attempts = response.get("data", {}).get("remaining_attempts")
            try:
                remain = int(remaining_attempts)
            except (TypeError, ValueError):
                remain = None
            if remain is not None:
                return f"账号或密码错误，再失败 {remain} 次将锁定账户"
        if code in ERROR_MESSAGE_MAP:
            return ERROR_MESSAGE_MAP[code]
        return str(response.get("message", default_message))

    def open_chat(self, account: str, password: str) -> None:
        self._stop_refresh_runtime()
        self.login_window.set_attempt_warning(None)
        response = self.client_controller.login(account, password)
        if not response.get("ok", False):
            remaining_attempts = response.get("data", {}).get("remaining_attempts")
            if str(response.get("code", "")) == "invalid_credentials":
                try:
                    remain = int(remaining_attempts)
                except (TypeError, ValueError):
                    remain = None
                self.login_window.set_attempt_warning(remain)
            else:
                self.login_window.set_attempt_warning(None)
            self.login_window.set_status(
                self._resolve_user_message(response, default_message="登录失败"),
                ok=False,
            )
            return
        self.login_window.set_attempt_warning(None)
        data = response.get("data", {})
        self.current_user = dict(data.get("user") or {})
        self.active_user_key = (
            str(self.current_user.get("username", "")).strip() or None
        )
        self.previous_last_seen_at = (
            str(self.current_user.get("previous_last_seen_at") or "").strip() or None
        )
        self._ensure_download_root()
        self._begin_refresh_generation(reset_peer=True)
        self.chat_window.reset_view_state()
        self.chat_window.set_download_root(str(self.download_root))
        self.chat_window.set_current_user(self.current_user)
        self.chat_window.populate_friends(list(data.get("friends") or []))
        self._replace_session_catalog(list(data.get("sessions") or []))
        self.chat_window.populate_sessions(self._session_view_payloads())
        groups = self._load_groups_into_sessions()
        offline_summary = self._sync_offline_inbox_state(groups=groups)
        self.current_rendered_messages = []
        self._rendered_message_keys.clear()
        self.chat_window.populate_messages([])
        self.chat_window.show()
        self.login_window.hide()
        if offline_summary["message_count"] > 0:
            self.chat_window.show_notice(
                f"已同步离线消息：{offline_summary['session_count']} 个会话，{offline_summary['message_count']} 条内容"
            )
        else:
            self.chat_window.show_notice(f"已加载账号 {account} 的聊天界面")
        self.login_window.set_status(str(response.get("message", "登录成功")), ok=True)
        if self.chat_window.current_peer:
            self.load_messages(self.chat_window.current_peer)
        else:
            self._start_idle_refresh()

    def back_to_login(self) -> None:
        self._stop_refresh_runtime()
        self._logout_current_user()
        self.chat_window.reset_view_state()
        self.chat_window.hide()
        self.login_window.show()
        self.login_window.set_status("已注销，本地界面已返回登录页", ok=True)

    def _handle_chat_window_close(self) -> None:
        self.back_to_login()

    def _logout_current_user(self) -> None:
        if self.current_user is None:
            return
        if not self._skip_next_server_logout:
            self.client_controller.logout(str(self.current_user.get("username", "")))
        self._skip_next_server_logout = False
        self.current_user = None
        self.active_user_key = None
        self.previous_last_seen_at = None

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._stop_refresh_runtime()
        self._logout_current_user()
        self.client_controller.close()

    def register_user(
        self, username: str, password: str, question: str, answer: str
    ) -> dict:
        return self.client_controller.register(username, password, question, answer)

    def update_profile(self, nickname: str) -> dict:
        if not self.current_user:
            return {"ok": False, "code": "invalid_request", "message": "未登录"}
        username = str(self.current_user.get("username", "")).strip()
        response = self.client_controller.update_profile(username, nickname)
        if response.get("ok", False):
            profile = dict(response.get("data", {}).get("profile") or {})
            self.current_user.update(profile)
            self.chat_window.set_current_user(self.current_user)
        return response

    def open_profile_dialog(self) -> None:
        if not self.current_user:
            return
        from .ui.profile_dialog import ProfileDialog

        username = str(self.current_user.get("username", "")).strip()
        profile_response = self.client_controller.get_profile(username)
        profile_data = dict(profile_response.get("data", {}).get("profile") or {})
        if profile_response.get("ok", False) and profile_data:
            self.current_user.update(profile_data)

        recovery_question = ""
        recovery_response = self.client_controller.get_recovery_questions(username)
        if recovery_response.get("ok", False):
            questions = list(recovery_response.get("data", {}).get("questions") or [])
            if questions:
                recovery_question = str(questions[0] or "").strip()

        dialog = ProfileDialog(self.chat_window)
        dialog.load_profile(
            username=username,
            nickname=str(
                self.current_user.get("nickname")
                or self.current_user.get("username")
                or username
            ),
            recovery_question=recovery_question,
        )
        if dialog.exec_() != dialog.Accepted:
            return

        payload = dialog.payload()
        notices: list[str] = []

        if payload["nickname"] != str(
            self.current_user.get("nickname")
            or self.current_user.get("username")
            or username
        ):
            response = self.update_profile(payload["nickname"])
            if not response.get("ok", False):
                self.chat_window.show_notice(
                    self._resolve_user_message(response, default_message="资料更新失败")
                )
                return
            notices.append("昵称已更新")

        if payload["current_password"] and payload["new_password"]:
            response = self.change_password(
                payload["current_password"], payload["new_password"]
            )
            if not response.get("ok", False):
                self.chat_window.show_notice(
                    self._resolve_user_message(response, default_message="密码修改失败")
                )
                return
            notices.append("登录密码已更新")

        if payload["recovery_question"] and payload["recovery_answer"]:
            response = self.set_recovery(
                payload["recovery_question"], payload["recovery_answer"]
            )
            if not response.get("ok", False):
                self.chat_window.show_notice(
                    self._resolve_user_message(response, default_message="找回信息设置失败")
                )
                return
            notices.append("找回信息已更新")

        if notices:
            self.chat_window.set_current_user(self.current_user)
            self.chat_window.show_notice("，".join(notices))
        else:
            self.chat_window.show_notice("资料未发生变化")

    def _replace_session_catalog(self, sessions: list[dict[str, object]]) -> None:
        self.session_catalog.clear()
        for payload in sessions:
            self._merge_session_record(payload)

    def _merge_session_record(self, payload: dict[str, object]) -> None:
        raw_peer = str(payload.get("username") or "")
        if not raw_peer:
            return
        merged = dict(self.session_catalog.get(raw_peer) or {})
        merged.update(payload)
        merged["username"] = raw_peer
        merged["unread_count"] = self._safe_int(merged.get("unread_count"))
        merged["has_offline_messages"] = bool(merged.get("has_offline_messages"))
        self.session_catalog[raw_peer] = merged

    def _session_view_payloads(self) -> list[dict[str, object]]:
        return [dict(item) for item in self.session_catalog.values()]

    def _upsert_session_record(self, payload: dict[str, object]) -> None:
        self._merge_session_record(payload)
        raw_peer = str(payload.get("username") or "")
        if not raw_peer:
            return
        self.chat_window.upsert_session(dict(self.session_catalog[raw_peer]))

    def _update_session_activity(self, raw_peer: str, *, created_at: str) -> None:
        if not raw_peer:
            return
        payload = dict(self.session_catalog.get(raw_peer) or {"username": raw_peer})
        if self._is_newer_timestamp(created_at, str(payload.get("last_message_at") or "")):
            payload["last_message_at"] = created_at
        self._upsert_session_record(payload)

    def _mark_session_attention(
        self,
        raw_peer: str,
        *,
        unread_increment: int = 0,
        has_offline_messages: bool = False,
        last_message_at: str = "",
    ) -> None:
        if not raw_peer:
            return
        payload = dict(self.session_catalog.get(raw_peer) or {"username": raw_peer})
        payload["unread_count"] = self._safe_int(payload.get("unread_count")) + max(
            0, unread_increment
        )
        payload["has_offline_messages"] = bool(
            payload.get("has_offline_messages")
        ) or has_offline_messages
        if last_message_at and self._is_newer_timestamp(
            last_message_at, str(payload.get("last_message_at") or "")
        ):
            payload["last_message_at"] = last_message_at
        self._upsert_session_record(payload)

    def _clear_session_attention(self, raw_peer: str) -> None:
        if not raw_peer:
            return
        payload = dict(self.session_catalog.get(raw_peer) or {"username": raw_peer})
        payload["unread_count"] = 0
        payload["has_offline_messages"] = False
        self._upsert_session_record(payload)

    def _sync_friend_sessions(self, friends: list[dict[str, object]]) -> None:
        for friend in friends:
            self._upsert_session_record(friend)

    def _group_session_key(self, group_id: int, group_name: str) -> str:
        return f"[群]{group_name}#{group_id}"

    def _safe_int(self, value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _timestamp_token(self, value: object) -> int:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if not digits:
            return 0
        try:
            return int(digits)
        except ValueError:
            return 0

    def _is_newer_timestamp(self, left: object, right: object) -> bool:
        return self._timestamp_token(left) > self._timestamp_token(right)

    def _is_offline_candidate(self, created_at: object) -> bool:
        if not self.previous_last_seen_at:
            return False
        return self._is_newer_timestamp(created_at, self.previous_last_seen_at)

    def change_password(self, old_password: str, new_password: str) -> dict:
        if not self.current_user:
            return {"ok": False, "code": "invalid_request", "message": "未登录"}
        username = str(self.current_user.get("username", "")).strip()
        return self.client_controller.change_password(username, old_password, new_password)

    def set_recovery(self, question: str, answer: str) -> dict:
        if not self.current_user:
            return {"ok": False, "code": "invalid_request", "message": "未登录"}
        username = str(self.current_user.get("username", "")).strip()
        return self.client_controller.set_recovery(username, question, answer)

    def get_recovery_questions(self, username: str) -> dict:
        return self.client_controller.get_recovery_questions(username)

    def recover_password(
        self, username: str, question: str, answer: str, new_password: str
    ) -> dict:
        return self.client_controller.recover_password(
            username, question, answer, new_password
        )

    def recover_password_from_login(
        self, username: str, question: str, answer: str, new_password: str
    ) -> None:
        response = self.recover_password(username, question, answer, new_password)
        self.login_window.set_status(
            self._resolve_user_message(response, default_message="密码找回完成"),
            ok=bool(response.get("ok", False)),
        )

    def create_group(self, group_name: str, members: list[str]) -> dict:
        if not self.current_user:
            return {"ok": False, "code": "invalid_request", "message": "未登录"}
        username = str(self.current_user.get("username", "")).strip()
        return self.client_controller.create_group(username, group_name, members)

    def send_file(self, peer: str, file_name: str, file_bytes: bytes) -> dict:
        if not self.current_user:
            return {"ok": False, "code": "invalid_request", "message": "未登录"}
        username = str(self.current_user.get("username", "")).strip()
        return self.client_controller.send_file(username, peer, file_name, file_bytes)

    def search_users(self, mode: str, query: str) -> None:
        if not self.current_user:
            return
        response = self.client_controller.search_users(
            str(self.current_user.get("username", "")), mode, query
        )
        if response.get("ok", False):
            self.chat_window.populate_search_results(
                list(response.get("data", {}).get("users") or [])
            )
            self.chat_window.show_notice(
                self._resolve_user_message(response, default_message="搜索成功")
            )
        else:
            self.chat_window.show_notice(
                self._resolve_user_message(response, default_message="搜索失败")
            )

    def add_friend(self, friend_id: int) -> None:
        if not self.current_user:
            return
        response = self.client_controller.add_friend(
            str(self.current_user.get("username", "")), friend_id
        )
        if response.get("ok", False):
            friends = list(response.get("data", {}).get("friends") or [])
            self.chat_window.populate_friends(friends)
            self._sync_friend_sessions(friends)
            friend = dict(response.get("data", {}).get("friend") or {})
            if friend:
                self._upsert_session_record(friend)
            self._reset_refresh_backoff()
        self.chat_window.show_notice(
            self._resolve_user_message(response, default_message="添加好友完成")
        )

    def send_message(self, peer: str, text: str) -> None:
        if not self.current_user:
            return
        username = str(self.current_user.get("username", "")).strip()
        encoding_rule = list(self.current_user.get("encoding_rule") or [])
        group_id = self._parse_group_session_id(peer)
        if peer.startswith("[群]"):
            if group_id is None:
                self.chat_window.show_notice("群会话标识无效，请重新选择群聊")
                return
            response = self.client_controller.send_group_message(
                username,
                group_id,
                text,
                encoding_rule,
            )
        else:
            response = self.client_controller.send_message(
                username,
                peer,
                text,
                encoding_rule,
            )
        self.chat_window.show_notice(
            self._resolve_user_message(response, default_message="消息发送完成")
        )
        if response.get("ok", False):
            self._refresh_messages(peer, reason="send_success")

    def send_file_from_dialog(self, peer: str) -> None:
        if not self.current_user:
            return
        if peer.startswith("[群]"):
            self.chat_window.show_notice("当前版本暂不支持群聊发送文件")
            return
        from PyQt5.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self.chat_window, "选择发送文件", "", "All Files (*.*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
        except OSError as exc:
            self.chat_window.show_notice(f"读取文件失败: {exc}")
            return
        file_name = file_path.replace("\\", "/").split("/")[-1]
        response = self.send_file(peer, file_name, file_bytes)
        message = self._resolve_user_message(response, default_message="文件发送完成")
        if response.get("ok", False):
            message = f"{message}，文件 {file_name} 已发往 {peer}"
        self.chat_window.show_notice(message)
        if response.get("ok", False):
            self._refresh_messages(peer, reason="send_success")

    def create_group_from_dialog(self) -> None:
        if not self.current_user:
            return
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import (
            QDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QListWidgetItem,
            QPushButton,
            QVBoxLayout,
        )

        friend_candidates = self._collect_friend_candidates()
        dialog = QDialog(self.chat_window)
        dialog.setWindowTitle("创建群聊")
        dialog.resize(420, 520)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("输入群名称，并从当前好友中选择成员。")
        title.setWordWrap(True)
        root.addWidget(title)

        group_name_edit = QLineEdit(dialog)
        group_name_edit.setPlaceholderText("请输入群名称")
        root.addWidget(group_name_edit)

        list_widget = QListWidget(dialog)
        list_widget.setSelectionMode(QListWidget.MultiSelection)
        for candidate in friend_candidates:
            item = QListWidgetItem(candidate["label"])
            item.setData(Qt.UserRole, candidate["username"])
            list_widget.addItem(item)
        root.addWidget(list_widget, 1)

        hint = QLabel("可不选成员，仅创建空群。")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        btn_confirm = QPushButton("创建", dialog)
        btn_cancel = QPushButton("取消", dialog)
        btn_confirm.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        buttons.addWidget(btn_confirm, 1)
        buttons.addWidget(btn_cancel, 1)
        root.addLayout(buttons)

        if dialog.exec_() != dialog.Accepted:
            return

        group_name = group_name_edit.text().strip()
        members = [
            str(list_widget.item(index).data(Qt.UserRole) or "").strip()
            for index in range(list_widget.count())
            if list_widget.item(index).isSelected()
        ]
        response = self.create_group(group_name.strip(), members)
        self.chat_window.show_notice(
            self._resolve_user_message(response, default_message="创建群聊完成")
        )
        if response.get("ok", False):
            group = dict(response.get("data", {}).get("group") or {})
            gid = group.get("id")
            gname = str(group.get("name", "群聊"))
            self._upsert_session_record(
                {
                    "username": f"[群]{gname}#{gid}",
                    "nickname": gname,
                    "members": list(group.get("members") or []),
                }
            )

    def _collect_friend_candidates(self) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()
        friend_list = getattr(self.chat_window, "list_friends", None)
        if friend_list is None:
            return candidates
        for index in range(friend_list.count()):
            item = friend_list.item(index)
            username = str(item.data(Qt.UserRole) or "").strip()
            if not username or username in seen:
                continue
            seen.add(username)
            candidates.append(
                {
                    "username": username,
                    "label": str(item.text() or username),
                }
            )
        return candidates

    def load_messages(self, peer: str) -> None:
        if not self.current_user:
            return
        self.active_peer_key = peer
        self._clear_session_attention(peer)
        self._begin_refresh_generation(reset_peer=False)
        self.last_loaded_message_id = 0
        self.last_loaded_file_id = 0
        self.full_refresh_required = True
        self.current_rendered_messages = []
        self._rendered_message_keys.clear()
        self._refresh_messages(peer, reason="session_switch")

    def _refresh_messages(self, peer: str, *, reason: str) -> None:
        if not self.current_user:
            return
        if self._shutting_down:
            return
        username = str(self.current_user.get("username", "")).strip()
        if not username or peer != self.active_peer_key:
            return
        if self.client_controller.request_in_flight or self.message_refresh_in_flight:
            return
        generation = self.refresh_generation
        self.message_request_token += 1
        token = self.message_request_token
        self.message_refresh_in_flight = True
        message_since_id, file_since_id = self._resolve_since_ids(reason)
        group_id = self._parse_group_session_id(peer)
        if group_id is not None:
            response = self.client_controller.pull_group_messages(
                username, group_id, since_id=message_since_id
            )
            file_response = {"ok": True, "data": {"files": []}}
        else:
            response = self.client_controller.pull_messages(
                username,
                since_id=message_since_id,
                peer=peer,
            )
            file_response = self.client_controller.pull_files(
                username, since_id=file_since_id, peer=peer
            )
        self.message_refresh_in_flight = False
        if self._is_stale_message_response(
            request_user_key=username,
            request_peer_key=peer,
            request_generation=generation,
            request_token=token,
        ):
            return
        if not response.get("ok", False):
            self._record_refresh_failure()
            self.chat_window.show_notice(
                self._resolve_user_message(response, default_message="消息加载失败")
            )
            return
        if not file_response.get("ok", False):
            self._record_refresh_failure()
            return
        self._apply_refresh_success()
        incoming_messages: list[dict[str, object]] = []
        max_message_id = self.last_loaded_message_id
        max_file_id = self.last_loaded_file_id
        for item in list(response.get("data", {}).get("messages") or []):
            mapped = {
                "content": item.get("content", ""),
                "sender": item.get("sender", ""),
                "created_at": item.get("created_at", ""),
                "outgoing": item.get("sender") == username,
                "message_type": "text",
            }
            incoming_messages.append(mapped)
            try:
                max_message_id = max(max_message_id, int(item.get("id") or 0))
            except (TypeError, ValueError):
                continue
        for item in list(file_response.get("data", {}).get("files") or []):
            saved_path, saved_now = self._persist_incoming_file(username, peer, item)
            file_size = self._format_file_size(item.get("file_size"))
            sender_name = str(item.get("sender") or "")
            if sender_name == username:
                delivery_text = f"已发送给 {peer}"
            elif saved_path is not None:
                delivery_text = f"已保存到：{saved_path}"
            else:
                delivery_text = "已接收，但保存失败"
            mapped = {
                "content": "如需转移文件，可点击顶部“接收目录”修改默认路径。",
                "sender": sender_name,
                "created_at": item.get("created_at", ""),
                "outgoing": sender_name == username,
                "message_type": "file",
                "file_name": str(item.get("file_name") or "未命名文件"),
                "file_size_text": file_size,
                "file_delivery_text": delivery_text,
            }
            incoming_messages.append(mapped)
            if saved_now and saved_path is not None:
                self.chat_window.show_notice(
                    f"收到文件 {item.get('file_name')}，已保存到 {saved_path}"
                )
            try:
                max_file_id = max(max_file_id, int(item.get("id") or 0))
            except (TypeError, ValueError):
                continue
        incoming_messages.sort(key=lambda x: str(x.get("created_at", "")))
        should_replace = reason in {"session_switch", "bootstrap"} or self.full_refresh_required
        changed = self._merge_rendered_messages(incoming_messages, replace=should_replace)
        if changed:
            self.chat_window.populate_messages(self.current_rendered_messages)
        self.last_loaded_message_id = max_message_id
        self.last_loaded_file_id = max_file_id
        self.last_inbox_message_id = max(self.last_inbox_message_id, max_message_id)
        self.last_inbox_file_id = max(self.last_inbox_file_id, max_file_id)
        latest_activity = ""
        for item in incoming_messages:
            created_at = str(item.get("created_at") or "")
            if self._is_newer_timestamp(created_at, latest_activity):
                latest_activity = created_at
        if latest_activity:
            self._update_session_activity(peer, created_at=latest_activity)
        self.full_refresh_required = False
        self._start_idle_refresh()

    def _persist_incoming_file(
        self, username: str, peer: str, item: dict[str, object]
    ) -> tuple[Path | None, bool]:
        receiver = str(item.get("receiver", "")).strip()
        sender = str(item.get("sender", "")).strip()
        if receiver != username or sender == username:
            return None, False
        try:
            file_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            return None, False
        if file_id <= 0:
            return None, False
        file_name = Path(str(item.get("file_name") or "received.bin")).name
        known_paths = getattr(self, "_received_file_paths", {})
        existing_path = known_paths.get(file_id)
        if existing_path is not None and existing_path.exists():
            self._received_file_ids.add(file_id)
            return existing_path, False
        target_path = self._build_default_receive_path(
            username=username,
            peer=peer,
            file_id=file_id,
            file_name=file_name,
        )
        if target_path.exists():
            self._received_file_ids.add(file_id)
            return target_path, False
        payload = str(item.get("file_base64") or "").strip()
        if not payload:
            return None, False
        target_path = self._choose_receive_target_path(
            sender=sender,
            file_name=file_name,
            default_path=target_path,
        )
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(base64.b64decode(payload.encode("ascii")))
        except Exception:
            return None, False
        self._received_file_ids.add(file_id)
        self._received_file_paths[file_id] = target_path
        return target_path, True

    def _safe_path_component(self, text: str) -> str:
        clean = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
        return clean.strip("_") or "unknown"

    def _build_default_receive_path(
        self, *, username: str, peer: str, file_id: int, file_name: str
    ) -> Path:
        self._ensure_download_root()
        target_dir = (
            self.download_root
            / self._safe_path_component(username)
            / self._safe_path_component(peer)
        )
        return target_dir / f"{file_id}_{file_name}"

    def _choose_receive_target_path(
        self, *, sender: str, file_name: str, default_path: Path
    ) -> Path:
        from PyQt5.QtWidgets import QFileDialog

        selected_path, _ = QFileDialog.getSaveFileName(
            self.chat_window,
            f"保存来自 {sender} 的文件",
            str(default_path),
            "All Files (*.*)",
        )
        if selected_path:
            return Path(selected_path)
        return default_path

    def choose_download_root(self) -> None:
        from PyQt5.QtWidgets import QFileDialog

        selected_dir = QFileDialog.getExistingDirectory(
            self.chat_window,
            "选择默认接收目录",
            str(self.download_root),
        )
        if not selected_dir:
            return
        self.download_root = Path(selected_dir)
        self._ensure_download_root()
        self.chat_window.set_download_root(str(self.download_root))
        self.chat_window.show_notice(f"默认接收目录已更新为 {self.download_root}")

    def _ensure_download_root(self) -> None:
        self.download_root.mkdir(parents=True, exist_ok=True)

    def _sync_offline_inbox_state(
        self, *, groups: list[dict[str, object]]
    ) -> dict[str, int]:
        summary = {"session_count": 0, "message_count": 0}
        if not self.current_user:
            return summary
        username = str(self.current_user.get("username", "")).strip()
        if not username:
            return summary

        message_response = self.client_controller.pull_messages(username, since_id=0)
        file_response = self.client_controller.pull_files(username, since_id=0)
        if not message_response.get("ok", False) or not file_response.get("ok", False):
            return summary

        attention_counts: dict[str, int] = defaultdict(int)
        latest_timestamps: dict[str, str] = {}

        for item in list(message_response.get("data", {}).get("messages") or []):
            sender = str(item.get("sender") or "").strip()
            created_at = str(item.get("created_at") or "")
            peer = sender if sender and sender != username else ""
            self.last_inbox_message_id = max(
                self.last_inbox_message_id, self._safe_int(item.get("id"))
            )
            if peer:
                self._update_session_activity(peer, created_at=created_at)
            if peer and self._is_offline_candidate(created_at):
                attention_counts[peer] += 1
                latest_timestamps[peer] = created_at

        for item in list(file_response.get("data", {}).get("files") or []):
            sender = str(item.get("sender") or "").strip()
            created_at = str(item.get("created_at") or "")
            peer = sender if sender and sender != username else ""
            self.last_inbox_file_id = max(
                self.last_inbox_file_id, self._safe_int(item.get("id"))
            )
            if peer:
                self._update_session_activity(peer, created_at=created_at)
            if peer and self._is_offline_candidate(created_at):
                attention_counts[peer] += 1
                latest_timestamps[peer] = created_at

        for group in groups:
            group_id = self._safe_int(group.get("id"))
            group_name = str(group.get("name") or "群聊")
            group_key = self._group_session_key(group_id, group_name)
            response = self.client_controller.pull_group_messages(
                username, group_id, since_id=0
            )
            if not response.get("ok", False):
                continue
            last_group_message_id = 0
            for item in list(response.get("data", {}).get("messages") or []):
                created_at = str(item.get("created_at") or "")
                sender = str(item.get("sender") or "").strip()
                last_group_message_id = max(
                    last_group_message_id, self._safe_int(item.get("id"))
                )
                self._update_session_activity(group_key, created_at=created_at)
                if sender and sender != username and self._is_offline_candidate(created_at):
                    attention_counts[group_key] += 1
                    latest_timestamps[group_key] = created_at
            self.group_last_loaded_message_ids[group_id] = last_group_message_id

        for raw_peer, unread_count in attention_counts.items():
            self._mark_session_attention(
                raw_peer,
                unread_increment=unread_count,
                has_offline_messages=True,
                last_message_at=latest_timestamps.get(raw_peer, ""),
            )
            summary["session_count"] += 1
            summary["message_count"] += unread_count

        return summary

    def _sync_private_inbox_updates(self) -> None:
        if not self.current_user or self._shutting_down:
            return
        username = str(self.current_user.get("username", "")).strip()
        if not username:
            return
        if self.client_controller.request_in_flight:
            return

        message_response = self.client_controller.pull_messages(
            username, since_id=self.last_inbox_message_id
        )
        file_response = self.client_controller.pull_files(
            username, since_id=self.last_inbox_file_id
        )
        if not message_response.get("ok", False) or not file_response.get("ok", False):
            return

        attention_counts: dict[str, int] = defaultdict(int)
        for item in list(message_response.get("data", {}).get("messages") or []):
            message_id = self._safe_int(item.get("id"))
            self.last_inbox_message_id = max(self.last_inbox_message_id, message_id)
            sender = str(item.get("sender") or "").strip()
            created_at = str(item.get("created_at") or "")
            if not sender or sender == username:
                continue
            self._update_session_activity(sender, created_at=created_at)
            if sender != self.active_peer_key:
                attention_counts[sender] += 1

        for item in list(file_response.get("data", {}).get("files") or []):
            file_id = self._safe_int(item.get("id"))
            self.last_inbox_file_id = max(self.last_inbox_file_id, file_id)
            sender = str(item.get("sender") or "").strip()
            created_at = str(item.get("created_at") or "")
            if not sender or sender == username:
                continue
            self._update_session_activity(sender, created_at=created_at)
            if sender != self.active_peer_key:
                attention_counts[sender] += 1

        total_updates = 0
        for raw_peer, unread_count in attention_counts.items():
            self._mark_session_attention(
                raw_peer,
                unread_increment=unread_count,
                last_message_at=str(
                    self.session_catalog.get(raw_peer, {}).get("last_message_at") or ""
                ),
            )
            total_updates += unread_count
        if total_updates > 0:
            self.chat_window.show_notice(f"收到 {total_updates} 条新消息，请查看高亮会话")

    def _sync_group_inbox_updates(self, groups: list[dict[str, object]]) -> None:
        if not self.current_user:
            return
        username = str(self.current_user.get("username", "")).strip()
        if not username:
            return

        total_updates = 0
        for group in groups:
            group_id = self._safe_int(group.get("id"))
            group_name = str(group.get("name") or "群聊")
            group_key = self._group_session_key(group_id, group_name)
            since_id = self.group_last_loaded_message_ids.get(group_id, 0)
            response = self.client_controller.pull_group_messages(
                username, group_id, since_id=since_id
            )
            if not response.get("ok", False):
                continue
            latest_group_id = since_id
            unread_count = 0
            latest_created_at = ""
            for item in list(response.get("data", {}).get("messages") or []):
                latest_group_id = max(latest_group_id, self._safe_int(item.get("id")))
                sender = str(item.get("sender") or "").strip()
                created_at = str(item.get("created_at") or "")
                self._update_session_activity(group_key, created_at=created_at)
                if sender and sender != username and group_key != self.active_peer_key:
                    unread_count += 1
                    latest_created_at = created_at
            self.group_last_loaded_message_ids[group_id] = latest_group_id
            if unread_count > 0:
                self._mark_session_attention(
                    group_key,
                    unread_increment=unread_count,
                    last_message_at=latest_created_at,
                )
                total_updates += unread_count
        if total_updates > 0:
            self.chat_window.show_notice(f"有 {total_updates} 条新的群聊消息待查看")

    def _format_file_size(self, raw_size: object) -> str:
        try:
            size = int(raw_size or 0)
        except (TypeError, ValueError):
            return "大小未知"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    def _on_refresh_timer_tick(self) -> None:
        if not self._can_run_idle_refresh():
            return
        now = time.monotonic()
        if self.active_peer_key:
            self._refresh_messages(self.active_peer_key, reason="idle")
            if not self._can_run_idle_refresh(now=now):
                return
        self._sync_private_inbox_updates()
        if not self._can_run_idle_refresh(now=now):
            return
        if self._should_refresh_presence(now):
            self._refresh_presence()

    def _refresh_presence(self) -> None:
        if not self.current_user or self._shutting_down:
            return
        username = str(self.current_user.get("username", "")).strip()
        if not username:
            return
        if self.client_controller.request_in_flight or self.presence_refresh_in_flight:
            return
        generation = self.refresh_generation
        self.presence_request_token += 1
        token = self.presence_request_token
        self.presence_refresh_in_flight = True
        hb = self.client_controller.heartbeat(username)
        if not hb.get("ok", False):
            self._record_refresh_failure()
            return
        response = self.client_controller.list_friends(username)
        group_response = self.client_controller.list_groups(username)
        self.presence_refresh_in_flight = False
        if self._is_stale_presence_response(
            request_user_key=username,
            request_generation=generation,
            request_token=token,
        ):
            return
        if not response.get("ok", False):
            self._record_refresh_failure()
            return
        if not group_response.get("ok", False):
            self._record_refresh_failure()
            return
        self._apply_refresh_success()
        friends = list(response.get("data", {}).get("friends") or [])
        self.chat_window.populate_friends(friends)
        self._sync_friend_sessions(friends)
        groups = list(group_response.get("data", {}).get("groups") or [])
        self._sync_group_sessions(groups)
        self._sync_group_inbox_updates(groups)
        self._last_presence_refresh_at = time.monotonic()

    def _on_forced_logout(self, payload: dict) -> None:
        if self.current_user is None:
            return
        message = self._resolve_user_message(payload, default_message="账号已下线")
        self._skip_next_server_logout = True
        self.back_to_login()
        self.login_window.set_status(message, ok=False)

    def _load_groups_into_sessions(self) -> None:
        if not self.current_user:
            return []
        username = str(self.current_user.get("username", "")).strip()
        response = self.client_controller.list_groups(username)
        if not response.get("ok", False):
            return []
        groups = list(response.get("data", {}).get("groups") or [])
        self._sync_group_sessions(groups)
        return groups

    def _sync_group_sessions(self, groups: list[dict[str, object]]) -> None:
        for item in groups:
            gid = self._safe_int(item.get("id"))
            gname = str(item.get("name", "群聊"))
            members = list(item.get("members") or [])
            label = self._group_session_key(gid, gname)
            self._upsert_session_record(
                {
                    "username": label,
                    "nickname": gname,
                    "members": members,
                }
            )

    def _parse_group_session_id(self, peer: str) -> int | None:
        if not peer.startswith("[群]"):
            return None
        _prefix, sep, tail = peer.rpartition("#")
        if not sep:
            return None
        try:
            group_id = int(tail)
        except (TypeError, ValueError):
            return None
        return group_id if group_id > 0 else None

    def _can_run_idle_refresh(self, *, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        return bool(
            self.idle_refresh_enabled
            and not self._shutting_down
            and self.current_user is not None
            and self.active_user_key
            and not self.client_controller.request_in_flight
            and not self.message_refresh_in_flight
            and not self.presence_refresh_in_flight
            and (self.backoff_until is None or current_time >= self.backoff_until)
        )

    def _should_refresh_presence(self, now: float) -> bool:
        if self._last_presence_refresh_at is None:
            return True
        return (
            now - self._last_presence_refresh_at
        ) * 1000 >= self.PRESENCE_REFRESH_INTERVAL_MS

    def _resolve_since_ids(self, reason: str) -> tuple[int, int]:
        if reason in {"session_switch", "bootstrap"}:
            return 0, 0
        if reason == "send_success":
            if not self.full_refresh_required:
                return self.last_loaded_message_id, self.last_loaded_file_id
            return 0, 0
        if self.full_refresh_required:
            return 0, 0
        return self.last_loaded_message_id, self.last_loaded_file_id

    def _merge_rendered_messages(
        self, incoming: list[dict[str, object]], *, replace: bool
    ) -> bool:
        if replace:
            self.current_rendered_messages = list(incoming)
            self._rendered_message_keys = {
                self._message_key(item) for item in self.current_rendered_messages
            }
            return True
        if not incoming:
            return False
        changed = False
        for item in incoming:
            key = self._message_key(item)
            if key in self._rendered_message_keys:
                continue
            self.current_rendered_messages.append(item)
            self._rendered_message_keys.add(key)
            changed = True
        if changed:
            self.current_rendered_messages.sort(
                key=lambda x: str(x.get("created_at", ""))
            )
        return changed

    def _message_key(self, item: dict[str, object]) -> str:
        return "|".join(
            [
                str(item.get("sender", "")),
                str(item.get("created_at", "")),
                str(item.get("content", "")),
                "1" if bool(item.get("outgoing")) else "0",
            ]
        )

    def _begin_refresh_generation(self, *, reset_peer: bool) -> None:
        self.refresh_generation += 1
        self.message_request_token += 1
        self.presence_request_token += 1
        self.message_refresh_in_flight = False
        self.presence_refresh_in_flight = False
        self.last_loaded_message_id = 0
        self.last_loaded_file_id = 0
        self.current_rendered_messages = []
        self._rendered_message_keys.clear()
        self.full_refresh_required = True
        self.backoff_until = None
        self.consecutive_failure_count = 0
        self.last_success_at = None
        if reset_peer:
            self.active_peer_key = None
            self.last_inbox_message_id = 0
            self.last_inbox_file_id = 0
            self.group_last_loaded_message_ids.clear()
            self.session_catalog.clear()

    def _start_idle_refresh(self) -> None:
        if self._shutting_down or not self.current_user or not self.active_user_key:
            return
        self.idle_refresh_enabled = True
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _stop_refresh_runtime(self) -> None:
        self.idle_refresh_enabled = False
        if self._refresh_timer.isActive():
            self._refresh_timer.stop()
        self._begin_refresh_generation(reset_peer=True)
        self.backoff_until = None
        self._last_presence_refresh_at = None

    def _record_refresh_failure(self) -> None:
        self.consecutive_failure_count += 1
        index = min(self.consecutive_failure_count - 1, len(self.BACKOFF_DELAYS) - 1)
        self.backoff_until = time.monotonic() + self.BACKOFF_DELAYS[index]

    def _apply_refresh_success(self) -> None:
        self.consecutive_failure_count = 0
        self.backoff_until = None
        self.last_success_at = time.monotonic()

    def _reset_refresh_backoff(self) -> None:
        self.consecutive_failure_count = 0
        self.backoff_until = None

    def _is_stale_message_response(
        self,
        *,
        request_user_key: str,
        request_peer_key: str,
        request_generation: int,
        request_token: int,
    ) -> bool:
        return bool(
            self._shutting_down
            or self.current_user is None
            or request_generation != self.refresh_generation
            or request_token != self.message_request_token
            or request_user_key != self.active_user_key
            or request_peer_key != self.active_peer_key
        )

    def _is_stale_presence_response(
        self,
        *,
        request_user_key: str,
        request_generation: int,
        request_token: int,
    ) -> bool:
        return bool(
            self._shutting_down
            or self.current_user is None
            or request_generation != self.refresh_generation
            or request_token != self.presence_request_token
            or request_user_key != self.active_user_key
        )


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    client = ClientApplication()
    return client.start()
