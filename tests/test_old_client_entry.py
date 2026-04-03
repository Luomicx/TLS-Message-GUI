from __future__ import annotations

import importlib
import unittest


class OldClientEntryTest(unittest.TestCase):
    def test_client_app_main_importable(self) -> None:
        module = importlib.import_module("client_app.__main__")
        self.assertTrue(hasattr(module, "main"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
