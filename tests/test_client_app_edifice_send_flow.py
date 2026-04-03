from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import override

from client_app_edifice.adapter import (
    AdapterStatus,
    ChatMessage,
    ChatSession,
    ChatUser,
    MessagesResult,
)
from client_app_edifice.pages import ChatShellController
from client_app_edifice.state import AppState, RequestStateKind


class FakeSendFlowAdapter:
    def __init__(self) -> None:
        self.send_calls: list[tuple[str, str, str, list[str] | None]] = []
        self.pull_calls: list[tuple[str, str, int]] = []
        self.on_first_pull: Callable[[], None] | None = None
        self.send_result: AdapterStatus = AdapterStatus(
            ok=True, code="ok", message="消息发送完成"
        )
        self.pull_result: MessagesResult = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="bob",
            messages=(),
        )

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
        self.send_calls.append((username, peer, content, encoding_rule))
        return self.send_result

    def pull_messages(
        self, username: str, peer: str, *, since_id: int = 0
    ) -> MessagesResult:
        self.pull_calls.append((username, peer, since_id))
        if peer == "bob" and self.pull_calls == [(username, peer, since_id)]:
            self._switch_to_carol_during_refresh()
        return self.pull_result

    def _switch_to_carol_during_refresh(self) -> None:
        callback = self.on_first_pull
        if callback is not None:
            callback()


class ChatShellControllerSendFlowTest(unittest.TestCase):
    state: AppState | None = None
    adapter: FakeSendFlowAdapter | None = None
    refresh_calls: int = 0
    controller: ChatShellController | None = None

    @override
    def setUp(self) -> None:
        self.state = AppState()
        self.state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(
                ChatSession(peer="bob", title="Bob", is_online=True),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )
        self.state.select_session("bob")
        self.adapter = FakeSendFlowAdapter()
        self.refresh_calls = 0

        def refresh() -> None:
            self.refresh_calls += 1

        self.controller = ChatShellController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=refresh,
        )

    def test_submit_message_refreshes_active_conversation_after_success(self) -> None:
        adapter = self.adapter
        controller = self.controller
        state = self.state
        assert adapter is not None
        assert controller is not None
        assert state is not None

        adapter.pull_result = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="bob",
            messages=(
                ChatMessage(
                    content="hello secure chat",
                    sender="alice",
                    created_at="2026-03-24 10:00:00",
                    outgoing=True,
                ),
            ),
        )

        result = controller.submit_message(" hello secure chat ")

        self.assertTrue(result)
        self.assertEqual(
            adapter.send_calls,
            [("alice", "bob", "hello secure chat", ["base64"])],
        )
        self.assertEqual(adapter.pull_calls, [("alice", "bob", 0)])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertIsNone(state.error_message)
        self.assertEqual(len(state.messages), 1)
        self.assertEqual(state.messages[0].content, "hello secure chat")
        self.assertGreaterEqual(self.refresh_calls, 3)

    def test_submit_message_failure_keeps_state_recoverable_without_refresh(
        self,
    ) -> None:
        adapter = self.adapter
        controller = self.controller
        state = self.state
        assert adapter is not None
        assert controller is not None
        assert state is not None

        adapter.send_result = AdapterStatus(
            ok=False,
            code="network_error",
            message="网络连接失败，请检查服务器状态后重试",
        )
        existing = ChatMessage(
            content="older message",
            sender="bob",
            created_at="2026-03-24 09:59:00",
            outgoing=False,
        )
        state.messages = [existing]

        result = controller.submit_message("hello")

        self.assertFalse(result)
        self.assertEqual(adapter.pull_calls, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertEqual(state.error_message, "网络连接失败，请检查服务器状态后重试")
        self.assertEqual(state.messages, [existing])

    def test_refresh_result_does_not_pollute_new_session_after_switch(self) -> None:
        adapter = self.adapter
        controller = self.controller
        state = self.state
        assert adapter is not None
        assert controller is not None
        assert state is not None

        adapter.pull_result = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="bob",
            messages=(
                ChatMessage(
                    content="stale from bob",
                    sender="alice",
                    created_at="2026-03-24 10:01:00",
                    outgoing=True,
                ),
            ),
        )
        state.messages = [
            ChatMessage(
                content="carol active message",
                sender="carol",
                created_at="2026-03-24 10:00:30",
                outgoing=False,
            )
        ]

        def switch_session() -> None:
            state.select_session("carol")

        adapter.on_first_pull = switch_session

        result = controller.submit_message("hello bob")

        self.assertTrue(result)
        self.assertIsNotNone(state.current_session)
        current_session = state.current_session
        assert current_session is not None
        self.assertEqual(current_session.peer, "carol")
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertIsNone(state.error_message)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
