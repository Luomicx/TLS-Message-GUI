from __future__ import annotations

import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from typing import cast, override

from client_app.network.client_controller import ClientController
from client_app_edifice.adapter import ProtocolAdapter
from client_app_edifice.pages import ChatShellController, LoginFlowController
from client_app_edifice.state import AppState, AuthState, RequestStateKind, ViewMode
from server_app.db import Database
from server_app.network.server_controller import ServerController


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        _host, port = cast(tuple[str, int], sock.getsockname())
        return port


class ClientAppEdificeMVPIntegrationTest(unittest.TestCase):
    temp_dir: Path | None = None
    db: Database | None = None
    server: ServerController | None = None
    port: int = 0
    adapter: ProtocolAdapter | None = None
    state: AppState | None = None
    refresh_calls: int = 0
    login_controller: LoginFlowController | None = None
    chat_shell_controller: ChatShellController | None = None

    @override
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        db_path = self.temp_dir / "server.db"
        self.db = Database(db_path, journal_mode="DELETE")
        self.db.init_schema()
        _ = self.db.register_user(
            username="alice",
            password="pw1",
            encoding_rule=["base64"],
        )
        _ = self.db.register_user(
            username="bob",
            password="pw2",
            encoding_rule=["base64"],
        )
        _ = self.db.register_user(
            username="carol",
            password="pw3",
            encoding_rule=["base64"],
        )

        bob = self.db.get_user_by_username("bob")
        carol = self.db.get_user_by_username("carol")
        assert bob is not None
        assert carol is not None
        bob_id = bob.get("id")
        carol_id = carol.get("id")
        assert isinstance(bob_id, int)
        assert isinstance(carol_id, int)
        _ = self.db.add_friend("alice", bob_id)
        _ = self.db.add_friend("alice", carol_id)

        _ = self.db.save_message(
            sender="carol",
            receiver="alice",
            content="older from carol",
        )
        _ = self.db.save_message(
            sender="bob",
            receiver="alice",
            content="newer from bob",
        )

        self.server = ServerController(db=self.db, host="127.0.0.1")
        self.port = get_free_port()
        self.server.start(self.port)

        self.adapter = ProtocolAdapter(
            name="edifice-integration",
            controller=ClientController(host="127.0.0.1", port=self.port),
        )
        self.state = AppState()
        self.refresh_calls = 0
        self.login_controller = LoginFlowController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=self._refresh,
        )
        self.chat_shell_controller = ChatShellController(
            state=self.state,
            adapter=self.adapter,
            on_state_change=self._refresh,
        )

    @override
    def tearDown(self) -> None:
        if self.adapter is not None:
            self.adapter.close()
        if self.server is not None:
            self.server.stop()
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _refresh(self) -> None:
        self.refresh_calls += 1

    def _login_as_alice(self) -> None:
        login_controller = self.login_controller
        server = self.server
        state = self.state
        assert login_controller is not None
        assert server is not None
        assert state is not None

        login_controller.submit_login("alice", "pw1")

        self.assertEqual(
            state.active_view,
            ViewMode.CHAT,
            "login orchestration drift: successful login should switch the MVP app into chat view",
        )
        self.assertEqual(
            state.auth_state,
            AuthState.LOGGED_IN,
            "login orchestration drift: auth state should be LOGGED_IN after a successful login",
        )
        self.assertTrue(
            server.is_user_online("alice"),
            "protocol drift: the real TLS login path should mark alice online on the server",
        )
        self.assertIsNotNone(
            state.current_user,
            "adapter/login drift: a successful login must populate current_user",
        )
        current_user = state.current_user
        assert current_user is not None
        self.assertEqual(current_user.username, "alice")
        self.assertEqual(
            [session.peer for session in state.sessions],
            ["bob", "carol"],
            "session normalization drift: login should expose the real server session list in stable order",
        )
        self.assertIsNone(state.current_session)
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

    def _assert_logged_out(self) -> None:
        server = self.server
        state = self.state
        assert server is not None
        assert state is not None

        self.assertEqual(
            state.active_view,
            ViewMode.LOGIN,
            "cleanup drift: logout should always return the MVP app to login view",
        )
        self.assertEqual(state.auth_state, AuthState.LOGGED_OUT)
        self.assertIsNone(state.current_user)
        self.assertIsNone(state.current_session)
        self.assertEqual(state.sessions, [])
        self.assertEqual(state.messages, [])
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)
        self.assertFalse(
            server.is_user_online("alice"),
            "cleanup/protocol drift: logout should clear alice from the server online registry",
        )

    def test_login_bootstrap_loads_default_session_and_logout_cleans_up(self) -> None:
        login_controller = self.login_controller
        chat_shell_controller = self.chat_shell_controller
        state = self.state
        assert login_controller is not None
        assert chat_shell_controller is not None
        assert state is not None

        self._login_as_alice()

        self.assertTrue(
            login_controller.should_bootstrap_initial_session(),
            "bootstrap drift: login with available sessions should request an initial session load",
        )

        chat_shell_controller.load_initial_session()

        self.assertIsNotNone(
            state.current_session,
            "bootstrap drift: initial load should select a default conversation",
        )
        current_session = state.current_session
        assert current_session is not None
        self.assertEqual(
            current_session.peer,
            "bob",
            "session-order drift: the newest real server session should become the default conversation",
        )
        self.assertEqual(
            [message.content for message in state.messages],
            ["newer from bob"],
            "message-load drift: bootstrapped transcript should reflect the selected peer only",
        )
        self.assertEqual(
            [message.outgoing for message in state.messages],
            [False],
            "message-direction drift: pulled history from bob should remain incoming for alice",
        )
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

        chat_shell_controller.request_logout()

        self._assert_logged_out()
        self.assertGreaterEqual(
            self.refresh_calls,
            3,
            "controller orchestration drift: login, bootstrap, and logout should all emit state refreshes",
        )

    def test_explicit_session_selection_sends_message_refreshes_transcript_and_logs_out(
        self,
    ) -> None:
        chat_shell_controller = self.chat_shell_controller
        state = self.state
        assert chat_shell_controller is not None
        assert state is not None

        self._login_as_alice()

        chat_shell_controller.select_session("carol")

        self.assertIsNotNone(
            state.current_session,
            "session-selection drift: explicit session selection should populate current_session",
        )
        current_session = state.current_session
        assert current_session is not None
        self.assertEqual(
            current_session.peer,
            "carol",
            "session-selection drift: the chosen peer should remain active after message load finishes",
        )
        self.assertEqual(
            [message.content for message in state.messages],
            ["older from carol"],
            "message-load drift: explicit selection should load only the chosen peer transcript",
        )
        self.assertEqual(
            [message.outgoing for message in state.messages],
            [False],
        )
        self.assertIsNone(state.error_message)

        sent = chat_shell_controller.submit_message("  reply to carol  ")

        self.assertTrue(
            sent,
            "send-flow drift: a valid message on the active conversation should complete successfully",
        )
        self.assertIsNotNone(state.current_session)
        current_session = state.current_session
        assert current_session is not None
        self.assertEqual(current_session.peer, "carol")
        self.assertEqual(
            [
                (message.sender, message.content, message.outgoing)
                for message in state.messages
            ],
            [
                ("carol", "older from carol", False),
                ("alice", "reply to carol", True),
            ],
            "send-refresh drift: after a real send, transcript refresh should preserve history and append alice's outgoing message for the active peer",
        )
        self.assertEqual(state.request_state.kind, RequestStateKind.IDLE)
        self.assertFalse(state.request_state.is_loading)
        self.assertIsNone(state.error_message)

        chat_shell_controller.request_logout()

        self._assert_logged_out()


if __name__ == "__main__":
    raise SystemExit(unittest.main())
