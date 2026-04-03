from __future__ import annotations

import os
import subprocess
import sys
import unittest


class ClientAppEdificeSmokeTest(unittest.TestCase):
    def test_smoke_app_starts_and_exits(self) -> None:
        command = [sys.executable, "-m", "client_app_edifice"]
        env = os.environ.copy()
        env["CLIENT_APP_EDIFICE_SMOKE_DELAY"] = "0.1"
        process = subprocess.run(command, text=True, check=False, env=env)
        self.assertEqual(
            process.returncode,
            0,
            msg="PyEdifice smoke app failed to exit cleanly",
        )


if __name__ == "__main__":
    raise SystemExit(unittest.main())
