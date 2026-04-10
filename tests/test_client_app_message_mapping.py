from __future__ import annotations

import importlib.util
import sys
import shutil
import types
import unittest
from pathlib import Path
import base64


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "client_app" / "app.py"


def load_app_module():
    original_modules = {
        name: sys.modules.get(name)
        for name in [
            "PyQt5",
            "PyQt5.QtCore",
            "PyQt5.QtWidgets",
            "client_app",
            "client_app.network",
            "client_app.ui",
            "client_app.app",
        ]
    }

    qtcore = types.ModuleType("PyQt5.QtCore")
    qtcore.QObject = type("QObject", (), {})
    class QTimer:
        def __init__(self, *_args, **_kwargs):
            pass

        def setInterval(self, *_args, **_kwargs):
            return None

        @property
        def timeout(self):
            return types.SimpleNamespace(connect=lambda *_args, **_kwargs: None)

        def isActive(self):
            return False

        def start(self):
            return None

        def stop(self):
            return None

    qtcore.QTimer = QTimer
    qtcore.Qt = types.SimpleNamespace(
        AA_EnableHighDpiScaling=1,
        AA_UseHighDpiPixmaps=2,
    )

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")

    class QApplication:
        @staticmethod
        def setAttribute(*_args, **_kwargs):
            return None

        @staticmethod
        def instance():
            return types.SimpleNamespace(exec_=lambda: 0)

    qtwidgets.QApplication = QApplication

    pyqt5 = types.ModuleType("PyQt5")
    sys.modules["PyQt5"] = pyqt5
    sys.modules["PyQt5.QtCore"] = qtcore
    sys.modules["PyQt5.QtWidgets"] = qtwidgets

    network_module = types.ModuleType("client_app.network")
    network_module.ClientController = type("ClientController", (), {})
    sys.modules["client_app.network"] = network_module

    ui_module = types.ModuleType("client_app.ui")
    ui_module.ChatWindow = type("ChatWindow", (), {})
    ui_module.LoginWindow = type("LoginWindow", (), {})
    sys.modules["client_app.ui"] = ui_module

    package_module = types.ModuleType("client_app")
    package_module.__path__ = [str(PROJECT_ROOT / "client_app")]
    sys.modules["client_app"] = package_module

    spec = importlib.util.spec_from_file_location("client_app.app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    for name, original in original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
    return module


app_module = load_app_module()
ClientApplication = app_module.ClientApplication


class ClientAppMessageMappingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = ClientApplication.__new__(ClientApplication)
        self.temp_download_root = PROJECT_ROOT / ".tmp_receive_test"
        if self.temp_download_root.exists():
            shutil.rmtree(self.temp_download_root, ignore_errors=True)
        self.app.download_root = self.temp_download_root
        self.app.previous_last_seen_at = None
        self.app.session_catalog = {}
        self.app.last_inbox_message_id = 0
        self.app.last_inbox_file_id = 0
        self.app.group_last_loaded_message_ids = {}
        self.app._received_file_ids = set()
        self.app._received_file_paths = {}
        self.app.chat_window = types.SimpleNamespace(
            upsert_session=lambda payload: None,
            set_current_user=lambda user: None,
        )
        self.app._choose_receive_target_path = lambda **kwargs: kwargs["default_path"]

    def tearDown(self) -> None:
        if self.temp_download_root.exists():
            shutil.rmtree(self.temp_download_root, ignore_errors=True)

    def test_login_invalid_credentials_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {
                "ok": False,
                "code": "invalid_credentials",
                "message": "bad password",
                "data": {"remaining_attempts": 3},
            },
            default_message="登录失败",
        )
        self.assertEqual(message, "账号或密码错误，再失败 3 次将锁定账户")

    def test_search_user_not_found_maps_to_search_specific_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "user_not_found", "message": "not found"},
            default_message="搜索失败",
        )
        self.assertEqual(message, "未找到符合条件的用户")

    def test_add_friend_already_friend_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "already_friend", "message": "already"},
            default_message="添加好友完成",
        )
        self.assertEqual(message, "对方已经是你的好友，无需重复添加")

    def test_send_message_network_error_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {
                "ok": False,
                "code": "network_error",
                "message": "服务器连接失败: timeout",
            },
            default_message="消息发送完成",
        )
        self.assertEqual(message, "网络连接失败，请检查服务器状态后重试")

    def test_load_messages_friend_not_found_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "friend_not_found", "message": "missing friend"},
            default_message="消息加载失败",
        )
        self.assertEqual(message, "未找到该好友或会话")

    def test_force_logout_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "force_logout", "message": "kicked"},
            default_message="账号已下线",
        )
        self.assertEqual(message, "你的账号已在其他终端登录，当前会话已下线")

    def test_recovery_mismatch_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "recovery_mismatch", "message": "mismatch"},
            default_message="密码找回失败",
        )
        self.assertEqual(message, "找回问题或答案不正确")

    def test_server_update_required_maps_to_restart_hint(self) -> None:
        message = self.app._resolve_user_message(
            {
                "ok": False,
                "code": "server_update_required",
                "message": "unsupported action",
            },
            default_message="找回问题加载失败",
        )
        self.assertEqual(message, "服务端未加载找回问题接口，请重启服务端后重试")

    def test_success_message_keeps_backend_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": True, "code": "ok", "message": "搜索完成，共 2 条结果"},
            default_message="搜索成功",
        )
        self.assertEqual(message, "搜索完成，共 2 条结果")

    def test_incremental_merge_does_not_clear_existing_transcript(self) -> None:
        self.app.current_rendered_messages = [
            {
                "content": "older",
                "sender": "alice",
                "created_at": "2026-01-01 10:00:00",
                "outgoing": True,
            }
        ]
        self.app._rendered_message_keys = {
            self.app._message_key(self.app.current_rendered_messages[0])
        }

        changed = self.app._merge_rendered_messages([], replace=False)

        self.assertFalse(changed)
        self.assertEqual(len(self.app.current_rendered_messages), 1)
        self.assertEqual(self.app.current_rendered_messages[0]["content"], "older")

    def test_incremental_merge_appends_new_messages(self) -> None:
        self.app.current_rendered_messages = [
            {
                "content": "older",
                "sender": "alice",
                "created_at": "2026-01-01 10:00:00",
                "outgoing": True,
            }
        ]
        self.app._rendered_message_keys = {
            self.app._message_key(self.app.current_rendered_messages[0])
        }

        changed = self.app._merge_rendered_messages(
            [
                {
                    "content": "newer",
                    "sender": "bob",
                    "created_at": "2026-01-01 10:01:00",
                    "outgoing": False,
                }
            ],
            replace=False,
        )

        self.assertTrue(changed)
        self.assertEqual(
            [item["content"] for item in self.app.current_rendered_messages],
            ["older", "newer"],
        )

    def test_persist_incoming_file_writes_to_local_download_root(self) -> None:
        payload = b"hello file payload"
        saved, saved_now = self.app._persist_incoming_file(
            "bob",
            "alice",
            {
                "id": 7,
                "sender": "alice",
                "receiver": "bob",
                "file_name": "demo.txt",
                "file_base64": base64.b64encode(payload).decode("ascii"),
            },
        )

        self.assertTrue(saved_now)
        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertTrue(saved.exists())
        self.assertEqual(saved.read_bytes(), payload)

    def test_persist_incoming_file_respects_selected_target_path(self) -> None:
        payload = b"custom target payload"
        custom_target = self.temp_download_root / "custom" / "picked.bin"
        self.app._choose_receive_target_path = lambda **_kwargs: custom_target

        saved, saved_now = self.app._persist_incoming_file(
            "bob",
            "alice",
            {
                "id": 8,
                "sender": "alice",
                "receiver": "bob",
                "file_name": "demo.bin",
                "file_base64": base64.b64encode(payload).decode("ascii"),
            },
        )

        self.assertTrue(saved_now)
        self.assertEqual(saved, custom_target)
        self.assertTrue(custom_target.exists())
        self.assertEqual(custom_target.read_bytes(), payload)

    def test_persist_incoming_file_reuses_previous_saved_path(self) -> None:
        payload = b"sticky target payload"
        custom_target = self.temp_download_root / "chosen" / "sticky.bin"
        chooser_calls: list[dict] = []

        def choose_once(**kwargs):
            chooser_calls.append(kwargs)
            return custom_target

        self.app._choose_receive_target_path = choose_once

        first_saved, first_saved_now = self.app._persist_incoming_file(
            "bob",
            "alice",
            {
                "id": 9,
                "sender": "alice",
                "receiver": "bob",
                "file_name": "sticky.bin",
                "file_base64": base64.b64encode(payload).decode("ascii"),
            },
        )
        second_saved, second_saved_now = self.app._persist_incoming_file(
            "bob",
            "alice",
            {
                "id": 9,
                "sender": "alice",
                "receiver": "bob",
                "file_name": "sticky.bin",
                "file_base64": base64.b64encode(payload).decode("ascii"),
            },
        )

        self.assertTrue(first_saved_now)
        self.assertFalse(second_saved_now)
        self.assertEqual(first_saved, custom_target)
        self.assertEqual(second_saved, custom_target)
        self.assertEqual(len(chooser_calls), 1)

    def test_sync_group_sessions_upserts_group_into_session_list(self) -> None:
        calls: list[dict] = []
        self.app.chat_window = types.SimpleNamespace(
            upsert_session=lambda payload: calls.append(payload)
        )

        self.app._sync_group_sessions(
            [
                {
                    "id": 12,
                    "name": "项目组",
                    "members": ["alice", "bob"],
                }
            ]
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["username"], "[群]项目组#12")

    def test_send_message_routes_group_session_to_group_api(self) -> None:
        notices: list[str] = []
        refresh_calls: list[tuple[str, str]] = []
        controller_calls: list[tuple[str, tuple, dict]] = []

        class FakeController:
            def send_message(self, *args, **kwargs):
                controller_calls.append(("private", args, kwargs))
                return {"ok": True, "message": "私聊消息发送成功"}

            def send_group_message(self, *args, **kwargs):
                controller_calls.append(("group", args, kwargs))
                return {"ok": True, "message": "群消息发送成功"}

        self.app.client_controller = FakeController()
        self.app.current_user = {"username": "alice", "encoding_rule": ["base64"]}
        self.app.chat_window = types.SimpleNamespace(
            show_notice=lambda text: notices.append(text)
        )
        self.app._refresh_messages = (
            lambda peer, *, reason: refresh_calls.append((peer, reason))
        )

        self.app.send_message("[群]项目组#12", "hello group")

        self.assertEqual(len(controller_calls), 1)
        self.assertEqual(controller_calls[0][0], "group")
        self.assertEqual(
            controller_calls[0][1],
            ("alice", 12, "hello group", ["base64"]),
        )
        self.assertEqual(notices, ["群消息发送成功"])
        self.assertEqual(refresh_calls, [("[群]项目组#12", "send_success")])

    def test_mark_session_attention_accumulates_unread_and_keeps_last_activity(self) -> None:
        captured: list[dict[str, object]] = []
        self.app.chat_window = types.SimpleNamespace(
            upsert_session=lambda payload: captured.append(dict(payload))
        )

        self.app._upsert_session_record({"username": "bob", "nickname": "Bob"})
        self.app._mark_session_attention(
            "bob",
            unread_increment=2,
            has_offline_messages=True,
            last_message_at="2026-04-06 10:00:00",
        )

        self.assertEqual(self.app.session_catalog["bob"]["unread_count"], 2)
        self.assertTrue(self.app.session_catalog["bob"]["has_offline_messages"])
        self.assertEqual(
            self.app.session_catalog["bob"]["last_message_at"], "2026-04-06 10:00:00"
        )
        self.assertEqual(captured[-1]["unread_count"], 2)

    def test_clear_session_attention_resets_unread_and_offline_flags(self) -> None:
        captured: list[dict[str, object]] = []
        self.app.chat_window = types.SimpleNamespace(
            upsert_session=lambda payload: captured.append(dict(payload))
        )
        self.app.session_catalog = {
            "bob": {
                "username": "bob",
                "nickname": "Bob",
                "unread_count": 4,
                "has_offline_messages": True,
            }
        }

        self.app._clear_session_attention("bob")

        self.assertEqual(self.app.session_catalog["bob"]["unread_count"], 0)
        self.assertFalse(self.app.session_catalog["bob"]["has_offline_messages"])
        self.assertEqual(captured[-1]["unread_count"], 0)

    def test_offline_candidate_uses_previous_last_seen_timestamp(self) -> None:
        self.app.previous_last_seen_at = "2026-04-06 10:00:00"

        self.assertTrue(self.app._is_offline_candidate("2026-04-06 10:05:00"))
        self.assertFalse(self.app._is_offline_candidate("2026-04-06 09:55:00"))

    def test_update_profile_refreshes_current_user_and_sidebar_summary(self) -> None:
        sidebar_updates: list[dict[str, object]] = []

        class FakeController:
            def update_profile(self, username: str, nickname: str) -> dict[str, object]:
                return {
                    "ok": True,
                    "data": {
                        "profile": {
                            "username": username,
                            "nickname": nickname,
                        }
                    },
                }

        self.app.client_controller = FakeController()
        self.app.current_user = {"username": "alice", "nickname": "alice"}
        self.app.chat_window = types.SimpleNamespace(
            set_current_user=lambda user: sidebar_updates.append(dict(user))
        )

        response = self.app.update_profile("AliceNew")

        self.assertTrue(response["ok"])
        self.assertEqual(self.app.current_user["nickname"], "AliceNew")
        self.assertEqual(sidebar_updates[-1]["nickname"], "AliceNew")


if __name__ == "__main__":
    unittest.main()
