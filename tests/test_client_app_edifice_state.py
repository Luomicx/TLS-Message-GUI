from __future__ import annotations

import unittest

from client_app_edifice.adapter import ChatMessage, ChatSession, ChatUser
from client_app_edifice.state import AppState, AuthState, RequestStateKind, ViewMode


def make_user() -> ChatUser:
    return ChatUser(username="alice", is_online=True, encoding_rule=("base64",))


def make_sessions() -> list[ChatSession]:
    return [
        ChatSession(peer="bob", title="Bob", is_online=True),
        ChatSession(peer="carol", title="Carol", is_online=False),
    ]


def make_messages() -> list[ChatMessage]:
    return [
        ChatMessage(
            content="hello",
            sender="alice",
            created_at="2026-03-24 10:00:00",
            outgoing=True,
        ),
        ChatMessage(
            content="hi",
            sender="bob",
            created_at="2026-03-24 10:01:00",
            outgoing=False,
        ),
    ]


class ClientAppEdificeStateTest(unittest.TestCase):
    def test_initial_state_matches_logged_out_mvp_defaults(self) -> None:
        state = AppState()

        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertFalse(state.is_authenticated)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

    def test_login_start_then_success_updates_authenticated_chat_state(self) -> None:
        state = AppState()

        state.start_login()
        self.assertEqual(state.auth_state, AuthState.LOGGING_IN)
        self.assertEqual(state.request_state.kind, RequestStateKind.LOGIN)
        self.assertTrue(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

        state.login_succeeded(user=make_user(), sessions=make_sessions())

        self.assertEqual(state.active_view, ViewMode.CHAT)
        self.assertEqual(state.auth_state, AuthState.LOGGED_IN)
        self.assertTrue(state.is_authenticated)
        self.assertEqual(state.current_user, make_user())
        self.assertIsNone(state.current_session)
        self.assertEqual([session.peer for session in state.sessions], ["bob", "carol"])
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

    def test_login_failure_clears_transient_state_and_exposes_error(self) -> None:
        state = AppState()
        state.start_login()

        state.login_failed("账号或密码错误，请重新输入")

        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertFalse(state.is_authenticated)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertEqual(state.error_message, "账号或密码错误，请重新输入")

    def test_select_session_clears_previous_error_and_targets_known_session(
        self,
    ) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.error_message = "旧错误"

        state.select_session("bob")

        self.assertIsNotNone(state.current_session)
        assert state.current_session is not None
        self.assertEqual(state.current_session.peer, "bob")
        self.assertEqual(state.current_session.title, "Bob")
        self.assertEqual(state.messages, [])
        self.assertIsNone(state.error_message)

    def test_message_loading_lifecycle_replaces_current_message_list(self) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())

        state.start_loading_messages("bob")

        self.assertEqual(state.request_state.kind, RequestStateKind.LOAD_MESSAGES)
        self.assertTrue(state.request_state.is_loading)
        self.assertEqual(state.request_state.peer, "bob")
        assert state.current_session is not None
        self.assertEqual(state.current_session.peer, "bob")

        messages = make_messages()
        state.finish_loading_messages(peer="bob", messages=messages)

        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertEqual(state.messages, messages)
        self.assertIsNone(state.error_message)

    def test_finish_loading_messages_ignores_stale_peer(self) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())

        state.start_loading_messages("bob")
        state.select_session("carol")

        state.finish_loading_messages(peer="bob", messages=make_messages())

        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertIsNotNone(state.current_session)
        assert state.current_session is not None
        self.assertEqual(state.current_session.peer, "carol")
        self.assertEqual(state.messages, [])

    def test_message_loading_failure_keeps_selected_session_and_sets_error(
        self,
    ) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.start_loading_messages("bob")

        state.fail_loading_messages("消息加载失败")

        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertEqual(state.error_message, "消息加载失败")
        assert state.current_session is not None
        self.assertEqual(state.current_session.peer, "bob")

    def test_fail_loading_messages_ignores_peer_mismatch(self) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())

        state.start_loading_messages("bob")
        state.select_session("carol")

        state.fail_loading_messages("无法加载", peer="bob")

        self.assertIsNone(state.error_message)
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertIsNotNone(state.current_session)
        assert state.current_session is not None
        self.assertEqual(state.current_session.peer, "carol")

    def test_send_message_failure_preserves_message_list_and_allows_recovery(
        self,
    ) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        messages = make_messages()
        state.select_session("bob")
        state.finish_loading_messages(peer="bob", messages=messages)

        state.start_sending_message()
        self.assertEqual(state.request_state.kind, RequestStateKind.SEND_MESSAGE)
        self.assertTrue(state.request_state.is_loading)
        self.assertEqual(state.request_state.peer, "bob")

        state.fail_sending_message("消息发送失败")

        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertEqual(state.messages, messages)
        self.assertEqual(state.error_message, "消息发送失败")

        state.recover_error()

        self.assertIsNone(state.error_message)
        self.assertEqual(state.messages, messages)

    def test_send_message_start_clears_previous_error_before_request_feedback(
        self,
    ) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.select_session("bob")
        state.error_message = "旧发送错误"

        state.start_sending_message()

        self.assertEqual(state.request_state.kind, RequestStateKind.SEND_MESSAGE)
        self.assertTrue(state.request_state.is_loading)
        self.assertEqual(state.request_state.peer, "bob")
        self.assertIsNone(state.error_message)

    def test_send_message_success_clears_pending_state_and_accepts_refreshed_messages(
        self,
    ) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.select_session("bob")
        state.finish_loading_messages(peer="bob", messages=make_messages())

        updated_messages = make_messages() + [
            ChatMessage(
                content="see you",
                sender="alice",
                created_at="2026-03-24 10:02:00",
                outgoing=True,
            )
        ]
        state.start_sending_message()
        state.finish_sending_message(updated_messages)

        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertEqual(state.messages, updated_messages)
        self.assertIsNone(state.error_message)

    def test_finish_sending_message_with_none_preserves_messages(self) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.select_session("bob")
        state.finish_loading_messages(peer="bob", messages=make_messages())

        state.start_sending_message()
        state.finish_sending_message()

        self.assertEqual(state.messages, make_messages())

    def test_logout_reset_returns_state_to_initial_defaults(self) -> None:
        state = AppState()
        state.login_succeeded(user=make_user(), sessions=make_sessions())
        state.select_session("bob")
        state.finish_loading_messages(peer="bob", messages=make_messages())
        state.start_sending_message()
        state.fail_sending_message("消息发送失败")

        state.logout_reset()

        self.assertEqual(state.active_view, ViewMode.LOGIN)
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertFalse(state.is_authenticated)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
