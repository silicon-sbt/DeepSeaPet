"""开机自启动 — 通过 Windows 注册表 Run 键

以前 enable/disable 把 OSError 吞成 pass，托盘照样弹"已开启开机自启"，
注册表其实没写进去——用户要等到下次开机才知道。现在失败向上抛，由调用方如实回报。
"""
import sys
import winreg
from pathlib import Path

APP_NAME = "DeepSeaPet"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class AutoStartManager:
    """管理开机自启注册表项"""

    @staticmethod
    def _command() -> str:
        """打包后指向 exe 自身；源码运行时指向 main.py"""
        exe = sys.executable
        if exe.lower().endswith(("python.exe", "pythonw.exe")):
            main_py = Path(__file__).resolve().parent.parent / "main.py"
            return f'"{exe}" "{main_py}"'
        return f'"{exe}"'

    @staticmethod
    def enable() -> str:
        """写入自启项，返回实际写入的命令行；失败抛 OSError"""
        command = AutoStartManager._command()
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        finally:
            winreg.CloseKey(key)
        return command

    @staticmethod
    def disable() -> None:
        """移除自启项；本来就不存在时静默通过"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            return
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
        finally:
            winreg.CloseKey(key)

    @staticmethod
    def is_enabled() -> bool:
        """以注册表实际内容为准（不要信 config 里那个勾选状态，它会漂移）"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ)
        except OSError:
            return False
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
        except OSError:
            return False
        finally:
            winreg.CloseKey(key)
