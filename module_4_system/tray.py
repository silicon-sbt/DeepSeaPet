"""托盘图标 + API 设置对话框

从 main.py 内联代码里拆出来：入口文件只该负责组装，
不该同时背着托盘菜单、注册表开关和一个表单对话框。
"""
import sys
from pathlib import Path

from PySide6.QtWidgets import (QSystemTrayIcon, QMenu, QDialog, QFormLayout,
                               QLineEdit, QComboBox, QDialogButtonBox,
                               QMessageBox, QLabel)
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QPen, QBrush
from PySide6.QtCore import Qt, Signal

from module_2_api.config_manager import ConfigManager, DEFAULT_MODEL
from module_4_system.autostart import AutoStartManager


def _asset_dir() -> Path:
    """PyInstaller 打包后资源解包到 sys._MEIPASS"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def make_icon(name="tray") -> QIcon:
    """优先用仓库自带的 icon.ico，缺素材时退回代码画的蓝鲸尾巴"""
    ico = _asset_dir() / "icon.ico"
    if ico.exists():
        return QIcon(str(ico))
    px = QPixmap(64, 64)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
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
        self.config.api_model = self.model_edit.text().strip() or (
            DEFAULT_MODEL if t == "deepseek" else "gpt-3.5-turbo")
        self.accept()


class TrayIcon(QSystemTrayIcon):
    """托盘图标：设置 API / 开机自启 / 退出

    自启勾选状态一律以注册表实际内容为准——以前读的是 config 里的值，
    注册表写失败时那个勾还会一直勾着，属于骗自己。
    """

    quit_requested = Signal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config

        menu = QMenu()
        menu.addAction("设置 API", self._show_api_dialog)
        menu.addSeparator()

        self._autostart_action = QAction("开机自启")
        self._autostart_action.setCheckable(True)
        self._autostart_action.toggled.connect(self._toggle_autostart)
        menu.addAction(self._autostart_action)

        menu.addSeparator()
        menu.addAction("退出", self.quit_requested.emit)

        self.setIcon(make_icon("tray"))
        self.setToolTip("深海鲸鱼娘")
        self.setContextMenu(menu)
        self._sync_autostart()

    def _sync_autostart(self):
        """按注册表真值回填勾选（blockSignals 防止回填动作又触发一次写注册表）"""
        actual = AutoStartManager.is_enabled()
        self._autostart_action.blockSignals(True)
        self._autostart_action.setChecked(actual)
        self._autostart_action.blockSignals(False)
        self.config.auto_start = actual

    def _show_api_dialog(self):
        dlg = ApiSetupDialog(self.config)
        if dlg.exec() == QDialog.Accepted:
            self.showMessage("深海鲸鱼娘", "API 配置已保存~", QSystemTrayIcon.Information, 2000)

    def _toggle_autostart(self, enabled):
        try:
            if enabled:
                AutoStartManager.enable()
            else:
                AutoStartManager.disable()
        except OSError as e:
            self.showMessage("深海鲸鱼娘", f"开机自启设置失败：{e}",
                             QSystemTrayIcon.Warning, 3000)
        else:
            self.showMessage("深海鲸鱼娘",
                             "已开启开机自启" if enabled else "已关闭开机自启",
                             QSystemTrayIcon.Information, 1500)
        self._sync_autostart()
