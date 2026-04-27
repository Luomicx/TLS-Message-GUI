from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import Mock, patch

from client_app.network.client_controller import ClientController


class ClientControllerFileUploadTest(unittest.TestCase):
    def test_send_file_waits_for_previous_request_to_finish(self) -> None:
        controller = ClientController()
        controller._request_lock.acquire()
        results: list[dict[str, object]] = []

        def fake_perform_request(
            payload: dict[str, object], *, allow_retry: bool
        ) -> dict[str, object]:
            action = str(payload.get("action") or "")
            if action == "start_file_upload":
                return {
                    "ok": True,
                    "code": "ok",
                    "message": "文件上传已开始",
                    "data": {"upload_id": "wait-upload"},
                }
            return {"ok": True, "code": "ok", "message": "文件发送成功", "data": {}}

        controller._perform_request = fake_perform_request  # type: ignore[method-assign]

        worker = threading.Thread(
            target=lambda: results.append(
                controller.send_file("alice", "bob", "demo.txt", b"payload")
            )
        )

        worker.start()
        time.sleep(0.2)
        self.assertTrue(worker.is_alive())

        controller._request_lock.release()
        worker.join(timeout=2)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["ok"])
        self.assertEqual(results[0]["code"], "ok")

    def test_connection_timeout_is_cleared_after_connect(self) -> None:
        controller = ClientController()
        wrapped_socket = Mock()
        ssl_context = Mock()
        ssl_context.wrap_socket.return_value = wrapped_socket
        controller._ssl_context = ssl_context

        with patch("client_app.network.client_controller.socket.create_connection") as create_connection:
            raw_socket = Mock()
            create_connection.return_value = raw_socket

            sock = controller._ensure_connection()

        self.assertIs(sock, wrapped_socket)
        create_connection.assert_called_once_with(
            ("127.0.0.1", 8000),
            timeout=controller.CONNECT_TIMEOUT_SECONDS,
        )
        wrapped_socket.settimeout.assert_called_once_with(None)

    def test_send_file_uses_chunk_upload_sequence(self) -> None:
        controller = ClientController()
        payload = b"a" * (controller.FILE_CHUNK_SIZE + 17)
        captured_actions: list[str] = []
        captured_chunks: list[int] = []

        def fake_perform_request(
            payload: dict[str, object], *, allow_retry: bool
        ) -> dict[str, object]:
            action = str(payload.get("action") or "")
            captured_actions.append(action)
            if action == "start_file_upload":
                return {
                    "ok": True,
                    "code": "ok",
                    "message": "文件上传已开始",
                    "data": {"upload_id": "up-1"},
                }
            if action == "upload_file_chunk":
                captured_chunks.append(int(payload.get("chunk_size") or 0))
                return {"ok": True, "code": "ok", "message": "分片成功", "data": {}}
            if action == "finish_file_upload":
                return {"ok": True, "code": "ok", "message": "文件发送成功", "data": {}}
            return {"ok": True, "code": "ok", "message": "ok", "data": {}}

        controller._perform_request = fake_perform_request  # type: ignore[method-assign]

        response = controller.send_file("alice", "bob", "demo.bin", payload)

        self.assertTrue(response["ok"])
        self.assertEqual(
            captured_actions,
            ["start_file_upload", "upload_file_chunk", "upload_file_chunk", "finish_file_upload"],
        )
        self.assertEqual(
            captured_chunks,
            [controller.FILE_CHUNK_SIZE, 17],
        )

    def test_send_file_path_reports_progress(self) -> None:
        controller = ClientController()
        progress: list[tuple[int, int]] = []

        def fake_send_chunks(**kwargs):
            kwargs["progress_callback"](0, 10)
            kwargs["progress_callback"](4, 10)
            kwargs["progress_callback"](10, 10)
            return {"ok": True, "code": "ok", "message": "文件发送成功", "data": {}}

        controller._send_file_chunks = fake_send_chunks  # type: ignore[method-assign]

        with patch("client_app.network.client_controller.Path.stat") as mock_stat:
            mock_stat.return_value = Mock(st_size=10)
            with patch("client_app.network.client_controller.Path.open") as mock_open:
                file_handle = Mock()
                file_handle.read.side_effect = [b"1234", b"567890", b""]
                mock_open.return_value.__enter__.return_value = file_handle

                response = controller.send_file_path(
                    "alice",
                    "bob",
                    "demo.bin",
                    progress_callback=lambda sent, total: progress.append((sent, total)),
                )

        self.assertTrue(response["ok"])
        self.assertEqual(progress, [(0, 10), (4, 10), (10, 10)])


if __name__ == "__main__":
    unittest.main()
