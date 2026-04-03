from __future__ import annotations

import socket
import ssl
import threading
from typing import Any

from PyQt5.QtCore import QObject, pyqtSignal

from ..protocol import decode_response, encode_request
from tls_support import build_client_ssl_context


class ClientController(QObject):
    login_finished = pyqtSignal(dict)
    register_finished = pyqtSignal(dict)
    friends_loaded = pyqtSignal(dict)
    search_finished = pyqtSignal(dict)
    message_sent = pyqtSignal(dict)
    messages_loaded = pyqtSignal(dict)
    logout_finished = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, host: str = "127.0.0.1", port: int = 8000, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = int(port)
        self._ssl_context = build_client_ssl_context()
        self._sock: socket.socket | ssl.SSLSocket | None = None
        self._request_lock = threading.Lock()
        self._request_in_flight = False

    @property
    def request_in_flight(self) -> bool:
        return self._request_in_flight

    def set_server(self, host: str, port: int) -> None:
        reconnect = host != self.host or int(port) != self.port
        self.host = host
        self.port = int(port)
        if reconnect:
            self.close()

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def login(self, username: str, password: str) -> dict[str, Any]:
        response = self._request(
            {"action": "login", "username": username, "password": password}
        )
        self.login_finished.emit(response)
        return response

    def logout(self, username: str) -> dict[str, Any]:
        response = self._request({"action": "logout", "username": username})
        self.logout_finished.emit(response)
        return response

    def register(self, username: str, password: str) -> dict[str, Any]:
        response = self._request(
            {
                "action": "register",
                "username": username,
                "password": password,
            }
        )
        self.register_finished.emit(response)
        return response

    def search_users(self, username: str, mode: str, query: str) -> dict[str, Any]:
        response = self._request(
            {
                "action": "search_users",
                "username": username,
                "mode": mode,
                "query": query,
            }
        )
        self.search_finished.emit(response)
        return response

    def add_friend(self, username: str, friend_id: int) -> dict[str, Any]:
        response = self._request(
            {
                "action": "add_friend",
                "username": username,
                "friend_id": int(friend_id),
            }
        )
        self.friends_loaded.emit(response)
        return response

    def list_friends(self, username: str) -> dict[str, Any]:
        response = self._request({"action": "list_friends", "username": username})
        self.friends_loaded.emit(response)
        return response

    def send_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            {
                "action": "send_message",
                "from": sender,
                "to": receiver,
                "content": content,
                "encoding_rule": encoding_rule or [],
            }
        )
        self.message_sent.emit(response)
        return response

    def pull_messages(
        self, username: str, *, since_id: int = 0, peer: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "pull_messages",
            "username": username,
            "since_id": int(since_id),
        }
        if peer:
            payload["peer"] = peer
        response = self._request(payload)
        self.messages_loaded.emit(response)
        return response

    def _ensure_connection(self) -> socket.socket | ssl.SSLSocket:
        if self._sock is None:
            raw_sock = socket.create_connection((self.host, self.port), timeout=5)
            self._sock = self._ssl_context.wrap_socket(
                raw_sock,
                server_hostname=self.host,
            )
        return self._sock

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._request_lock.acquire(blocking=False):
            message = "当前连接仍在处理上一条请求，请稍后重试"
            self.error_occurred.emit(message)
            return {
                "ok": False,
                "code": "request_busy",
                "message": message,
                "data": {},
            }
        self._request_in_flight = True
        try:
            sock = self._ensure_connection()
            sock.sendall(encode_request(payload))
            response = self._recv_line(sock)
            data = decode_response(response)
            if not data.get("ok", False):
                self.error_occurred.emit(str(data.get("message", "请求失败")))
            return data
        except Exception as exc:  # noqa: BLE001
            self.close()
            message = f"服务器连接失败: {exc}"
            self.error_occurred.emit(message)
            return {
                "ok": False,
                "code": "network_error",
                "message": message,
                "data": {},
            }
        finally:
            self._request_in_flight = False
            self._request_lock.release()

    def _recv_line(self, sock: socket.socket) -> bytes:
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("服务器已断开连接")
            chunks.append(chunk)
            if b"\n" in chunk:
                break
        joined = b"".join(chunks)
        return joined.splitlines()[0]
