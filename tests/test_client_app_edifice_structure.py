from __future__ import annotations

import unittest
from typing import override

from client_app_edifice.adapter import (
    AdapterStatus,
    ChatMessage,
    ChatSession,
    ChatUser,
    MessagesResult,
    ProtocolAdapter,
)
from client_app_edifice.components import PasswordInput
from client_app_edifice.pages import (
    ChatShellController,
    build_chat_shell_view_model,
    describe_chat_shell,
    describe_login_page,
)
from client_app_edifice.state import (
    AppState,
    AuthState,
    RequestStateKind,
    ViewMode,
)


class FakeCleanupAdapter:
    def __init__(self) -> None:
        self.logout_calls: list[str] = []
        self.close_calls: int = 0

    def logout(self, username: str) -> AdapterStatus:
        self.logout_calls.append(username)
        return AdapterStatus(ok=True, code="ok", message="注销成功")

    def close(self) -> None:
        self.close_calls += 1

    def pull_messages(
        self, username: str, peer: str, *, since_id: int = 0
    ) -> MessagesResult:
        _ = (username, peer, since_id)
        return MessagesResult(
            ok=True, code="ok", message="消息加载成功", peer=peer, messages=()
        )

    def send_message(
        self,
        username: str,
        peer: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> AdapterStatus:
        _ = (username, peer, content, encoding_rule)
        return AdapterStatus(ok=True, code="ok", message="消息发送成功")


class FailingCleanupAdapter(FakeCleanupAdapter):
    @override
    def logout(self, username: str) -> AdapterStatus:
        self.logout_calls.append(username)
        raise RuntimeError("logout failed")


class ClientAppEdificeStructureTest(unittest.TestCase):
    def test_adapter_handshake_is_readable(self) -> None:
        adapter = ProtocolAdapter(name="edifice-test")
        self.assertEqual(adapter.handshake(), "edifice-test ready")

    def test_password_input_extends_text_input_for_masked_entry(self) -> None:
        field = PasswordInput(text="secret")
        self.assertEqual(field.props["text"], "secret")

    def test_login_and_chat_descriptions_use_state(self) -> None:
        state = AppState()
        self.assertIn(str(ViewMode.LOGIN.value), describe_login_page(state))
        self.assertIn(str(ViewMode.LOGIN.value), describe_chat_shell(state))
        state.switch_to_chat()
        self.assertEqual(state.active_view, ViewMode.CHAT)

    def test_chat_shell_view_model_uses_stable_shell_regions(self) -> None:
        state = AppState()
        state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(
                ChatSession(peer="bob", title="Bob", is_online=True),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )
        view_model = build_chat_shell_view_model(state)

        self.assertEqual(view_model.shell_title, "聊天主壳层")
        self.assertEqual(view_model.sidebar_title, "alice")
        self.assertEqual(view_model.header_title, "未选择会话")
        self.assertEqual(view_model.session_titles, ("Bob", "Carol"))
        self.assertEqual(view_model.session_count, 2)
        self.assertEqual(view_model.logout_label, "注销并返回登录")
        self.assertIn("聊天记录", view_model.transcript_title)
        self.assertIn("消息输入区", view_model.composer_title)

    def test_chat_shell_controller_logout_reuses_shared_cleanup_path(self) -> None:
        state = AppState()
        state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
        )
        state.select_session("bob")
        adapter = FakeCleanupAdapter()
        refresh_calls = 0

        def refresh() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        controller = ChatShellController(
            state=state,
            adapter=adapter,
            on_state_change=refresh,
        )

        controller.request_logout()

        self.assertEqual(adapter.logout_calls, ["alice"])
        self.assertEqual(adapter.close_calls, 1)
        self.assertEqual(refresh_calls, 1)
        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])

    def test_chat_shell_controller_window_close_uses_same_cleanup_without_logout_call(
        self,
    ) -> None:
        state = AppState()
        adapter = FakeCleanupAdapter()
        refresh_calls = 0

        def refresh() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        controller = ChatShellController(
            state=state,
            adapter=adapter,
            on_state_change=refresh,
        )

        controller.handle_window_close()

        self.assertEqual(adapter.logout_calls, [])
        self.assertEqual(adapter.close_calls, 1)
        self.assertEqual(refresh_calls, 1)
        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)

    def test_cleanup_handles_logout_failure_and_resets_state(self) -> None:
        state = AppState()
        state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
        )
        state.select_session("bob")
        state.start_sending_message()
        state.messages = [
            ChatMessage(
                content="pending",
                sender="bob",
                created_at="2026-03-24 10:00:00",
                outgoing=False,
            )
        ]
        adapter = FailingCleanupAdapter()
        refresh_calls = 0

        def refresh() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        controller = ChatShellController(
            state=state,
            adapter=adapter,
            on_state_change=refresh,
        )

        controller.request_logout()

        self.assertEqual(adapter.logout_calls, ["alice"])
        self.assertEqual(adapter.close_calls, 1)
        self.assertEqual(refresh_calls, 1)
        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertFalse(state.request_state.is_loading)
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])

    def test_window_close_clears_busy_request_state_even_without_logout(self) -> None:
        state = AppState()
        state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
        )
        state.start_loading_messages("bob")
        adapter = FakeCleanupAdapter()
        refresh_calls = 0

        def refresh() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        controller = ChatShellController(
            state=state,
            adapter=adapter,
            on_state_change=refresh,
        )

        controller.handle_window_close()

        self.assertEqual(adapter.logout_calls, ["alice"])
        self.assertEqual(adapter.close_calls, 1)
        self.assertEqual(refresh_calls, 1)
        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertFalse(state.request_state.is_loading)
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
