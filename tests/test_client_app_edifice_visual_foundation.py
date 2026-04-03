from __future__ import annotations

import unittest

from client_app_edifice.visual_foundation import (
    MVP_LAYOUT_FOUNDATION,
    validate_layout_foundation,
)


class ClientAppEdificeVisualFoundationTest(unittest.TestCase):
    def test_spacing_tokens_follow_increasing_eight_point_rhythm(self) -> None:
        spacing = MVP_LAYOUT_FOUNDATION.spacing

        self.assertEqual(spacing.base, 8)
        self.assertEqual(spacing.values(), (8, 12, 16, 24, 32, 40))

    def test_login_shell_keeps_auth_region_primary_and_status_anchored(self) -> None:
        login_shell = MVP_LAYOUT_FOUNDATION.login_shell
        stack_keys = [region.key for region in login_shell.auth_stack]

        self.assertEqual(login_shell.min_window.width, 960)
        self.assertGreaterEqual(
            login_shell.min_window.width,
            login_shell.minimum_required_width(),
        )
        self.assertGreater(
            login_shell.auth_column.preferred_width,
            login_shell.intro_column.preferred_width,
        )
        self.assertIn(login_shell.status_region_key, stack_keys)
        self.assertIn(login_shell.primary_action_region_key, stack_keys)

    def test_chat_shell_prioritizes_reading_surface_and_caps_sidebar_width(
        self,
    ) -> None:
        chat_shell = MVP_LAYOUT_FOUNDATION.chat_shell
        content_regions = {region.key: region for region in chat_shell.content_stack}
        composer_max_height = content_regions["composer_region"].max_height

        self.assertEqual(chat_shell.min_window.width, 1080)
        self.assertGreaterEqual(
            chat_shell.min_window.width,
            chat_shell.minimum_required_width(),
        )
        self.assertLess(
            chat_shell.sidebar_column.preferred_width,
            chat_shell.transcript_column_min_width,
        )
        self.assertEqual(chat_shell.empty_state_region_key, "message_region")
        self.assertEqual(chat_shell.request_feedback_region_key, "composer_region")
        self.assertGreaterEqual(content_regions["message_region"].flex_weight, 1)
        self.assertIsNotNone(composer_max_height)
        assert composer_max_height is not None
        self.assertGreater(composer_max_height, 200)

    def test_mvp_layout_exclusions_and_validation_lock_scope(self) -> None:
        exclusions = set(MVP_LAYOUT_FOUNDATION.login_shell.excluded_affordances)

        self.assertSetEqual(
            exclusions,
            set(MVP_LAYOUT_FOUNDATION.chat_shell.excluded_affordances),
        )
        self.assertTrue(
            {
                "register_entry",
                "guest_preview",
                "search_bar",
                "add_friend_action",
                "attachments",
                "emoji_bar",
                "theme_switcher",
            }.issubset(exclusions)
        )
        self.assertEqual(validate_layout_foundation(), ())


if __name__ == "__main__":
    raise SystemExit(unittest.main())
