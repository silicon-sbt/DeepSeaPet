"""深海鲸鱼娘桌宠 — 入口"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QSystemTrayIcon, QMenu,
                                QDialog, QFormLayout, QLineEdit, QComboBox,
                                QDialogButtonBox, QMessageBox, QLabel)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt

# 把项目根加到 path
sys.path.insert(0, str(Path(__file__).parent))

from module_2_api.config_manager import ConfigManager


def make_icon(name="tray"):
    """ponytail: 用代码画简单图标，省去素材依赖。后期替换为真实图标"""
    from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    # 蓝色鲸鱼尾巴简笔画
    p.setBrush(QBrush(QColor(66, 133, 244)))
    p.setPen(QPen(QColor(30, 80, 180), 2))
    if name == "tray":
        p.drawEllipse(8, 8, 48, 48)
        p.drawEllipse(18, 18, 12, 12)
        p.drawEllipse(34, 18, 12, 12)
        p.drawArc(16, 32, 32, 24, 0, -180 * 16)
    p.end()
    return QIcon(px)


class ApiSetupDialog(QDialog):
    """API 配置对话框"""
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("设置 API")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.api_type_combo = QComboBox()
        self.api_type_combo.addItems(["deepseek", "custom"])
        self.api_type_combo.setCurrentText(config.api_type or "deepseek")
        layout.addRow("API 类型:", self.api_type_combo)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText(config.api_key)
        self.api_key_edit.setPlaceholderText("sk-...")
        layout.addRow("API Key:", self.api_key_edit)

        self.api_base_edit = QLineEdit()
        self.api_base_edit.setText(config.api_base)
        self.api_base_edit.setPlaceholderText("https://api.deepseek.com")
        layout.addRow(QLabel("API 地址 (custom 时填写):"), self.api_base_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setText(config.api_model)
        layout.addRow("模型:", self.model_edit)

        self.api_type_combo.currentTextChanged.connect(self._on_type_changed)
        self._on_type_changed(config.api_type or "deepseek")

        btn = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn.accepted.connect(self._save)
        btn.rejected.connect(self.reject)
        layout.addRow(btn)

    def _on_type_changed(self, t):
        self.api_base_edit.setEnabled(t == "custom")

    def _save(self):
        t = self.api_type_combo.currentText()
        key = self.api_key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "API Key 不能为空")
            return
        self.config.api_type = t
        self.config.api_key = key
        self.config.api_base = self.api_base_edit.text().strip()
        self.config.api_model = self.model_edit.text().strip() or ("deepseek-v4-flash" if t == "deepseek" else "gpt-3.5-turbo")
        self.accept()


class App:
    def __init__(self):
        self.qapp = QApplication(sys.argv)
        self.qapp.setQuitOnLastWindowClosed(False)
        self.config = ConfigManager.instance()
        self._setup_tray()
        self._setup_pet()

    def _setup_pet(self):
        from module_1_core.pet_window import PetWindow
        self.pet = PetWindow(self.config)
        self.pet.clicked.connect(self._on_pet_clicked)
        self.pet.files_dropped.connect(self._on_files_dropped)
        self.pet.show()
        self.pet.raise_()  # 强制置顶

        # 启动时打招呼
        if self.config.api_key and not self.config.has_greeted:
            from module_3_chat.greeting import get_random_greeting
            msg = get_random_greeting(self.config.api_type or "deepseek")
            self.config.has_greeted = True
            # 延迟显示，等窗口初始化完
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, lambda: self.pet.show_bubble(msg, 5000))

    def _on_pet_clicked(self):
        try:
            from module_3_chat.chat_window import ChatWindow
            if not hasattr(self, "chat_win") or self.chat_win is None:
                self.chat_win = ChatWindow(self.config)
            self.chat_win.show()
            self.chat_win.raise_()
        except ImportError:
            self.pet.show_bubble("聊天模块还在开发中哦~", 2000)

    def _on_files_dropped(self, paths):
        try:
            from module_4_system.trash import TrashHandler
            result = TrashHandler.handle(self.config, paths)
            ok = len(result.get("success", []))
            if ok:
                self.pet.show_bubble(f"已删除 {ok} 个文件~", 2500)
        except ImportError:
            self.pet.show_bubble("垃圾桶还没准备好~", 2000)

    def _setup_tray(self):
        menu = QMenu()
        menu.addAction("设置 API", self._show_api_dialog)
        menu.addSeparator()

        self.auto_start_action = QAction("开机自启")
        self.auto_start_action.setCheckable(True)
        self.auto_start_action.setChecked(self.config.auto_start)
        self.auto_start_action.toggled.connect(self._toggle_autostart)
        menu.addAction(self.auto_start_action)

        menu.addSeparator()
        menu.addAction("退出", self._quit)

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(make_icon("tray"))
        self.tray.setToolTip("深海鲸鱼娘")
        self.tray.setContextMenu(menu)
        self.tray.show()

    def _show_api_dialog(self):
        dlg = ApiSetupDialog(self.config)
        if dlg.exec() == QDialog.Accepted:
            self.tray.showMessage("深海鲸鱼娘", "API 配置已保存~", QSystemTrayIcon.Information, 2000)

    def _toggle_autostart(self, enabled):
        self.config.auto_start = enabled
        # ponytail: 延迟导入，阶段 9 才实现真正的注册表写入
        try:
            from module_4_system.autostart import AutoStartManager
            if enabled:
                AutoStartManager.enable()
            else:
                AutoStartManager.disable()
            self.tray.showMessage("深海鲸鱼娘",
                "已开启开机自启" if enabled else "已关闭开机自启",
                QSystemTrayIcon.Information, 1500)
        except ImportError:
            self.tray.showMessage("深海鲸鱼娘", "自启模块尚未就绪", QSystemTrayIcon.Warning, 1500)

    def _quit(self):
        if hasattr(self, "pet"):
            self.pet.close()
        if hasattr(self, "chat_win") and self.chat_win:
            self.chat_win.close()
        self.tray.hide()
        self.qapp.quit()

    def run(self):
        sys.exit(self.qapp.exec())


if __name__ == "__main__":
    App().run()
