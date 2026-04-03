from __future__ import annotations

import os
import unittest

from client_app_edifice.adapter import ChatMessage, ChatSession, ChatUser
from client_app_edifice.app import resolve_window_open_size
from client_app_edifice.pages import (
    build_chat_shell_view_model,
    build_composer_view_model,
    build_transcript_view_model,
)
from client_app_edifice.state import AppState
from client_app_edifice.visual_foundation import (
    MVP_LAYOUT_FOUNDATION,
    build_chat_shell_layout_styles,
    build_login_page_layout_styles,
)


def make_logged_in_state() -> AppState:
    state = AppState()
    state.login_succeeded(
        user=ChatUser(username="alice", is_online=True, encoding_rule=("base64",)),
        sessions=(ChatSession(peer="bob", title="Bob", is_online=True),),
    )
    state.select_session("bob")
    return state


def clear_env_var(name: str) -> None:
    _ = os.environ.pop(name, None)


class ClientAppEdificeLayoutRegressionTest(unittest.TestCase):
    def test_login_layout_styles_lock_minimum_window_and_auth_stack_regions(
        self,
    ) -> None:
        login_shell = MVP_LAYOUT_FOUNDATION.login_shell
        styles = build_login_page_layout_styles()

        self.assertEqual(styles["root"]["min-width"], login_shell.min_window.width)
        self.assertEqual(styles["root"]["min-height"], login_shell.min_window.height)
        self.assertEqual(styles["root"]["column-gap"], login_shell.column_gap)
        self.assertEqual(
            styles["auth_panel"]["min-width"],
            login_shell.auth_column.min_width,
        )
        self.assertEqual(
            styles["auth_panel"]["width"],
            login_shell.auth_column.preferred_width,
        )
        self.assertEqual(
            styles["status_panel"]["min-height"],
            next(
                region.min_height
                for region in login_shell.auth_stack
                if region.key == login_shell.status_region_key
            ),
        )
        self.assertEqual(
            styles["actions_panel"]["min-height"],
            next(
                region.min_height
                for region in login_shell.auth_stack
                if region.key == login_shell.primary_action_region_key
            ),
        )

    def test_chat_layout_styles_protect_sidebar_transcript_and_composer_regions(
        self,
    ) -> None:
        chat_shell = MVP_LAYOUT_FOUNDATION.chat_shell
        styles = build_chat_shell_layout_styles()

        self.assertEqual(styles["root"]["min-width"], chat_shell.min_window.width)
        self.assertEqual(styles["root"]["min-height"], chat_shell.min_window.height)
        self.assertEqual(
            styles["sidebar_panel"]["min-width"],
            chat_shell.sidebar_column.min_width,
        )
        self.assertEqual(
            styles["transcript_shell"]["min-width"],
            chat_shell.transcript_column_min_width,
        )
        self.assertEqual(
            styles["message_panel"]["min-height"],
            next(
                region.min_height
                for region in chat_shell.content_stack
                if region.key == "message_region"
            ),
        )
        self.assertEqual(
            styles["composer_panel"]["min-height"],
            next(
                region.min_height
                for region in chat_shell.content_stack
                if region.key == "composer_region"
            ),
        )
        self.assertEqual(styles["composer_feedback_column"]["min-width"], 320)
        self.assertEqual(styles["composer_send_button"]["min-width"], 132)

        for section in (
            "message_panel",
            "composer_panel",
            "transcript_content",
            "transcript_bubble_base",
            "composer_feedback_column",
        ):
            for key, value in styles[section].items():
                if key.endswith("width") and isinstance(value, str):
                    self.assertNotIn(
                        "%",
                        value,
                        msg=f"{section}.{key} should not use percentage width in Edifice/Qt layouts",
                    )

    def test_transcript_view_model_keeps_long_multiline_messages_readable(self) -> None:
        state = make_logged_in_state()
        long_line = "这是一段用于回归测试的长消息" * 12
        state.finish_loading_messages(
            peer="bob",
            messages=[
                ChatMessage(
                    content=f"{long_line}\n第二段仍应保留换行\n{long_line}",
                    sender="bob",
                    created_at="2026-03-24 10:00:00",
                    outgoing=False,
                )
            ],
        )

        transcript = build_transcript_view_model(state)

        self.assertFalse(transcript.is_empty)
        self.assertEqual(len(transcript.messages), 1)
        self.assertIn("\n第二段仍应保留换行\n", transcript.messages[0].body_text)
        self.assertGreater(len(transcript.messages[0].body_text), len(long_line))

    def test_empty_chat_and_composer_view_models_keep_readable_guidance_at_minimum_state(
        self,
    ) -> None:
        shell = build_chat_shell_view_model(AppState())
        transcript = build_transcript_view_model(AppState())
        composer = build_composer_view_model(AppState(), draft="")

        self.assertIn("未选择会话", shell.header_title)
        self.assertIn("请选择左侧会话", transcript.empty_message)
        self.assertIn("请先在左侧选择一个会话", composer.feedback_message)
        self.assertFalse(composer.can_send)

    def test_runtime_open_size_can_be_overridden_for_constrained_smoke(self) -> None:
        self.addCleanup(clear_env_var, "CLIENT_APP_EDIFICE_SMOKE_WIDTH")
        self.addCleanup(clear_env_var, "CLIENT_APP_EDIFICE_SMOKE_HEIGHT")

        os.environ["CLIENT_APP_EDIFICE_SMOKE_WIDTH"] = str(
            MVP_LAYOUT_FOUNDATION.chat_shell.min_window.width
        )
        os.environ["CLIENT_APP_EDIFICE_SMOKE_HEIGHT"] = str(
            MVP_LAYOUT_FOUNDATION.chat_shell.min_window.height
        )

        self.assertEqual(
            resolve_window_open_size(),
            (
                MVP_LAYOUT_FOUNDATION.chat_shell.min_window.width,
                MVP_LAYOUT_FOUNDATION.chat_shell.min_window.height,
            ),
        )


if __name__ == "__main__":
    raise SystemExit(unittest.main())
