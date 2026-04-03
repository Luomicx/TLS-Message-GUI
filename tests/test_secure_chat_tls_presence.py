from __future__ import annotations

import socket
import shutil
import tempfile
import unittest
from pathlib import Path

from client_app.network.client_controller import ClientController
from server_app.db import Database
from server_app.network.server_controller import ServerController


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class SecureChatTLSPresenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        db_path = self.temp_dir / "server.db"
        self.db = Database(db_path, journal_mode="DELETE")
        self.db.init_schema()
        self.db.register_user(
            username="alice", password="pw1", encoding_rule=["base64"]
        )
        self.db.register_user(username="bob", password="pw2", encoding_rule=["base64"])
        bob = self.db.get_user_by_username("bob")
        assert bob is not None
        self.db.add_friend("alice", int(bob["id"]))

        self.server = ServerController(db=self.db, host="127.0.0.1")
        self.port = get_free_port()
        self.server.start(self.port)

        self.alice_client = ClientController(host="127.0.0.1", port=self.port)
        self.bob_client = ClientController(host="127.0.0.1", port=self.port)

    def tearDown(self) -> None:
        self.alice_client.close()
        self.bob_client.close()
        self.server.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tls_login_and_presence_flow(self) -> None:
        alice_login = self.alice_client.login("alice", "pw1")
        self.assertTrue(alice_login["ok"])
        self.assertEqual(alice_login["data"]["user"]["username"], "alice")
        self.assertTrue(alice_login["data"]["user"]["is_online"])

        alice_friends = alice_login["data"]["friends"]
        self.assertEqual(len(alice_friends), 1)
        self.assertFalse(alice_friends[0]["is_online"])

        bob_login = self.bob_client.login("bob", "pw2")
        self.assertTrue(bob_login["ok"])
        self.assertTrue(bob_login["data"]["user"]["is_online"])

        refreshed_friends = self.alice_client.list_friends("alice")
        self.assertTrue(refreshed_friends["ok"])
        self.assertTrue(refreshed_friends["data"]["friends"][0]["is_online"])

    def test_tls_message_roundtrip(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        self.assertTrue(self.bob_client.login("bob", "pw2")["ok"])

        sent = self.alice_client.send_message(
            "alice", "bob", "hello over tls", ["base64"]
        )
        self.assertTrue(sent["ok"])

        pulled = self.bob_client.pull_messages("bob", peer="alice")
        self.assertTrue(pulled["ok"])
        self.assertEqual(len(pulled["data"]["messages"]), 1)
        self.assertEqual(pulled["data"]["messages"][0]["content"], "hello over tls")


if __name__ == "__main__":
    unittest.main()
