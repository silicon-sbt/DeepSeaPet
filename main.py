"""深海鲸鱼娘桌宠 — 入口

只做组装：桌宠窗口 + 托盘，然后把两边的事件接起来。
界面细节在 module_1_core / module_3_chat，托盘和 API 对话框在 module_4_system/tray.py。
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# 兼容从任意工作目录启动（打包后也要能找到同级模块）
sys.path.insert(0, str(Path(__file__).resolve().parent))

from module_2_api.config_manager import ConfigManager
from module_4_system.tray import TrayIcon


class App:
    def __init__(self, argv=None):
        self.qapp = QApplication(argv if argv is not None else sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)   # 关掉聊天窗不退出，桌宠还在
        self.config = ConfigManager.instance()
        self._chat_win = None

        from module_1_core.pet_window import PetWindow
        self.pet = PetWindow(self.config)
        self.pet.clicked.connect(self._on_pet_clicked)
        self.pet.chat_requested.connect(self._open_chat)
        self.pet.files_dropped.connect(self._on_files_dropped)
        self.pet.show()

        self.tray = TrayIcon(self.config)
        self.tray.quit_requested.connect(self._quit)

        # 打招呼：需求要求"设置好 API 时 / 每次打开软件时"都播，所以不再用一次性标记
        QTimer.singleShot(1000, self._greet)

    # ── 事件接线 ──────────────────────────

    def _greet(self):
        if not self.config.api_key:
            return
        from module_3_chat.greeting import get_random_greeting
        self.pet.show_bubble(get_random_greeting(self.config.api_type or "deepseek"), 5000)

    def _on_pet_clicked(self):
        """单击桌宠 → 显示/隐藏余额气泡（理念致敬 DeepSeek-Balance-Whale-Widget）"""
        self.pet.show_balance_bubble()

    def _open_chat(self):
        """双击桌宠 → 打开聊天窗（懒加载，关掉只是隐藏，下次直接复用）"""
        from module_3_chat.chat_window import ChatWindow
        if self._chat_win is None:
            self._chat_win = ChatWindow(self.config)
        self._chat_win.show()
        self._chat_win.raise_()

    def _on_files_dropped(self, paths):
        from module_4_system.trash import TrashHandler
        result = TrashHandler.handle(self.config, paths)
        ok, failed = len(result["success"]), len(result["failed"])
        if ok and not failed:
            self.pet.show_bubble(f"已删除 {ok} 个文件~", 2500)
        elif ok:
            self.pet.show_bubble(f"删了 {ok} 个，{failed} 个没成功", 3000)
        elif failed:
            reason = next(iter(result["errors"].values()), "未知原因")
            self.pet.show_bubble(f"{failed} 个都没删掉：{reason[:40]}", 3500)

    def _quit(self):
        self.pet.close()
        if self._chat_win is not None:
            self._chat_win.close()
        self.tray.hide()
        self.qapp.quit()

    def run(self):
        return self.qapp.exec()


if __name__ == "__main__":
    sys.exit(App().run())
