from __future__ import annotations

import socket
import ssl
import threading
import base64
from pathlib import Path
from typing import Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal

from ..protocol import decode_response, encode_request
from tls_support import build_client_ssl_context


class ClientController(QObject):
    CONNECT_TIMEOUT_SECONDS = 5
    FILE_REQUEST_LOCK_TIMEOUT_SECONDS = 30.0
    FILE_CHUNK_SIZE = 256 * 1024

    login_finished = pyqtSignal(dict)
    register_finished = pyqtSignal(dict)
    friends_loaded = pyqtSignal(dict)
    search_finished = pyqtSignal(dict)
    message_sent = pyqtSignal(dict)
    messages_loaded = pyqtSignal(dict)
    logout_finished = pyqtSignal(dict)
    forced_logout = pyqtSignal(dict)
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

    def register(
        self, username: str, password: str, question: str, answer: str
    ) -> dict[str, Any]:
        response = self._request(
            {
                "action": "register",
                "username": username,
                "password": password,
                "question": question,
                "answer": answer,
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

    def add_friend(
        self, username: str, friend_id: int, request_note: str = ""
    ) -> dict[str, Any]:
        response = self._request(
            {
                "action": "add_friend",
                "username": username,
                "friend_id": int(friend_id),
                "request_note": request_note,
            }
        )
        self.friends_loaded.emit(response)
        return response

    def list_friends(self, username: str) -> dict[str, Any]:
        response = self._request({"action": "list_friends", "username": username})
        self.friends_loaded.emit(response)
        return response

    def accept_friend_request(self, username: str, friend_id: int) -> dict[str, Any]:
        response = self._request(
            {
                "action": "accept_friend_request",
                "username": username,
                "friend_id": int(friend_id),
            }
        )
        self.friends_loaded.emit(response)
        return response

    def reject_friend_request(
        self, username: str, friend_id: int, decision_note: str = ""
    ) -> dict[str, Any]:
        response = self._request(
            {
                "action": "reject_friend_request",
                "username": username,
                "friend_id": int(friend_id),
                "decision_note": decision_note,
            }
        )
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

    def heartbeat(self, username: str) -> dict[str, Any]:
        return self._request({"action": "heartbeat", "username": username})

    def get_profile(self, username: str) -> dict[str, Any]:
        return self._request({"action": "get_profile", "username": username})

    def update_profile(self, username: str, nickname: str) -> dict[str, Any]:
        return self._request(
            {"action": "update_profile", "username": username, "nickname": nickname}
        )

    def change_password(
        self, username: str, old_password: str, new_password: str
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "change_password",
                "username": username,
                "old_password": old_password,
                "new_password": new_password,
            }
        )

    def set_recovery(self, username: str, question: str, answer: str) -> dict[str, Any]:
        return self._request(
            {
                "action": "set_recovery",
                "username": username,
                "question": question,
                "answer": answer,
            }
        )

    def get_recovery_questions(self, username: str) -> dict[str, Any]:
        response = self._request(
            {
                "action": "get_recovery_questions",
                "username": username,
            }
        )
        if (
            not response.get("ok", False)
            and str(response.get("message", "")).strip().lower() == "unsupported action"
        ):
            return {
                "ok": False,
                "code": "server_update_required",
                "message": "服务端未加载找回问题接口，请重启服务端后重试",
                "data": {},
            }
        return response

    def recover_password(
        self, username: str, question: str, answer: str, new_password: str
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "recover_password",
                "username": username,
                "question": question,
                "answer": answer,
                "new_password": new_password,
            }
        )

    def create_group(
        self,
        username: str,
        group_name: str,
        members: list[str] | None = None,
        invite_note: str = "",
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "create_group",
                "username": username,
                "group_name": group_name,
                "members": list(members or []),
                "invite_note": invite_note,
            }
        )

    def process_group_join_request(
        self,
        username: str,
        request_id: int,
        *,
        decision: str,
        decision_note: str = "",
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "process_group_join_request",
                "username": username,
                "request_id": int(request_id),
                "decision": decision,
                "decision_note": decision_note,
            }
        )

    def list_groups(self, username: str) -> dict[str, Any]:
        return self._request({"action": "list_groups", "username": username})

    def send_group_message(
        self,
        sender: str,
        group_id: int,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "send_group_message",
                "sender": sender,
                "group_id": int(group_id),
                "content": content,
                "encoding_rule": list(encoding_rule or []),
            }
        )

    def pull_group_messages(
        self, username: str, group_id: int, *, since_id: int = 0
    ) -> dict[str, Any]:
        return self._request(
            {
                "action": "pull_group_messages",
                "username": username,
                "group_id": int(group_id),
                "since_id": int(since_id),
            }
        )

    def send_file(
        self, sender: str, receiver: str, file_name: str, file_bytes: bytes
    ) -> dict[str, Any]:
        return self._send_file_chunks(
            sender=sender,
            receiver=receiver,
            file_name=file_name,
            file_size=len(file_bytes),
            chunk_iterable=(bytes(file_bytes[index : index + self.FILE_CHUNK_SIZE]) for index in range(0, len(file_bytes), self.FILE_CHUNK_SIZE)),
            progress_callback=None,
        )

    def send_file_path(
        self,
        sender: str,
        receiver: str,
        file_path: str,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        file_size = path.stat().st_size

        def iter_chunks() -> Any:
            with path.open("rb") as file_handle:
                while True:
                    chunk = file_handle.read(self.FILE_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return self._send_file_chunks(
            sender=sender,
            receiver=receiver,
            file_name=path.name,
            file_size=file_size,
            chunk_iterable=iter_chunks(),
            progress_callback=progress_callback,
        )

    def pull_files(
        self, username: str, *, since_id: int = 0, peer: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "pull_files",
            "username": username,
            "since_id": int(since_id),
        }
        if peer:
            payload["peer"] = peer
        return self._request(payload)

    def _ensure_connection(self) -> socket.socket | ssl.SSLSocket:
        if self._sock is None:
            raw_sock = socket.create_connection(
                (self.host, self.port),
                timeout=self.CONNECT_TIMEOUT_SECONDS,
            )
            self._sock = self._ssl_context.wrap_socket(
                raw_sock,
                server_hostname=self.host,
            )
            self._sock.settimeout(None)
        return self._sock

    def _request(
        self,
        payload: dict[str, Any],
        *,
        wait_for_slot: bool = False,
        lock_timeout: float | None = None,
    ) -> dict[str, Any]:
        if wait_for_slot:
            if lock_timeout is None:
                acquired = self._request_lock.acquire()
            else:
                acquired = self._request_lock.acquire(timeout=lock_timeout)
        else:
            acquired = self._request_lock.acquire(blocking=False)
        if not acquired:
            message = "当前连接仍在处理其他请求，请稍后重试"
            self.error_occurred.emit(message)
            return {
                "ok": False,
                "code": "request_busy",
                "message": message,
                "data": {},
            }
        self._request_in_flight = True
        try:
            return self._perform_request(payload, allow_retry=True)
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

    def _perform_request(
        self, payload: dict[str, Any], *, allow_retry: bool
    ) -> dict[str, Any]:
        try:
            sock = self._ensure_connection()
            sock.sendall(encode_request(payload))
            response = self._recv_line(sock)
            data = decode_response(response)
        except (ConnectionError, OSError, ssl.SSLError):
            self.close()
            if allow_retry and self._should_retry_after_disconnect(payload):
                return self._perform_request(payload, allow_retry=False)
            raise
        if str(data.get("code", "")) == "force_logout":
            self.close()
            self.forced_logout.emit(data)
            return data
        if not data.get("ok", False):
            self.error_occurred.emit(str(data.get("message", "请求失败")))
        return data

    def _should_retry_after_disconnect(self, payload: dict[str, Any]) -> bool:
        action = str(payload.get("action", "")).strip().lower()
        return action not in {"login", "register", "recover_password"}

    def _send_file_chunks(
        self,
        *,
        sender: str,
        receiver: str,
        file_name: str,
        file_size: int,
        chunk_iterable,
        progress_callback: Callable[[int, int], None] | None,
    ) -> dict[str, Any]:
        acquired = self._request_lock.acquire(
            timeout=self.FILE_REQUEST_LOCK_TIMEOUT_SECONDS
        )
        if not acquired:
            message = "当前连接仍在处理其他请求，请稍后重试"
            self.error_occurred.emit(message)
            return {
                "ok": False,
                "code": "request_busy",
                "message": message,
                "data": {},
            }

        self._request_in_flight = True
        upload_id = ""
        bytes_sent = 0
        try:
            start_response = self._perform_request(
                {
                    "action": "start_file_upload",
                    "sender": sender,
                    "receiver": receiver,
                    "file_name": file_name,
                    "file_size": int(file_size),
                },
                allow_retry=True,
            )
            if (
                not start_response.get("ok", False)
                and str(start_response.get("message", "")).strip().lower()
                == "unsupported action"
            ):
                return {
                    "ok": False,
                    "code": "server_update_required",
                    "message": "服务端还是旧版本，未加载分片文件接口，请重启服务端后重试",
                    "data": {},
                }
            if not start_response.get("ok", False):
                return start_response

            upload_id = str(
                start_response.get("data", {}).get("upload_id") or ""
            ).strip()
            if not upload_id:
                return {
                    "ok": False,
                    "code": "upload_session_invalid",
                    "message": "文件上传会话初始化失败",
                    "data": {},
                }

            if progress_callback is not None:
                progress_callback(0, int(file_size))

            for chunk_index, chunk in enumerate(chunk_iterable):
                chunk_response = self._perform_request(
                    {
                        "action": "upload_file_chunk",
                        "sender": sender,
                        "upload_id": upload_id,
                        "chunk_index": int(chunk_index),
                        "chunk_size": len(chunk),
                        "chunk_base64": base64.b64encode(chunk).decode("ascii"),
                    },
                    allow_retry=True,
                )
                if not chunk_response.get("ok", False):
                    self._cancel_upload(sender, upload_id)
                    return chunk_response
                bytes_sent += len(chunk)
                if progress_callback is not None:
                    progress_callback(bytes_sent, int(file_size))

            finish_response = self._perform_request(
                {
                    "action": "finish_file_upload",
                    "sender": sender,
                    "upload_id": upload_id,
                },
                allow_retry=True,
            )
            if progress_callback is not None:
                progress_callback(int(file_size), int(file_size))
            return finish_response
        except Exception as exc:  # noqa: BLE001
            if upload_id:
                self._cancel_upload(sender, upload_id)
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

    def _cancel_upload(self, sender: str, upload_id: str) -> None:
        try:
            self._perform_request(
                {
                    "action": "cancel_file_upload",
                    "sender": sender,
                    "upload_id": upload_id,
                },
                allow_retry=False,
            )
        except Exception:
            return None

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
