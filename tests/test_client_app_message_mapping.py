from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "client_app" / "app.py"


def load_app_module():
    original_modules = {
        name: sys.modules.get(name)
        for name in [
            "PyQt5",
            "PyQt5.QtCore",
            "PyQt5.QtWidgets",
            "client_app",
            "client_app.network",
            "client_app.ui",
            "client_app.app",
        ]
    }

    qtcore = types.ModuleType("PyQt5.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        AA_EnableHighDpiScaling=1,
        AA_UseHighDpiPixmaps=2,
    )

    qtwidgets = types.ModuleType("PyQt5.QtWidgets")

    class QApplication:
        @staticmethod
        def setAttribute(*_args, **_kwargs):
            return None

        @staticmethod
        def instance():
            return types.SimpleNamespace(exec_=lambda: 0)

    qtwidgets.QApplication = QApplication

    pyqt5 = types.ModuleType("PyQt5")
    sys.modules["PyQt5"] = pyqt5
    sys.modules["PyQt5.QtCore"] = qtcore
    sys.modules["PyQt5.QtWidgets"] = qtwidgets

    network_module = types.ModuleType("client_app.network")
    network_module.ClientController = type("ClientController", (), {})
    sys.modules["client_app.network"] = network_module

    ui_module = types.ModuleType("client_app.ui")
    ui_module.ChatWindow = type("ChatWindow", (), {})
    ui_module.LoginWindow = type("LoginWindow", (), {})
    sys.modules["client_app.ui"] = ui_module

    package_module = types.ModuleType("client_app")
    package_module.__path__ = [str(PROJECT_ROOT / "client_app")]
    sys.modules["client_app"] = package_module

    spec = importlib.util.spec_from_file_location("client_app.app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    for name, original in original_modules.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
    return module


app_module = load_app_module()
ClientApplication = app_module.ClientApplication


class ClientAppMessageMappingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = ClientApplication.__new__(ClientApplication)

    def test_login_invalid_credentials_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "invalid_credentials", "message": "bad password"},
            default_message="登录失败",
        )
        self.assertEqual(message, "账号或密码错误，请重新输入")

    def test_search_user_not_found_maps_to_search_specific_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "user_not_found", "message": "not found"},
            default_message="搜索失败",
        )
        self.assertEqual(message, "未找到符合条件的用户")

    def test_add_friend_already_friend_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "already_friend", "message": "already"},
            default_message="添加好友完成",
        )
        self.assertEqual(message, "对方已经是你的好友，无需重复添加")

    def test_send_message_network_error_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {
                "ok": False,
                "code": "network_error",
                "message": "服务器连接失败: timeout",
            },
            default_message="消息发送完成",
        )
        self.assertEqual(message, "网络连接失败，请检查服务器状态后重试")

    def test_load_messages_friend_not_found_maps_to_clear_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": False, "code": "friend_not_found", "message": "missing friend"},
            default_message="消息加载失败",
        )
        self.assertEqual(message, "未找到该好友或会话")

    def test_success_message_keeps_backend_message(self) -> None:
        message = self.app._resolve_user_message(
            {"ok": True, "code": "ok", "message": "搜索完成，共 2 条结果"},
            default_message="搜索成功",
        )
        self.assertEqual(message, "搜索完成，共 2 条结果")


if __name__ == "__main__":
    unittest.main()
