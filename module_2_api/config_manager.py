"""配置管理器 — 单例 JSON 持久化

写盘一律走原子替换（临时文件 + os.replace）：配置文件里存着 API Key，
直接覆盖写一旦中途失败（进程被杀 / 断电），留下的就是半截 JSON。
读取遇到坏文件时先备份成 .corrupt 再回落默认值——解析失败绝不能把用户数据悄悄清掉。
"""
import json
import os
import shutil
import sys
from pathlib import Path

CONFIG_DIR = Path(os.getenv("APPDATA") or Path.home()) / "DeepSeaPet"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 默认模型只在这里定义一次，main.py / api_client.py 都引用这个常量
DEFAULT_MODEL = "deepseek-v4-flash"

# 聊天窗默认尺寸。旧版 DEFAULT_CONFIG 里写的 (400, 600) 从未被任何代码读取过，
# 读到这一对就说明是历史遗留值而不是用户改过的尺寸，按"未设置"处理。
DEFAULT_CHAT_W, DEFAULT_CHAT_H = 520, 450
_LEGACY_CHAT_SIZE = (400, 600)

DEFAULT_CONFIG = {
    "api_type": "",        # "deepseek" | "custom" | ""
    "api_key": "",
    "api_base": "",        # 仅 custom 时生效
    "api_model": DEFAULT_MODEL,
    "auto_start": False,
    "confirm_delete": True,
    "pet_x": 100,
    "pet_y": 100,
    "chat_w": DEFAULT_CHAT_W,
    "chat_h": DEFAULT_CHAT_H,
}


def atomic_write_json(path: Path, data) -> None:
    """原子写 JSON：同目录临时文件 → fsync → os.replace（同分区 rename 是原子的）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_json(path: Path):
    """读 JSON；文件损坏时备份为 .corrupt 并返回 None，不覆盖原文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        backup = path.with_suffix(path.suffix + ".corrupt")
        try:
            shutil.copy2(path, backup)
            print(f"[config] {path.name} 解析失败（{e}），已备份为 {backup.name}，本次使用默认值",
                  file=sys.stderr)
        except OSError:
            pass
        return None


class ConfigManager:
    """单例配置管理器，自动读写 JSON"""
    _instance = None

    def __init__(self):
        self._data = dict(DEFAULT_CONFIG)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.load()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── 通用读写 ──────────────────────────

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        if self._data.get(key) == value:
            return                      # 值没变就不落盘，避免无谓写盘
        self._data[key] = value
        self.save()

    def load(self):
        stored = load_json(CONFIG_FILE)
        if stored is None:
            self.save()                 # 首次运行（或坏文件已备份）落一份默认配置
            return
        if isinstance(stored, dict):
            self._data.update(stored)
        if (self._data.get("chat_w"), self._data.get("chat_h")) == _LEGACY_CHAT_SIZE:
            self._data["chat_w"], self._data["chat_h"] = DEFAULT_CHAT_W, DEFAULT_CHAT_H

    def save(self):
        atomic_write_json(CONFIG_FILE, self._data)

    # ── 便捷属性 ──────────────────────────

    @property
    def api_type(self):        return self._data["api_type"]

    @api_type.setter
    def api_type(self, v):     self.set("api_type", v)

    @property
    def api_key(self):         return self._data["api_key"]

    @api_key.setter
    def api_key(self, v):      self.set("api_key", v)

    @property
    def api_base(self):        return self._data["api_base"]

    @api_base.setter
    def api_base(self, v):     self.set("api_base", v)

    @property
    def api_model(self):       return self._data["api_model"]

    @api_model.setter
    def api_model(self, v):    self.set("api_model", v)

    @property
    def auto_start(self):      return self._data["auto_start"]

    @auto_start.setter
    def auto_start(self, v):   self.set("auto_start", v)

    @property
    def confirm_delete(self):  return self._data["confirm_delete"]

    @confirm_delete.setter
    def confirm_delete(self, v): self.set("confirm_delete", v)

    @property
    def pet_x(self):           return self._data["pet_x"]

    @pet_x.setter
    def pet_x(self, v):        self.set("pet_x", v)

    @property
    def pet_y(self):           return self._data["pet_y"]

    @pet_y.setter
    def pet_y(self, v):        self.set("pet_y", v)

    @property
    def chat_w(self):          return self._data["chat_w"]

    @chat_w.setter
    def chat_w(self, v):       self.set("chat_w", v)

    @property
    def chat_h(self):          return self._data["chat_h"]

    @chat_h.setter
    def chat_h(self, v):       self.set("chat_h", v)
