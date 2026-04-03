from __future__ import annotations
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
        self._shutting_down = False
        self.active_user_key: str | None = None
        self.active_peer_key: str | None = None
        self.last_loaded_message_id = 0
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
        self.login_window.login_requested.connect(self.open_chat)
        self.chat_window.logout_requested.connect(self.back_to_login)
        self.chat_window.close_requested.connect(self._handle_chat_window_close)
        self.chat_window.search_requested.connect(self.search_users)
        self.chat_window.add_friend_requested.connect(self.add_friend)
        self.chat_window.send_message_requested.connect(self.send_message)
        self.chat_window.session_selected.connect(self.load_messages)
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
        if code in ERROR_MESSAGE_MAP:
            return ERROR_MESSAGE_MAP[code]
        return str(response.get("message", default_message))

    def open_chat(self, account: str, password: str) -> None:
        self._stop_refresh_runtime()
        response = self.client_controller.login(account, password)
        if not response.get("ok", False):
            self.login_window.set_status(
                self._resolve_user_message(response, default_message="登录失败"),
                ok=False,
            )
            return
        data = response.get("data", {})
        self.current_user = dict(data.get("user") or {})
        self.active_user_key = (
            str(self.current_user.get("username", "")).strip() or None
        )
        self._begin_refresh_generation(reset_peer=True)
        self.chat_window.reset_view_state()
        self.chat_window.set_current_user(self.current_user)
        self.chat_window.populate_friends(list(data.get("friends") or []))
        self.chat_window.populate_sessions(list(data.get("sessions") or []))
        self.chat_window.populate_messages([])
        self.chat_window.show_notice(f"已加载账号 {account} 的聊天界面")
        self.chat_window.show()
        self.login_window.hide()
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
        self.client_controller.logout(str(self.current_user.get("username", "")))
        self.current_user = None
        self.active_user_key = None

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        self._stop_refresh_runtime()
        self._logout_current_user()
        self.client_controller.close()

    def register_user(self, username: str, password: str) -> dict:
        return self.client_controller.register(username, password)

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
            friend = dict(response.get("data", {}).get("friend") or {})
            if friend:
                self.chat_window.upsert_session(friend)
            self._reset_refresh_backoff()
        self.chat_window.show_notice(
            self._resolve_user_message(response, default_message="添加好友完成")
        )

    def send_message(self, peer: str, text: str) -> None:
        if not self.current_user:
            return
        response = self.client_controller.send_message(
            str(self.current_user.get("username", "")),
            peer,
            text,
            list(self.current_user.get("encoding_rule") or []),
        )
        self.chat_window.show_notice(
            self._resolve_user_message(response, default_message="消息发送完成")
        )
        if response.get("ok", False):
            self._refresh_messages(peer, reason="send_success")

    def load_messages(self, peer: str) -> None:
        if not self.current_user:
            return
        self.active_peer_key = peer
        self._begin_refresh_generation(reset_peer=False)
        self.last_loaded_message_id = 0
        self.full_refresh_required = True
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
        since_id = self._resolve_since_id(reason)
        response = self.client_controller.pull_messages(
            username,
            since_id=since_id,
            peer=peer,
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
        self._apply_refresh_success()
        messages = []
        max_message_id = 0
        for item in list(response.get("data", {}).get("messages") or []):
            mapped = {
                "content": item.get("content", ""),
                "sender": item.get("sender", ""),
                "created_at": item.get("created_at", ""),
                "outgoing": item.get("sender") == username,
            }
            messages.append(mapped)
            try:
                max_message_id = max(max_message_id, int(item.get("id") or 0))
            except (TypeError, ValueError):
                continue
        self.chat_window.populate_messages(messages)
        self.last_loaded_message_id = max_message_id
        self.full_refresh_required = False
        self._start_idle_refresh()

    def _on_refresh_timer_tick(self) -> None:
        if not self._can_run_idle_refresh():
            return
        now = time.monotonic()
        if self.active_peer_key:
            self._refresh_messages(self.active_peer_key, reason="idle")
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
        response = self.client_controller.list_friends(username)
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
        self._apply_refresh_success()
        friends = list(response.get("data", {}).get("friends") or [])
        self.chat_window.populate_friends(friends)
        self._last_presence_refresh_at = time.monotonic()

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

    def _resolve_since_id(self, reason: str) -> int:
        if reason in {"session_switch", "bootstrap"}:
            return 0
        if reason == "send_success":
            if self.last_loaded_message_id > 0 and not self.full_refresh_required:
                return self.last_loaded_message_id
            return 0
        if self.full_refresh_required or self.last_loaded_message_id <= 0:
            return 0
        return self.last_loaded_message_id

    def _begin_refresh_generation(self, *, reset_peer: bool) -> None:
        self.refresh_generation += 1
        self.message_request_token += 1
        self.presence_request_token += 1
        self.message_refresh_in_flight = False
        self.presence_refresh_in_flight = False
        self.last_loaded_message_id = 0
        self.full_refresh_required = True
        self.backoff_until = None
        self.consecutive_failure_count = 0
        self.last_success_at = None
        if reset_peer:
            self.active_peer_key = None

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
