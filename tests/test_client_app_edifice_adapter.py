from __future__ import annotations

import sys
import types
import unittest
from typing import cast
from typing_extensions import override

from client_app_edifice.adapter import ProtocolAdapter


class FakeController:
    def __init__(self) -> None:
        self.login_response: dict[str, object] = {
            "ok": True,
            "code": "ok",
            "message": "登录成功",
            "data": {
                "user": {
                    "username": "alice",
                    "is_online": True,
                    "encoding_rule": ["base64"],
                },
                "sessions": [
                    {"username": "bob", "is_online": True},
                    {"username": "carol", "is_online": False},
                ],
            },
        }
        self.logout_response: dict[str, object] = {
            "ok": True,
            "code": "ok",
            "message": "已注销",
            "data": {},
        }
        self.list_friends_response: dict[str, object] = {
            "ok": True,
            "code": "ok",
            "message": "好友列表已刷新",
            "data": {
                "friends": [
                    {"username": "bob", "is_online": True},
                    {"username": "carol", "is_online": False},
                ]
            },
        }
        self.send_message_response: dict[str, object] = {
            "ok": True,
            "code": "ok",
            "message": "消息发送成功",
            "data": {},
        }
        self.pull_messages_response: dict[str, object] = {
            "ok": True,
            "code": "ok",
            "message": "消息加载成功",
            "data": {
                "messages": [
                    {
                        "sender": "alice",
                        "content": "hello",
                        "created_at": "2026-03-24 10:00:00",
                    },
                    {
                        "sender": "bob",
                        "content": "hi",
                        "created_at": "2026-03-24 10:01:00",
                    },
                ]
            },
        }
        self.sent_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
        self.closed: bool = False

    def login(self, username: str, password: str) -> dict[str, object]:
        self.sent_calls.append(("login", (username, password), {}))
        return self.login_response

    def logout(self, username: str) -> dict[str, object]:
        self.sent_calls.append(("logout", (username,), {}))
        return self.logout_response

    def list_friends(self, username: str) -> dict[str, object]:
        self.sent_calls.append(("list_friends", (username,), {}))
        return self.list_friends_response

    def send_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> dict[str, object]:
        self.sent_calls.append(
            ("send_message", (sender, receiver, content, encoding_rule), {})
        )
        return self.send_message_response

    def pull_messages(
        self, username: str, *, since_id: int = 0, peer: str | None = None
    ) -> dict[str, object]:
        self.sent_calls.append(
            ("pull_messages", (username,), {"since_id": since_id, "peer": peer})
        )
        return self.pull_messages_response

    def close(self) -> None:
        self.closed = True


class ClientControllerModule(types.ModuleType):
    ClientController: type | None = None


class NetworkPackageModule(types.ModuleType):
    client_controller: types.ModuleType | None = None


class ClientAppEdificeAdapterTest(unittest.TestCase):
    controller: FakeController | None = None
    adapter: ProtocolAdapter | None = None

    @override
    def setUp(self) -> None:
        self.controller = FakeController()
        self.adapter = ProtocolAdapter(controller=self.controller, name="test-adapter")

    def test_client_property_creates_controller_when_missing(self) -> None:
        module_backup = sys.modules.get("client_app.network")
        controller_backup = sys.modules.get("client_app.network.client_controller")
        dummy_module = ClientControllerModule("client_app.network.client_controller")

        class DummyController:
            closed: bool

            def __init__(self) -> None:
                self.closed = False

            def close(self) -> None:
                self.closed = True

        dummy_module.ClientController = DummyController
        network_package = NetworkPackageModule("client_app.network")
        setattr(network_package, "client_controller", dummy_module)
        sys.modules["client_app.network"] = network_package
        sys.modules["client_app.network.client_controller"] = dummy_module

        try:
            adapter = ProtocolAdapter(controller=None, name="lazy-adapter")
            client = adapter.client

            self.assertIsInstance(client, DummyController)
            self.assertIs(client, adapter.client)
        finally:
            if controller_backup is None:
                _ = sys.modules.pop("client_app.network.client_controller", None)
            else:
                sys.modules["client_app.network.client_controller"] = controller_backup
            if module_backup is None:
                _ = sys.modules.pop("client_app.network", None)
            else:
                sys.modules["client_app.network"] = module_backup

    def test_login_normalizes_user_and_sessions(self) -> None:
        adapter = self.adapter
        assert adapter is not None
        result = adapter.login("alice", "pw1")

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "登录成功")
        self.assertIsNotNone(result.user)
        assert result.user is not None
        self.assertEqual(result.user.username, "alice")
        self.assertEqual(result.user.encoding_rule, ("base64",))
        self.assertEqual(
            [session.peer for session in result.sessions], ["bob", "carol"]
        )
        self.assertEqual(
            [session.is_online for session in result.sessions], [True, False]
        )

    def test_login_failure_reuses_existing_error_message_mapping(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        controller.login_response = {
            "ok": False,
            "code": "invalid_credentials",
            "message": "bad password",
            "data": {},
        }

        result = adapter.login("alice", "wrong")

        self.assertFalse(result.ok)
        self.assertEqual(result.code, "invalid_credentials")
        self.assertEqual(result.message, "账号或密码错误，请重新输入")
        self.assertIsNone(result.user)
        self.assertEqual(result.sessions, ())

    def test_list_sessions_normalizes_list_friends_as_ui_sessions(self) -> None:
        adapter = self.adapter
        assert adapter is not None
        result = adapter.list_sessions("alice")

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "好友列表已刷新")
        self.assertEqual(
            [session.title for session in result.sessions], ["bob", "carol"]
        )

    def test_pull_messages_marks_outgoing_messages_from_current_user(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        result = adapter.pull_messages("alice", "bob", since_id=3)

        self.assertTrue(result.ok)
        self.assertEqual(result.peer, "bob")
        self.assertEqual(
            [message.outgoing for message in result.messages], [True, False]
        )
        self.assertEqual(
            controller.sent_calls[-1],
            (
                "pull_messages",
                ("alice",),
                {"since_id": 3, "peer": "bob"},
            ),
        )

    def test_send_message_keeps_protocol_arguments_and_returns_status(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        result = adapter.send_message(
            "alice",
            "bob",
            "hello secure chat",
            ["base64"],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.message, "消息发送成功")
        self.assertEqual(
            controller.sent_calls[-1],
            ("send_message", ("alice", "bob", "hello secure chat", ["base64"]), {}),
        )

    def test_logout_failure_maps_network_error_message(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        controller.logout_response = {
            "ok": False,
            "code": "network_error",
            "message": "服务器连接失败: timeout",
            "data": {},
        }

        result = adapter.logout("alice")

        self.assertFalse(result.ok)
        self.assertEqual(result.message, "网络连接失败，请检查服务器状态后重试")

    def test_status_message_uses_backend_text_when_code_unknown(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        controller.logout_response = {
            "ok": False,
            "code": "missing_token",
            "message": "session expired",
            "data": {},
        }

        result = adapter.logout("alice")

        self.assertEqual(result.message, "session expired")

    def test_close_delegates_to_underlying_controller(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        adapter.close()

        self.assertTrue(controller.closed)

    def test_close_without_controller_is_noop(self) -> None:
        adapter = ProtocolAdapter(controller=None, name="safe-close")
        adapter.close()

        controller_state: object | None = getattr(adapter, "_controller", None)
        self.assertIsNone(controller_state)

    def test_login_accepts_string_session_payload(self) -> None:
        controller = self.controller
        adapter = self.adapter
        assert controller is not None
        assert adapter is not None
        data = cast(dict[str, object], controller.login_response.setdefault("data", {}))
        data["sessions"] = ["bob", "carol"]

        result = adapter.login("alice", "pw1")

        self.assertEqual(
            [session.title for session in result.sessions], ["bob", "carol"]
        )


if __name__ == "__main__":
    _ = unittest.main()
