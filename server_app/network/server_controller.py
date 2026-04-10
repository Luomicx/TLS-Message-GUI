from __future__ import annotations

import json
import base64
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
        self._online_users: dict[str, socketserver.StreamRequestHandler] = {}
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

    def online_usernames(self) -> list[str]:
        with self._lock:
            return sorted(self._online_users)

    def online_user_count(self) -> int:
        with self._lock:
            return len(self._online_users)

    def _kick_existing_session(
        self, username: str, current: socketserver.StreamRequestHandler
    ) -> None:
        with self._lock:
            existing = self._online_users.get(username)
            if existing is None or existing is current:
                return
        try:
            existing.wfile.write(
                encode_response_line(
                    ok=False,
                    code="force_logout",
                    message="该账号已在另一台终端登录，你已被强制下线",
                    data={"reason": "single_session_conflict"},
                )
            )
            existing.wfile.flush()
        except Exception:
            pass

    def _make_handler(self) -> Type[socketserver.StreamRequestHandler]:
        controller = self

        class RequestHandler(socketserver.StreamRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.current_user: str | None = None

            def handle(self) -> None:
                while True:
                    try:
                        raw = self.rfile.readline()
                    except OSError:
                        break
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
                    controller._set_online(self.current_user, False, self)
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
                        controller._set_online(username, True, self)
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
                    controller._set_online(username, False, self)
                    controller.log_signal.emit(f'"{username}"已注销')
                    return b"OK\n"

                return b"ERR\n"

            def _build_session_invalid_response(self, username: str) -> bytes:
                if username and controller.is_user_online(username):
                    return encode_response_line(
                        ok=False,
                        code="force_logout",
                        message="该账号已在另一台终端登录，你已被强制下线",
                        data={"reason": "single_session_conflict"},
                    )
                return encode_response_line(
                    ok=False,
                    code="not_authenticated",
                    message="当前会话未登录或已失效，请重新登录",
                )

            def _require_authenticated_user(self, username: str) -> bytes | None:
                if not username:
                    return encode_response_line(
                        ok=False,
                        code="invalid_request",
                        message="username is required",
                    )
                if self.current_user == username:
                    return None
                return self._build_session_invalid_response(username)

            def _handle_json(self, request: dict[str, Any]) -> bytes:
                action = str(request.get("action", "")).strip().lower()

                if action == "login":
                    username = str(request.get("username", "")).strip()
                    password = str(request.get("password", ""))
                    result = controller.db.verify_login_detail(username, password)
                    if result.ok:
                        controller._kick_existing_session(username, self)
                        self.current_user = username
                        controller._set_online(username, True, self)
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
                        ok=False,
                        code=result.code,
                        message=result.message,
                        data={
                            "remaining_attempts": result.remaining_attempts,
                        },
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
                    controller._set_online(username, False, self)
                    controller.log_signal.emit(f'"{username}"已注销')
                    return encode_response_line(ok=True, code="ok", message="注销成功")

                if action == "register":
                    username = str(request.get("username", "")).strip()
                    password = str(request.get("password", ""))
                    question = str(request.get("question", "")).strip()
                    answer = str(request.get("answer", ""))
                    encoding_rule = request.get("encoding_rule") or ["base64"]
                    if not question or not answer.strip():
                        return encode_response_line(
                            ok=False,
                            code="recovery_required",
                            message="注册时必须设置安全问题和答案",
                        )
                    try:
                        user = controller.db.register_user(
                            username=username,
                            password=password,
                            recovery_question=question,
                            recovery_answer=answer,
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
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
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
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
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
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
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
                    auth_error = self._require_authenticated_user(sender)
                    if auth_error is not None:
                        return auth_error
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

                if action == "heartbeat":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    updated = controller.db.mark_heartbeat(username)
                    if not updated:
                        return encode_response_line(
                            ok=False,
                            code="user_not_found",
                            message="用户不存在",
                        )
                    if self.current_user == username:
                        controller._set_online(username, True, self)
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="heartbeat acknowledged",
                    )

                if action == "get_profile":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    profile = controller.db.get_profile(username)
                    if profile is None:
                        return encode_response_line(
                            ok=False,
                            code="user_not_found",
                            message="用户不存在",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="资料获取成功",
                        data={"profile": controller._with_presence(profile)},
                    )

                if action == "update_profile":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    nickname = str(request.get("nickname", "")).strip()
                    try:
                        profile = controller.db.update_profile(
                            username,
                            nickname=nickname,
                        )
                    except ValueError as exc:
                        code = str(exc)
                        return encode_response_line(
                            ok=False,
                            code=code if code else "invalid_request",
                            message="资料更新失败",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="资料更新成功",
                        data={"profile": controller._with_presence(profile)},
                    )

                if action == "change_password":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    old_password = str(request.get("old_password", ""))
                    new_password = str(request.get("new_password", ""))
                    try:
                        controller.db.change_password(username, old_password, new_password)
                    except ValueError as exc:
                        code = str(exc) or "invalid_request"
                        message_map = {
                            "user_not_found": "用户不存在",
                            "user_locked": "账号被锁定",
                            "invalid_credentials": "原密码错误",
                            "invalid_request": "请求参数无效",
                        }
                        return encode_response_line(
                            ok=False,
                            code=code,
                            message=message_map.get(code, "修改密码失败"),
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="密码修改成功",
                    )

                if action == "set_recovery":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    question = str(request.get("question", ""))
                    answer = str(request.get("answer", ""))
                    try:
                        controller.db.set_recovery_info(username, question, answer)
                    except ValueError as exc:
                        code = str(exc) or "invalid_request"
                        return encode_response_line(
                            ok=False,
                            code=code,
                            message="找回信息设置失败",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="找回信息设置成功",
                    )

                if action in {
                    "get_recovery_questions",
                    "get_recovery_question",
                    "load_recovery_questions",
                }:
                    username = str(request.get("username", "")).strip()
                    try:
                        questions = controller.db.get_recovery_questions(username)
                    except ValueError as exc:
                        code = str(exc) or "invalid_request"
                        message_map = {
                            "user_not_found": "用户不存在",
                            "recovery_not_set": "未设置找回信息",
                            "invalid_request": "请求参数无效",
                        }
                        return encode_response_line(
                            ok=False,
                            code=code,
                            message=message_map.get(code, "找回问题获取失败"),
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="找回问题获取成功",
                        data={"questions": questions},
                    )

                if action == "recover_password":
                    username = str(request.get("username", "")).strip()
                    question = str(request.get("question", ""))
                    answer = str(request.get("answer", ""))
                    new_password = str(request.get("new_password", ""))
                    try:
                        controller.db.recover_password(
                            username,
                            question=question,
                            answer=answer,
                            new_password=new_password,
                        )
                    except ValueError as exc:
                        code = str(exc) or "invalid_request"
                        message_map = {
                            "user_not_found": "用户不存在",
                            "recovery_not_set": "未设置找回信息",
                            "recovery_mismatch": "找回校验失败",
                            "invalid_request": "请求参数无效",
                        }
                        return encode_response_line(
                            ok=False,
                            code=code,
                            message=message_map.get(code, "密码找回失败"),
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="密码重置成功",
                    )

                if action == "pull_messages":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
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

                if action == "create_group":
                    owner = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(owner)
                    if auth_error is not None:
                        return auth_error
                    group_name = str(request.get("group_name", "")).strip()
                    members = list(request.get("members") or [])
                    try:
                        group = controller.db.create_group(owner, group_name, members)
                    except ValueError as exc:
                        return encode_response_line(
                            ok=False,
                            code=str(exc) or "invalid_request",
                            message="创建群聊失败",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="创建群聊成功",
                        data={"group": group},
                    )

                if action == "list_groups":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    groups = controller.db.list_groups(username)
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="群列表获取成功",
                        data={"groups": groups},
                    )

                if action == "send_group_message":
                    sender = str(request.get("sender", "")).strip()
                    auth_error = self._require_authenticated_user(sender)
                    if auth_error is not None:
                        return auth_error
                    group_id = int(request.get("group_id", 0) or 0)
                    content = str(request.get("content", ""))
                    encoding_rule = list(request.get("encoding_rule") or [])
                    try:
                        encoded_content = (
                            encode_sensitive_text(content, encoding_rule)
                            if encoding_rule
                            else content
                        )
                        message = controller.db.send_group_message(
                            group_id=group_id,
                            sender=sender,
                            content=encoded_content,
                            encoding_rule=encoding_rule,
                        )
                    except ValueError as exc:
                        return encode_response_line(
                            ok=False,
                            code=str(exc) or "invalid_request",
                            message="群消息发送失败",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="群消息发送成功",
                        data={"message": message},
                    )

                if action == "pull_group_messages":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    group_id = int(request.get("group_id", 0) or 0)
                    since_id = int(request.get("since_id", 0) or 0)
                    try:
                        items = controller.db.pull_group_messages(
                            username,
                            group_id=group_id,
                            since_id=since_id,
                        )
                    except ValueError as exc:
                        return encode_response_line(
                            ok=False,
                            code=str(exc) or "invalid_request",
                            message="群消息拉取失败",
                        )
                    out: list[dict[str, Any]] = []
                    for item in items:
                        mapped = dict(item)
                        rule = list(mapped.get("encoding_rule") or [])
                        if rule:
                            mapped["content"] = decode_sensitive_text(
                                str(mapped["content"]), rule
                            )
                        out.append(mapped)
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="群消息拉取成功",
                        data={"messages": out},
                    )

                if action == "send_file":
                    sender = str(request.get("sender", "")).strip()
                    auth_error = self._require_authenticated_user(sender)
                    if auth_error is not None:
                        return auth_error
                    receiver = str(request.get("receiver", "")).strip()
                    file_name = str(request.get("file_name", "")).strip()
                    file_base64 = str(request.get("file_base64", "")).strip()
                    try:
                        file_bytes = base64.b64decode(file_base64.encode("ascii"))
                        item = controller.db.send_file(
                            sender=sender,
                            receiver=receiver,
                            file_name=file_name,
                            file_bytes=file_bytes,
                        )
                    except Exception:
                        return encode_response_line(
                            ok=False,
                            code="invalid_file",
                            message="文件发送失败",
                        )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="文件发送成功",
                        data={"file": item},
                    )

                if action == "pull_files":
                    username = str(request.get("username", "")).strip()
                    auth_error = self._require_authenticated_user(username)
                    if auth_error is not None:
                        return auth_error
                    since_id = int(request.get("since_id", 0) or 0)
                    peer = request.get("peer")
                    items = controller.db.pull_files(
                        username,
                        since_id=since_id,
                        peer=str(peer) if peer else None,
                    )
                    return encode_response_line(
                        ok=True,
                        code="ok",
                        message="文件拉取成功",
                        data={"files": items},
                    )

                return encode_response_line(
                    ok=False,
                    code="invalid_request",
                    message="unsupported action",
                )

        return RequestHandler

    def _set_online(
        self,
        username: str,
        online: bool,
        handler: socketserver.StreamRequestHandler | None = None,
    ) -> None:
        with self._lock:
            if online:
                if handler is not None:
                    self._online_users[username] = handler
            else:
                if handler is None:
                    self._online_users.pop(username, None)
                    return
                current = self._online_users.get(username)
                if current is handler:
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
