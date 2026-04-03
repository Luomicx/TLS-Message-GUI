from __future__ import annotations

import unittest

from client_app_edifice.adapter import ChatMessage, ChatSession, ChatUser
from client_app_edifice.pages import (
    build_chat_shell_view_model,
    build_transcript_message_view_model,
    build_transcript_view_model,
)
from client_app_edifice.state import AppState, RequestStateKind


def make_state_with_session() -> AppState:
    state = AppState()
    state.login_succeeded(
        user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
        sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
    )
    state.select_session("bob")
    return state


class ClientAppEdificeTranscriptTest(unittest.TestCase):
    def test_chat_shell_view_model_describes_transcript_as_normalized_state_reader(
        self,
    ) -> None:
        view_model = build_chat_shell_view_model(AppState())

        self.assertEqual(view_model.transcript_title, "聊天记录")
        self.assertIn("归一化消息状态", view_model.transcript_message)

    def test_transcript_message_mapping_keeps_direction_sender_time_and_multiline_body(
        self,
    ) -> None:
        outgoing = build_transcript_message_view_model(
            ChatMessage(
                content="第一行\r\n第二行",
                sender="alice",
                created_at="2026-03-24 10:00:00",
                outgoing=True,
            ),
            fallback_sender="Bob",
        )
        incoming = build_transcript_message_view_model(
            ChatMessage(
                content="hello back",
                sender="bob",
                created_at="2026-03-24 10:01:00",
                outgoing=False,
            ),
            fallback_sender="Bob",
        )

        self.assertTrue(outgoing.is_outgoing)
        self.assertEqual(outgoing.sender_text, "我")
        self.assertEqual(outgoing.direction_text, "我发出的消息")
        self.assertEqual(outgoing.time_text, "2026-03-24 10:00:00")
        self.assertEqual(outgoing.body_text, "第一行\n第二行")

        self.assertFalse(incoming.is_outgoing)
        self.assertEqual(incoming.sender_text, "bob")
        self.assertEqual(incoming.direction_text, "收到的消息")
        self.assertEqual(incoming.time_text, "2026-03-24 10:01:00")
        self.assertEqual(incoming.body_text, "hello back")

    def test_transcript_view_model_uses_stable_placeholder_when_no_session_selected(
        self,
    ) -> None:
        transcript = build_transcript_view_model(AppState())

        self.assertTrue(transcript.is_empty)
        self.assertEqual(transcript.messages, ())
        self.assertIn("请选择左侧会话", transcript.empty_message)

    def test_transcript_view_model_uses_empty_history_placeholder_for_selected_session(
        self,
    ) -> None:
        state = make_state_with_session()

        transcript = build_transcript_view_model(state)

        self.assertTrue(transcript.is_empty)
        self.assertEqual(transcript.messages, ())
        self.assertIn("Bob", transcript.subtitle)
        self.assertIn("暂无历史消息", transcript.empty_message)

    def test_transcript_view_model_exposes_mapped_messages_for_selected_session(
        self,
    ) -> None:
        state = make_state_with_session()
        state.finish_loading_messages(
            peer="bob",
            messages=[
                ChatMessage(
                    content="hi bob",
                    sender="alice",
                    created_at="2026-03-24 10:00:00",
                    outgoing=True,
                ),
                ChatMessage(
                    content="hi alice\nsee you",
                    sender="bob",
                    created_at="2026-03-24 10:01:00",
                    outgoing=False,
                ),
            ],
        )

        transcript = build_transcript_view_model(state)

        self.assertFalse(transcript.is_empty)
        self.assertEqual(len(transcript.messages), 2)
        self.assertEqual(transcript.messages[0].sender_text, "我")
        self.assertEqual(transcript.messages[1].sender_text, "bob")
        self.assertEqual(transcript.messages[1].body_text, "hi alice\nsee you")
        self.assertIn("共 2 条消息", transcript.subtitle)

    def test_transcript_view_model_shows_loading_placeholder_during_message_fetch(
        self,
    ) -> None:
        state = make_state_with_session()
        state.request_state.kind = RequestStateKind.LOAD_MESSAGES
        state.request_state.is_loading = True
        state.request_state.peer = "bob"

        transcript = build_transcript_view_model(state)

        self.assertTrue(transcript.is_empty)
        self.assertIn("正在加载与 Bob 的聊天记录", transcript.empty_message)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
