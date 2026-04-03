from __future__ import annotations

import importlib
import os
import subprocess
import sys
import unittest
from collections.abc import Callable
from types import ModuleType
from typing import Protocol, cast


class MainModule(Protocol):
    main: Callable[[], int]


def import_main_module(module_name: str) -> MainModule:
    return cast(MainModule, cast(object, importlib.import_module(module_name)))


def import_module(module_name: str) -> ModuleType:
    return importlib.import_module(module_name)


class ClientEntrypointCoexistenceTest(unittest.TestCase):
    def test_new_client_smoke_entry_starts_and_exits(self) -> None:
        command = [sys.executable, "-m", "client_app_edifice"]
        env = os.environ.copy()
        env["CLIENT_APP_EDIFICE_SMOKE_DELAY"] = "0.1"

        process = subprocess.run(command, text=True, check=False, env=env)

        self.assertEqual(
            process.returncode,
            0,
            msg="New PyEdifice client entry failed smoke startup/exit",
        )

    def test_new_client_entry_exports_main(self) -> None:
        module = import_main_module("client_app_edifice.__main__")
        package = import_main_module("client_app_edifice")

        self.assertTrue(callable(module.main))
        self.assertEqual(module.main, package.main)

    def test_old_client_entry_remains_importable(self) -> None:
        module = import_main_module("client_app.__main__")

        self.assertTrue(callable(module.main))

    def test_old_and_new_entries_are_distinct_modules(self) -> None:
        legacy_entry = import_module("client_app.__main__")
        new_entry = import_module("client_app_edifice.__main__")
        legacy_main = import_main_module("client_app.__main__").main
        new_main = import_main_module("client_app_edifice.__main__").main

        self.assertNotEqual(legacy_entry.__name__, new_entry.__name__)
        self.assertNotEqual(legacy_main.__module__, new_main.__module__)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
