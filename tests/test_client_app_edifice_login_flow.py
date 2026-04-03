from __future__ import annotations

import unittest
from typing import override

from client_app_edifice.adapter import (
    AdapterStatus,
    ChatMessage,
    ChatSession,
    ChatUser,
    LoginResult,
    MessagesResult,
)
from client_app_edifice.pages import (
    ChatShellController,
    LoginFlowController,
    build_login_view_model,
)
from client_app_edifice.state import AppState, AuthState, ViewMode


class FakeLoginAdapter:
    def __init__(self) -> None:
        self.result: LoginResult = LoginResult(
            ok=True,
            code="ok",
            message="登录成功",
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(
                ChatSession(peer="bob", title="Bob", is_online=True),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )
        self.calls: list[tuple[str, str]] = []
        self.pull_calls: list[tuple[str, str, int]] = []
        self.messages_result: MessagesResult = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="bob",
            messages=(
                ChatMessage(
                    content="hello",
                    sender="bob",
                    created_at="2026-03-24 10:00:00",
                    outgoing=False,
                ),
            ),
        )

    def login(self, username: str, password: str) -> LoginResult:
        self.calls.append((username, password))
        return self.result

    def pull_messages(
        self, username: str, peer: str, *, since_id: int = 0
    ) -> MessagesResult:
        self.pull_calls.append((username, peer, since_id))
        return self.messages_result

    def logout(self, username: str) -> AdapterStatus:
        _ = username
        return AdapterStatus(ok=True, code="ok", message="注销成功")

    def close(self) -> None:
        return None

    def send_message(
        self,
        username: str,
        peer: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> AdapterStatus:
        _ = (username, peer, content, encoding_rule)
        return AdapterStatus(ok=True, code="ok", message="消息发送成功")


class ClientAppEdificeLoginFlowTest(unittest.TestCase):
    state: AppState | None = None
    adapter: FakeLoginAdapter | None = None
    refresh_calls: int = 0
    controller: LoginFlowController | None = None
    chat_shell_controller: ChatShellController | None = None

    @override
    def setUp(self) -> None:
        self.state = AppState()
        self.adapter = FakeLoginAdapter()
        self.refresh_calls = 0
        self.controller = LoginFlowController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=self._refresh,
        )
        self.chat_shell_controller = ChatShellController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=self._refresh,
        )

    def _refresh(self) -> None:
        self.refresh_calls += 1

    def test_successful_login_updates_state_and_switches_to_chat(self) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.chat_shell_controller is not None
        assert self.state is not None
        self.controller.submit_login("alice", "pw1")
        self.chat_shell_controller.load_initial_session()

        self.assertEqual(self.adapter.calls, [("alice", "pw1")])
        self.assertEqual(self.adapter.pull_calls, [("alice", "bob", 0)])
        self.assertEqual(self.state.active_view, ViewMode.CHAT)
        self.assertEqual(self.state.auth_state, AuthState.LOGGED_IN)
        self.assertTrue(self.state.is_authenticated)
        self.assertIsNotNone(self.state.current_user)
        assert self.state.current_user is not None
        self.assertEqual(self.state.current_user.username, "alice")
        self.assertEqual([item.peer for item in self.state.sessions], ["bob", "carol"])
        self.assertIsNotNone(self.state.current_session)
        assert self.state.current_session is not None
        self.assertEqual(self.state.current_session.peer, "bob")
        self.assertEqual(len(self.state.messages), 1)
        self.assertIsNone(self.state.error_message)
        self.assertGreaterEqual(self.refresh_calls, 4)

    def test_successful_login_with_no_sessions_keeps_safe_empty_chat_state(
        self,
    ) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.chat_shell_controller is not None
        assert self.state is not None
        self.adapter.result = LoginResult(
            ok=True,
            code="ok",
            message="登录成功",
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(),
        )

        self.controller.submit_login("alice", "pw1")
        self.chat_shell_controller.load_initial_session()

        self.assertEqual(self.state.active_view, ViewMode.CHAT)
        self.assertEqual(self.state.auth_state, AuthState.LOGGED_IN)
        self.assertEqual(self.adapter.pull_calls, [])
        self.assertIsNone(self.state.current_session)
        self.assertEqual(self.state.messages, [])
        self.assertIsNone(self.state.error_message)

    def test_successful_login_skips_blank_session_peer_and_loads_first_valid_session(
        self,
    ) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.chat_shell_controller is not None
        assert self.state is not None
        self.adapter.result = LoginResult(
            ok=True,
            code="ok",
            message="登录成功",
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(
                ChatSession(peer="", title=""),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )
        self.adapter.messages_result = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="carol",
            messages=(
                ChatMessage(
                    content="hey",
                    sender="carol",
                    created_at="",
                    outgoing=False,
                ),
            ),
        )

        self.controller.submit_login("alice", "pw1")
        self.chat_shell_controller.load_initial_session()

        self.assertEqual(self.adapter.pull_calls, [("alice", "carol", 0)])
        self.assertIsNotNone(self.state.current_session)
        assert self.state.current_session is not None
        self.assertEqual(self.state.current_session.peer, "carol")
        self.assertEqual(len(self.state.messages), 1)

    def test_initial_session_load_failure_keeps_chat_context_stable(self) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.chat_shell_controller is not None
        assert self.state is not None
        self.adapter.messages_result = MessagesResult(
            ok=False,
            code="network_error",
            message="网络连接失败，请检查服务器状态后重试",
            peer="bob",
            messages=(),
        )

        self.controller.submit_login("alice", "pw1")
        self.chat_shell_controller.load_initial_session()

        self.assertEqual(self.state.active_view, ViewMode.CHAT)
        self.assertEqual(self.state.auth_state, AuthState.LOGGED_IN)
        self.assertIsNotNone(self.state.current_session)
        assert self.state.current_session is not None
        self.assertEqual(self.state.current_session.peer, "bob")
        self.assertEqual(self.state.messages, [])
        self.assertEqual(
            self.state.error_message, "网络连接失败，请检查服务器状态后重试"
        )

    def test_failed_login_exposes_inline_error_and_allows_retry(self) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.state is not None
        self.adapter.result = LoginResult(
            ok=False,
            code="invalid_credentials",
            message="账号或密码错误，请重新输入",
            user=None,
            sessions=(),
        )

        self.controller.submit_login("alice", "wrong")

        self.assertEqual(self.state.active_view, ViewMode.LOGIN)
        self.assertEqual(self.state.auth_state, AuthState.LOGGED_OUT)
        self.assertEqual(self.state.error_message, "账号或密码错误，请重新输入")
        failure_view = build_login_view_model(
            self.state,
            username="alice",
            password="wrong",
        )
        self.assertFalse(failure_view.is_loading)
        self.assertTrue(failure_view.can_submit)
        self.assertEqual(failure_view.status_title, "登录失败")
        self.assertIn("账号或密码错误", failure_view.status_message)

        self.adapter.result = LoginResult(
            ok=True,
            code="ok",
            message="登录成功",
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
        )
        self.controller.submit_login("alice", "pw1")
        self.assertEqual(self.state.active_view, ViewMode.CHAT)
        self.assertIsNone(self.state.error_message)

    def test_blank_username_short_circuits_before_adapter_call(self) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.state is not None
        self.controller.submit_login("   ", "pw1")

        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.state.error_message, "请输入用户名")
        self.assertEqual(self.state.active_view, ViewMode.LOGIN)

    def test_blank_password_short_circuits_before_adapter_call(self) -> None:
        assert self.adapter is not None
        assert self.controller is not None
        assert self.state is not None
        self.controller.submit_login("alice", "")

        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(self.state.error_message, "请输入密码")
        self.assertEqual(self.state.active_view, ViewMode.LOGIN)

    def test_login_view_model_disables_primary_action_only_while_loading(self) -> None:
        assert self.state is not None
        idle_view = build_login_view_model(
            self.state,
            username="alice",
            password="pw1",
        )
        self.assertFalse(idle_view.is_loading)
        self.assertTrue(idle_view.can_submit)
        self.assertEqual(idle_view.submit_label, "进入聊天")

        self.state.start_login()
        loading_view = build_login_view_model(
            self.state,
            username="alice",
            password="pw1",
        )
        self.assertTrue(loading_view.is_loading)
        self.assertFalse(loading_view.can_submit)
        self.assertEqual(loading_view.submit_label, "正在登录...")
        self.assertEqual(loading_view.status_title, "正在登录")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
