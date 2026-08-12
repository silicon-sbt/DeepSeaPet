"""配置管理器 — 单例 JSON 持久化"""
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("APPDATA", "")) / "DeepSeaPet"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_type": "",        # "deepseek" | "custom" | ""
    "api_key": "",
    "api_base": "",        # 仅 custom 时生效
    "api_model": "deepseek-v4-flash",
    "auto_start": False,
    "confirm_delete": True,
    "has_greeted": False,
    "pet_x": 100,
    "pet_y": 100,
    "chat_w": 400,
    "chat_h": 600,
}


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
        self._data[key] = value
        self.save()

    def load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            self._data.update(stored)
        except (FileNotFoundError, json.JSONDecodeError):
            self.save()

    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

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
    def has_greeted(self):     return self._data["has_greeted"]

    @has_greeted.setter
    def has_greeted(self, v):  self.set("has_greeted", v)

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
