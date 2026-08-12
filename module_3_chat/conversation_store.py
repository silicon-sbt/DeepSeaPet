"""对话持久化 — JSON 文件存储多会话"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from module_2_api.config_manager import CONFIG_DIR

STORE_FILE = CONFIG_DIR / "conversations.json"
MAX_MESSAGES = 100  # 保留最近 100 条消息（50 轮对话）


class Conversation:
    def __init__(self, id=None, title="", messages=None, created_at=None):
        self.id = id or str(uuid.uuid4())
        self.title = title
        self.messages = messages or []
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id"),
            title=d.get("title", ""),
            messages=d.get("messages", []),
            created_at=d.get("created_at", ""),
        )

    @property
    def message_count(self):
        return len(self.messages)


class ConversationStore:
    """管理所有对话——增删改查 + JSON 持久化"""

    def __init__(self):
        self._conversations = {}  # id -> Conversation
        self._current_id = None
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.load()

    # ── 持久化 ──────────────────────────

    def load(self):
        try:
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._conversations = {}
            self._current_id = None
            self.save()
            return
        self._current_id = data.get("current_id")
        self._conversations = {}
        for d in data.get("conversations", []):
            conv = Conversation.from_dict(d)
            self._conversations[conv.id] = conv

    def save(self):
        data = {
            "current_id": self._current_id,
            "conversations": [c.to_dict() for c in self._conversations.values()],
        }
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── CRUD ─────────────────────────────

    def list_all(self) -> list[Conversation]:
        """返回所有对话摘要（按创建时间倒序）"""
        return sorted(
            self._conversations.values(),
            key=lambda c: c.created_at,
            reverse=True,
        )

    def get(self, conv_id: str) -> Conversation | None:
        return self._conversations.get(conv_id)

    def create(self) -> Conversation:
        conv = Conversation()
        self._conversations[conv.id] = conv
        self._current_id = conv.id
        self.save()
        return conv

    def delete(self, conv_id: str) -> bool:
        if conv_id not in self._conversations:
            return False
        del self._conversations[conv_id]
        if self._current_id == conv_id:
            # 切换到其他对话或清空
            remaining = self.list_all()
            self._current_id = remaining[0].id if remaining else None
        self.save()
        return True

    def add_message(self, conv_id: str, role: str, content: str):
        conv = self._conversations.get(conv_id)
        if not conv:
            return
        conv.messages.append({"role": role, "content": content})
        # 自动截断
        if len(conv.messages) > MAX_MESSAGES:
            conv.messages = conv.messages[-MAX_MESSAGES:]
        # 自动标题
        if not conv.title and role == "user":
            conv.title = content[:20] + ("…" if len(content) > 20 else "")
        self.save()

    def get_history(self, conv_id: str) -> list[dict]:
        """返回 LLM 格式消息列表"""
        conv = self._conversations.get(conv_id)
        return list(conv.messages) if conv else []

    @property
    def current_id(self) -> str | None:
        return self._current_id

    @current_id.setter
    def current_id(self, conv_id: str):
        if conv_id in self._conversations or conv_id is None:
            self._current_id = conv_id
            self.save()

    def has_conversations(self) -> bool:
        return len(self._conversations) > 0
