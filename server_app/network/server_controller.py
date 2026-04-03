from __future__ import annotations

import json
import socket
import socketserver
import ssl
import sqlite3
import threading
from typing import Any, Optional, Type

from PyQt5.QtCore import QObject, pyqtSignal

from ..db import Database
from ..protocol import (
    decode_request_line,
    decode_sensitive_text,
    encode_response_line,
    encode_sensitive_text,
)
from tls_support import build_server_ssl_context, cert_dir


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: Type[socketserver.BaseRequestHandler],
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.ssl_context = ssl_context
        super().__init__(server_address, request_handler_class)

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        sock, addr = super().get_request()
        if self.ssl_context is None:
            return sock, addr
        try:
            wrapped = self.ssl_context.wrap_socket(sock, server_side=True)
        except Exception:
            sock.close()
            raise
        return wrapped, addr


class ServerController(QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, *, db: Database, host: str = "0.0.0.0") -> None:
        super().__init__()
        self.db = db
        self.host = host
        self._server: Optional[ThreadingTCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._online_users: dict[str, str] = {}
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        return self._server is not None

    def listening_port(self) -> int | None:
        if self._server is None:
            return None
        return int(self._server.server_address[1])

    def _with_presence(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        if not payload:
            return {}
        mapped = dict(payload)
        username = str(mapped.get("username", "")).strip()
        if username:
            mapped["is_online"] = self.is_user_online(username)
        return mapped

    def _with_presence_list(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._with_presence(item) for item in items]

    def is_user_online(self, username: str) -> bool:
        with self._lock:
            return username in self._online_users

    def _make_handler(self) -> Type[socketserver.StreamRequestHandler]:
        controller = self

        class RequestHandler(socketserver.StreamRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.current_user: str | None = None

            def handle(self) -> None:
                while True:
                    raw = self.rfile.readline()
                    if not raw:
                        break
                    raw = raw.strip()
                    if not raw:
                        continue

                    try:
                        if raw.startswith(b"{"):
                            request = decode_request_line(raw)
                            response = self._handle_json(request)
                            self.wfile.write(response)
                            self.wfile.flush()
                            continue
                        response = self._handle_legacy(raw)
                        self.wfile.write(response)
                        self.wfile.flush()
                    except Exception as exc:  # noqa: BLE001
                        controller.log_signal.emit(f"协议处理异常: {exc}")
                        self.wfile.write(
                            encode_response_line(
                                ok=False,
                                code="server_error",
                                message="服务器内部错误",
                            )
                        )
                        self.wfile.flush()

            def finish(self) -> None:
                if self.current_user:
                    controller._set_online(self.current_user, False)
                super().finish()

            def _handle_legacy(self, raw: bytes) -> bytes:
                text = raw.decode("utf-8", errors="ignore").strip()
                parts = text.split()
                cmd = parts[0].upper() if parts else ""

                if cmd == "LOGIN":
                    if len(parts) < 3:
                        return b"ERR\n"
                    username = parts[1]
                    password = " ".join(parts[2:])
                    result = controller.db.verify_login_detail(username, password)
                    if result.ok:
                        self.current_user = username
                        controller._set_online(username, True)
                        controller.log_signal.emit(f'"{username}"请求登录, 登录成功')
                        return b"OK\n"
                    controller.log_signal.emit(f'"{username}"请求登录, 登录失败')
                    return b"FAIL\n"

                if cmd == "LOGOUT":
                    if len(parts) < 2:
                        return b"ERR\n"
                    username = parts[1]
                    if self.current_user == username:
                        self.current_user = None
                    controller._set_online(username, False)
                    controller.log_signal.emit(f'"{username}"已注销')
                    return b"OK\n"

                return b"ERR\n"

            def _handle_json(self, request: dict[str, Any]) -> bytes:
                action = str(request.get("action", "")).strip().lower()

                if action == "login":
                    username = str(request.get("username", "")).strip()
                    password = str(request.get("password", ""))
                    result = controller.db.verify_login_detail(username, password)
                    if result.ok:
                        self.current_user = username
                        controller._set_online(username, True)
                        controller.log_signal.emit(f'"{username}"请求登录, 登录成功')
                        return encode_response_line(
                            ok=True,
                            code=result.code,
                            message=result.message,
                            data={
                                "user": controller._with_presence(result.user),
                                "friends": controller._with_presence_list(
                                    controller.db.list_friends(username)
                                ),
                                "sessions": controller._with_presence_list(
                                    controller.db.list_sessions(username)
                                ),
                            },
                        )
                    controller.log_signal.emit(f'"{username}"请求登录, 登录失败')
                    return encode_response_line(
                        ok=False, code=result.code, message=result.message
                    )

                if action == "logout":
                    username = str(request.get("username", "")).strip()
                    if not username:
                        return encode_response_line(
                            ok=False,
                            code="invalid_request",
                            message="username is required",
                        )
                    if self.current_user == username:
                        self.current_user = None
                    controller._set_online(username, False)
                    controller.log_signal.emit(f'"{username}"已注销')
                    return encode_response_line(ok=True, code="ok", message="注销成功")

                if action == "register":
                    username = str(request.get("username", "")).strip()
                    password = str(request.get("password", ""))
                    encoding_rule = request.get("encoding_rule") or ["base64"]
                    try:
                        user = controller.db.register_user(
                            username=username,
                            password=password,
                            encoding_rule=encoding_rule,
                        )
                    except sqlite3.IntegrityError:
                        return encode_response_line(
                            ok=False,
                            code="user_exists",
                            message="用户名已存在",
                        )
                    except ValueError as exc:
                        return encode_response_line(
                            ok=False,
                            code="invalid_request",
                            message=str(exc),
                        )
                    controller.log_signal.emit(f'"{username}"注册成功')
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="注册成功",
                        data={"user": user},
                    )

                if action == "search_users":
                    username = str(request.get("username", "")).strip()
                    mode = str(request.get("mode", "fuzzy")).strip().lower()
                    query = str(request.get("query", "")).strip()
                    if mode == "id":
                        users = controller.db.search_user_by_id(
                            query, exclude_username=username or None
                        )
                    else:
                        users = controller.db.search_users_fuzzy(
                            query, exclude_username=username or None
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="搜索成功",
                        data={"users": controller._with_presence_list(users)},
                    )

                if action == "add_friend":
                    username = str(request.get("username", "")).strip()
                    friend_id = request.get("friend_id")
                    try:
                        friend = controller.db.add_friend(username, int(friend_id))
                    except ValueError as exc:
                        code = str(exc)
                        message_map = {
                            "user_not_found": "用户不存在",
                            "friend_not_found": "目标用户不存在",
                            "already_friend": "已经是好友",
                            "cannot_add_self": "不能添加自己为好友",
                        }
                        return encode_response_line(
                            ok=False,
                            code=code,
                            message=message_map.get(code, "添加好友失败"),
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="添加好友成功",
                        data={
                            "friend": controller._with_presence(friend),
                            "friends": controller._with_presence_list(
                                controller.db.list_friends(username)
                            ),
                        },
                    )

                if action == "list_friends":
                    username = str(request.get("username", "")).strip()
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="好友列表获取成功",
                        data={
                            "friends": controller._with_presence_list(
                                controller.db.list_friends(username)
                            )
                        },
                    )

                if action == "send_message":
                    sender = str(request.get("from", "")).strip()
                    receiver = str(request.get("to", "")).strip()
                    content = str(request.get("content", ""))
                    encoding_rule = request.get("encoding_rule") or []
                    try:
                        encoded_content = (
                            encode_sensitive_text(content, list(encoding_rule))
                            if encoding_rule
                            else content
                        )
                        message = controller.db.save_message(
                            sender=sender,
                            receiver=receiver,
                            content=encoded_content,
                            encoding_rule=encoding_rule,
                        )
                    except ValueError as exc:
                        return encode_response_line(
                            ok=False,
                            code="invalid_request",
                            message=str(exc),
                        )
                    controller.log_signal.emit(f'"{sender}"向"{receiver}"发送消息')
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="消息发送成功",
                        data={"message": message},
                    )

                if action == "pull_messages":
                    username = str(request.get("username", "")).strip()
                    since_id = int(request.get("since_id", 0) or 0)
                    peer = request.get("peer")
                    messages = controller.db.pull_messages(
                        username, since_id=since_id, peer=str(peer) if peer else None
                    )
                    decoded_messages = []
                    for item in messages:
                        rule = list(item.get("encoding_rule") or [])
                        decoded = dict(item)
                        if rule:
                            decoded["content"] = decode_sensitive_text(
                                str(item["content"]), rule
                            )
                        decoded_messages.append(decoded)
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="消息拉取成功",
                        data={"messages": decoded_messages},
                    )

                return encode_response_line(
                    ok=False,
                    code="invalid_request",
                    message="unsupported action",
                )

        return RequestHandler

    def _set_online(self, username: str, online: bool) -> None:
        with self._lock:
            if online:
                self._online_users[username] = username
            else:
                self._online_users.pop(username, None)

    def start(self, port: int) -> None:
        if self._server is not None:
            return
        handler_cls = self._make_handler()
        ssl_context = build_server_ssl_context()
        server = ThreadingTCPServer((self.host, int(port)), handler_cls, ssl_context)
        server.controller = self
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()
        self.log_signal.emit(f"TLS 已启用，证书目录: {cert_dir()}")

    def stop(self) -> None:
        if self._server is None:
            return
        server = self._server
        self._server = None
        server.shutdown()
        server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
