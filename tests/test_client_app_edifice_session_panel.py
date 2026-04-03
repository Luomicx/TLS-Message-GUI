from __future__ import annotations

import unittest

from client_app_edifice.adapter import (
    AdapterStatus,
    ChatSession,
    ChatUser,
    MessagesResult,
)
from client_app_edifice.pages import (
    ChatShellController,
    build_session_panel_view_model,
)
from client_app_edifice.state import AppState, RequestStateKind


class FakeCleanupAdapter:
    def __init__(self) -> None:
        self.logout_calls: list[str] = []
        self.close_calls: int = 0

    def logout(self, username: str) -> AdapterStatus:
        self.logout_calls.append(username)
        return AdapterStatus(ok=True, code="ok", message="ok")

    def close(self) -> None:
        self.close_calls += 1

    def send_message(
        self,
        username: str,
        peer: str,
        content: str,
        encoding_rule: list[str] | None = None,
    ) -> AdapterStatus:
        _ = (username, peer, content, encoding_rule)
        return AdapterStatus(ok=True, code="ok", message="消息发送成功")

    def pull_messages(
        self, username: str, peer: str, *, since_id: int = 0
    ) -> MessagesResult:
        _ = (username, peer, since_id)
        return MessagesResult(
            ok=True,
            code="ok",
            message="消息加载成功",
            peer=peer,
            messages=(),
        )


class SessionPanelViewModelTest(unittest.TestCase):
    def test_rows_reflect_state_sessions_with_selection_flag(self) -> None:
        state = AppState()
        user = ChatUser(username="alice", is_online=True, encoding_rule=("base64",))
        state.login_succeeded(
            user=user,
            sessions=(
                ChatSession(peer="bob", title="Bob", is_online=True),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )
        state.select_session("carol")

        view_model = build_session_panel_view_model(state)

        self.assertEqual(view_model.session_count, 2)
        selected = [row for row in view_model.rows if row.is_selected]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].peer, "carol")

    def test_loading_while_no_sessions_reports_loading_state_message(self) -> None:
        state = AppState()
        state.request_state = state.request_state.__class__(
            kind=RequestStateKind.LOAD_MESSAGES,
            is_loading=True,
            peer="bob",
        )

        view_model = build_session_panel_view_model(state)

        self.assertTrue(view_model.is_loading)
        self.assertFalse(view_model.is_empty)
        self.assertEqual(
            view_model.loading_message, "正在加载所选会话；稍后会刷新消息区。"
        )

    def test_empty_without_loading_sets_empty_message(self) -> None:
        state = AppState()

        view_model = build_session_panel_view_model(state)

        self.assertTrue(view_model.is_empty)
        self.assertFalse(view_model.is_loading)
        self.assertEqual(
            view_model.empty_message,
            "当前尚无任何会话入口，后续任务会把好友与聊天记录填充在这里。",
        )


class ChatShellControllerSelectionTest(unittest.TestCase):
    def test_select_session_updates_state_and_notifies(self) -> None:
        state = AppState()
        state.login_succeeded(
            user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
            sessions=(
                ChatSession(peer="bob", title="Bob", is_online=True),
                ChatSession(peer="carol", title="Carol", is_online=False),
            ),
        )

        adapter = FakeCleanupAdapter()
        refresh_calls = 0

        def refresh() -> None:
            nonlocal refresh_calls
            refresh_calls += 1

        controller = ChatShellController(
            state=state, adapter=adapter, on_state_change=refresh
        )

        controller.select_session("bob")

        self.assertEqual(refresh_calls, 2)
        self.assertIsNotNone(state.current_session)
        current_session = state.current_session
        assert current_session is not None
        self.assertEqual(current_session.peer, "bob")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
