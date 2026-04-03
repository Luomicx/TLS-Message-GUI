from __future__ import annotations

import unittest
from typing import override

from client_app_edifice.adapter import (
    AdapterStatus,
    ChatSession,
    ChatUser,
    MessagesResult,
)
from client_app_edifice.pages import (
    ChatShellController,
    build_chat_shell_view_model,
    build_composer_view_model,
)
from client_app_edifice.state import AppState, RequestStateKind


def make_state() -> AppState:
    state = AppState()
    state.login_succeeded(
        user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
        sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
    )
    return state


class FakeChatAdapter:
    def __init__(self) -> None:
        self.send_result: AdapterStatus = AdapterStatus(
            ok=True,
            code="ok",
            message="消息发送成功",
        )
        self.pull_result: MessagesResult = MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer="bob",
            messages=(),
        )
        self.send_calls: list[tuple[str, str, str, list[str] | None]] = []
        self.pull_calls: list[tuple[str, str, int]] = []
        self.logout_calls: list[str] = []
        self.closed: bool = False

    def send_message(
        self,
        username: str,
        peer: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> AdapterStatus:
        self.send_calls.append((username, peer, content, encoding_rule))
        return self.send_result

    def logout(self, username: str) -> AdapterStatus:
        self.logout_calls.append(username)
        return AdapterStatus(ok=True, code="ok", message="已注销")

    def pull_messages(
        self, username: str, peer: str, *, since_id: int = 0
    ) -> MessagesResult:
        self.pull_calls.append((username, peer, since_id))
        return self.pull_result

    def close(self) -> None:
        self.closed = True


class ClientAppEdificeComposerTest(unittest.TestCase):
    state: AppState | None = None
    adapter: FakeChatAdapter | None = None
    refresh_calls: int = 0
    controller: ChatShellController | None = None

    @override
    def setUp(self) -> None:
        self.state = make_state()
        self.adapter = FakeChatAdapter()
        self.refresh_calls = 0
        self.controller = ChatShellController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=self._refresh,
        )

    def _refresh(self) -> None:
        self.refresh_calls += 1

    def test_send_success_trims_multiline_draft_and_restores_idle_state(self) -> None:
        assert self.state is not None
        assert self.adapter is not None
        assert self.controller is not None
        self.state.select_session("bob")

        ok = self.controller.submit_message("  hello secure chat\nsecond line  ")

        self.assertTrue(ok)
        self.assertEqual(
            self.adapter.send_calls,
            [("alice", "bob", "hello secure chat\nsecond line", ["base64"])],
        )
        self.assertEqual(self.adapter.pull_calls, [("alice", "bob", 0)])
        self.assertEqual(self.state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(self.state.request_state.is_loading)
        self.assertIsNone(self.state.error_message)
        self.assertGreaterEqual(self.refresh_calls, 2)

    def test_blank_draft_is_blocked_before_adapter_call(self) -> None:
        assert self.state is not None
        assert self.adapter is not None
        assert self.controller is not None
        self.state.select_session("bob")

        ok = self.controller.submit_message("  \n \t  ")

        self.assertFalse(ok)
        self.assertEqual(self.adapter.send_calls, [])
        self.assertEqual(self.state.error_message, "请输入消息后再发送")
        self.assertEqual(self.state.request_state.kind, RequestStateKind.IDLE)

    def test_missing_session_blocks_send_before_adapter_call(self) -> None:
        assert self.state is not None
        assert self.adapter is not None
        assert self.controller is not None

        ok = self.controller.submit_message("hello")

        self.assertFalse(ok)
        self.assertEqual(self.adapter.send_calls, [])
        self.assertEqual(self.state.error_message, "请先选择一个会话")
        self.assertEqual(self.state.request_state.kind, RequestStateKind.IDLE)

    def test_failed_send_keeps_recoverable_state_and_feedback(self) -> None:
        assert self.state is not None
        assert self.adapter is not None
        assert self.controller is not None
        self.state.select_session("bob")
        self.adapter.send_result = AdapterStatus(
            ok=False,
            code="network_error",
            message="网络连接失败，请检查服务器状态后重试",
        )

        ok = self.controller.submit_message("hello")

        self.assertFalse(ok)
        self.assertEqual(len(self.adapter.send_calls), 1)
        self.assertEqual(
            self.state.error_message,
            "网络连接失败，请检查服务器状态后重试",
        )
        self.assertEqual(self.state.request_state.kind, RequestStateKind.IDLE)

    def test_composer_view_model_disables_send_and_shows_inline_feedback_while_sending(
        self,
    ) -> None:
        assert self.state is not None
        self.state.select_session("bob")
        self.state.start_sending_message()

        composer = build_composer_view_model(self.state, draft="hello")
        shell = build_chat_shell_view_model(self.state)

        self.assertTrue(composer.is_sending)
        self.assertFalse(composer.can_send)
        self.assertEqual(composer.send_label, "正在发送...")
        self.assertIn("请勿重复点击发送", composer.feedback_message)
        self.assertIn("正在发送消息", shell.request_feedback)

    def test_composer_view_model_requires_session_and_non_blank_draft(self) -> None:
        assert self.state is not None

        no_session = build_composer_view_model(self.state, draft="hello")
        self.assertFalse(no_session.can_send)
        self.assertIn("请先在左侧选择一个会话", no_session.feedback_message)

        self.state.select_session("bob")
        blank_draft = build_composer_view_model(self.state, draft="   ")
        self.assertFalse(blank_draft.can_send)
        self.assertIn("请输入消息内容", blank_draft.feedback_message)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
