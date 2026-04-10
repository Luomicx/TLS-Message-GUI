from __future__ import annotations

import socket
import shutil
import tempfile
import unittest
import os
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
        fd, db_file = tempfile.mkstemp(suffix=".db", dir=str(Path.cwd()))
        os.close(fd)
        self.temp_dir = None
        self.db_path = Path(db_file)
        self.db = Database(self.db_path, journal_mode="DELETE")
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
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        try:
            self.db_path.unlink(missing_ok=True)
        except PermissionError:
            pass

    def test_tls_login_and_presence_flow(self) -> None:
        alice_login = self.alice_client.login("alice", "pw1")
        self.assertTrue(alice_login["ok"])
        self.assertEqual(alice_login["data"]["user"]["username"], "alice")
        self.assertTrue(alice_login["data"]["user"]["is_online"])
        self.assertIn("previous_last_seen_at", alice_login["data"]["user"])

        alice_friends = alice_login["data"]["friends"]
        self.assertEqual(len(alice_friends), 1)
        self.assertFalse(alice_friends[0]["is_online"])

        bob_login = self.bob_client.login("bob", "pw2")
        self.assertTrue(bob_login["ok"])
        self.assertTrue(bob_login["data"]["user"]["is_online"])

        refreshed_friends = self.alice_client.list_friends("alice")
        self.assertTrue(refreshed_friends["ok"])
        self.assertTrue(refreshed_friends["data"]["friends"][0]["is_online"])

    def test_login_response_returns_previous_last_seen_timestamp(self) -> None:
        first_login = self.alice_client.login("alice", "pw1")
        self.assertTrue(first_login["ok"])
        self.assertEqual(first_login["data"]["user"]["previous_last_seen_at"], "")

        logged_out = self.alice_client.logout("alice")
        self.assertTrue(logged_out["ok"])

        second_login = self.alice_client.login("alice", "pw1")
        self.assertTrue(second_login["ok"])
        self.assertTrue(
            str(second_login["data"]["user"]["previous_last_seen_at"]).strip()
        )

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

    def test_login_failed_attempts_and_lock(self) -> None:
        for remain in [4, 3, 2, 1]:
            failed = self.alice_client.login("alice", "wrong")
            self.assertFalse(failed["ok"])
            self.assertEqual(failed["code"], "invalid_credentials")
            self.assertEqual(failed["data"]["remaining_attempts"], remain)

        locked = self.alice_client.login("alice", "wrong")
        self.assertFalse(locked["ok"])
        self.assertEqual(locked["code"], "user_locked")
        self.assertEqual(locked["data"]["remaining_attempts"], 0)

    def test_single_session_kicks_previous_client(self) -> None:
        first = ClientController(host="127.0.0.1", port=self.port)
        second = ClientController(host="127.0.0.1", port=self.port)
        try:
            self.assertTrue(first.login("alice", "pw1")["ok"])
            self.assertTrue(second.login("alice", "pw1")["ok"])
            kicked = first.list_friends("alice")
            self.assertFalse(kicked["ok"])
            self.assertEqual(kicked["code"], "force_logout")
            self.assertTrue(self.server.is_user_online("alice"))
            self.assertTrue(second.list_friends("alice")["ok"])
        finally:
            first.close()
            second.close()

    def test_reconnected_stale_client_receives_force_logout(self) -> None:
        first = ClientController(host="127.0.0.1", port=self.port)
        second = ClientController(host="127.0.0.1", port=self.port)
        stale = ClientController(host="127.0.0.1", port=self.port)
        try:
            self.assertTrue(first.login("alice", "pw1")["ok"])
            self.assertTrue(second.login("alice", "pw1")["ok"])
            kicked = stale.list_friends("alice")
            self.assertFalse(kicked["ok"])
            self.assertEqual(kicked["code"], "force_logout")
        finally:
            first.close()
            second.close()
            stale.close()

    def test_register_requires_recovery_info(self) -> None:
        missing_recovery = self.alice_client.register("charlie", "pw3", "", "")
        self.assertFalse(missing_recovery["ok"])
        self.assertEqual(missing_recovery["code"], "recovery_required")

        created = self.alice_client.register("charlie", "pw3", "pet", "cat")
        self.assertTrue(created["ok"])
        recovered = self.alice_client.recover_password("charlie", "pet", "cat", "pw3-new")
        self.assertTrue(recovered["ok"])

        self.alice_client.close()
        self.assertTrue(self.alice_client.login("charlie", "pw3-new")["ok"])

    def test_heartbeat_ack(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        hb = self.alice_client.heartbeat("alice")
        self.assertTrue(hb["ok"])
        self.assertEqual(hb["code"], "ok")

    def test_profile_update_and_password_recovery(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        profile = self.alice_client.get_profile("alice")
        self.assertTrue(profile["ok"])
        self.assertEqual(profile["data"]["profile"]["nickname"], "alice")

        updated = self.alice_client.update_profile("alice", "AliceNew")
        self.assertTrue(updated["ok"])
        self.assertEqual(updated["data"]["profile"]["nickname"], "AliceNew")

        changed = self.alice_client.change_password("alice", "pw1", "pw1-new")
        self.assertTrue(changed["ok"])

        self.alice_client.close()
        self.assertTrue(self.alice_client.login("alice", "pw1-new")["ok"])

        set_recovery = self.alice_client.set_recovery("alice", "default", "ans-1")
        self.assertTrue(set_recovery["ok"])
        questions = self.alice_client.get_recovery_questions("alice")
        self.assertTrue(questions["ok"])
        self.assertEqual(questions["data"]["questions"], ["default"])
        recovered = self.alice_client.recover_password(
            "alice", "default", "ans-1", "pw1-reset"
        )
        self.assertTrue(recovered["ok"])

        self.alice_client.close()
        self.assertTrue(self.alice_client.login("alice", "pw1-reset")["ok"])

    def test_get_recovery_questions_rejects_unknown_or_unset_user(self) -> None:
        missing_user = self.alice_client.get_recovery_questions("nobody")
        self.assertFalse(missing_user["ok"])
        self.assertEqual(missing_user["code"], "user_not_found")

        no_recovery = self.alice_client.get_recovery_questions("bob")
        self.assertFalse(no_recovery["ok"])
        self.assertEqual(no_recovery["code"], "recovery_not_set")

    def test_group_chat_roundtrip(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        self.assertTrue(self.bob_client.login("bob", "pw2")["ok"])

        created = self.alice_client.create_group("alice", "g-1", ["bob"])
        self.assertTrue(created["ok"])
        group_id = int(created["data"]["group"]["id"])

        sent = self.alice_client.send_group_message(
            "alice", group_id, "hello group", ["base64"]
        )
        self.assertTrue(sent["ok"])

        pulled = self.bob_client.pull_group_messages("bob", group_id)
        self.assertTrue(pulled["ok"])
        self.assertEqual(len(pulled["data"]["messages"]), 1)
        self.assertEqual(pulled["data"]["messages"][0]["content"], "hello group")

        groups = self.bob_client.list_groups("bob")
        self.assertTrue(groups["ok"])
        self.assertEqual(len(groups["data"]["groups"]), 1)
        self.assertEqual(groups["data"]["groups"][0]["name"], "g-1")

    def test_create_group_rejects_unknown_member(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        created = self.alice_client.create_group("alice", "bad-group", ["nobody"])
        self.assertFalse(created["ok"])
        self.assertEqual(created["code"], "group_member_not_found")

    def test_file_transfer_roundtrip(self) -> None:
        self.assertTrue(self.alice_client.login("alice", "pw1")["ok"])
        self.assertTrue(self.bob_client.login("bob", "pw2")["ok"])

        payload = b"sample file bytes"
        sent = self.alice_client.send_file("alice", "bob", "demo.txt", payload)
        self.assertTrue(sent["ok"])

        pulled = self.bob_client.pull_files("bob", peer="alice")
        self.assertTrue(pulled["ok"])
        self.assertEqual(len(pulled["data"]["files"]), 1)
        item = pulled["data"]["files"][0]
        self.assertEqual(item["file_name"], "demo.txt")
        self.assertEqual(item["file_size"], len(payload))


if __name__ == "__main__":
    unittest.main()

