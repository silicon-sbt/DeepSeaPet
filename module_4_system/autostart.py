"""开机自启动 — 通过 Windows 注册表 Run 键"""
import sys
import winreg


APP_NAME = "DeepSeaPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutoStartManager:
    """管理开机自启注册表项"""

    @staticmethod
    def enable():
        """添加开机自启"""
        exe_path = sys.executable
        # 如果是 python 运行，指向 main.py；否则是打包后的 exe
        if exe_path.lower().endswith("python.exe") or exe_path.lower().endswith("pythonw.exe"):
            from pathlib import Path
            main_py = Path(__file__).parent.parent / "main.py"
            command = f'"{exe_path}" "{main_py}"'
        else:
            command = f'"{exe_path}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
        except OSError:
            pass

    @staticmethod
    def disable():
        """移除开机自启"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, APP_NAME)
            winreg.CloseKey(key)
        except OSError:
            pass

    @staticmethod
    def is_enabled() -> bool:
        """查询是否已设置开机自启"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return bool(value)
        except OSError:
            return False
