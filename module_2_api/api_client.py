"""API 通信层 — 统一 LLM 调用接口（DeepSeek / 自定义 OpenAI 兼容）"""
import json
import urllib.error
import urllib.request
from typing import Generator

from openai import (
    APIError, APIConnectionError, AuthenticationError,
    RateLimitError, APITimeoutError, OpenAI,
)

from module_2_api.config_manager import ConfigManager, DEFAULT_MODEL


# ── 异常体系 ──────────────────────────────

class ApiConfigError(Exception):
    """API 未配置或配置无效"""

class ApiAuthError(Exception):
    """401 — Key 无效"""

class ApiQuotaError(Exception):
    """402 — 余额不足"""

class ApiRateLimitError(Exception):
    """429 — 限流"""

class ApiNetworkError(Exception):
    """网络不通 / 超时"""


# ── 客户端缓存 ────────────────────────────

# 实测 openai.OpenAI() 构造一次要 1.3~1.8 秒（httpx 客户端 + SSL 上下文，
# Windows 上尤其贵），而余额气泡每 60 秒就要查一次。按（key, base_url）缓存复用，
# 换 key 或换地址会自然落到新条目上。
_CLIENT_CACHE: dict[tuple, OpenAI] = {}


def _openai_for(api_key: str, base_url) -> OpenAI:
    cache_key = (api_key, base_url or "")
    client = _CLIENT_CACHE.get(cache_key)
    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url or None)
        _CLIENT_CACHE[cache_key] = client
    return client


# ── 客户端 ────────────────────────────────

class ApiClient:
    """统一 LLM 调用接口"""

    def __init__(self, config: ConfigManager = None):
        self._config = config or ConfigManager.instance()
        self._client = None
        self._build_client()

    def _build_client(self):
        if not self._config.api_key:
            self._client = None
            return
        base = self._config.api_base
        if self._config.api_type == "deepseek" and not base:
            base = "https://api.deepseek.com"
        self._client = _openai_for(self._config.api_key, base)

    @property
    def is_configured(self) -> bool:
        return bool(self._config.api_key)

    @property
    def api_type(self) -> str:
        return self._config.api_type

    def _get_model(self, model=None) -> str:
        return model or self._config.api_model or DEFAULT_MODEL

    # ── 流式对话（主要接口）────────────────

    def chat_stream(
        self, messages: list[dict], model: str = None
    ) -> Generator[str, None, None]:
        """发送对话请求，流式返回 token 生成器"""
        if not self._client:
            raise ApiConfigError("API 未配置，请先设置 API Key")

        try:
            response = self._client.chat.completions.create(
                model=self._get_model(model),
                messages=messages,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except AuthenticationError:
            raise ApiAuthError("API Key 无效，请检查后重试")
        except RateLimitError:
            raise ApiRateLimitError("请求太频繁，请稍后重试")
        # 注意顺序：APITimeoutError 是 APIConnectionError 的子类，
        # 超时分支必须写在前面，否则永远命中不了（超时会被报成"无法连接"）。
        except APITimeoutError:
            raise ApiNetworkError("API 响应超时")
        except APIConnectionError:
            raise ApiNetworkError("无法连接 API，请检查网络或 API 地址")
        except APIError as e:
            # 402 余额不足
            if getattr(e, "status_code", None) == 402:
                raise ApiQuotaError("余额不足，请充值后重试")
            raise ApiNetworkError(f"API 错误: {e}")

    # ── 余额查询（仅 DeepSeek）────────────

    def get_balance(self):
        """查询 DeepSeek 账户余额 → (balance: float, currency: str)

        自定义 OpenAI 兼容 API 不支持余额接口时返回 None；
        未配置 / 网络 / 鉴权失败抛对应 Api*Error。
        """
        if not self._config.api_key:
            raise ApiConfigError("API 未配置，请先设置 API Key")
        if self.api_type != "deepseek":
            return None
        base = (self._config.api_base or "https://api.deepseek.com").rstrip("/")
        req = urllib.request.Request(
            base + "/user/balance",
            headers={"Authorization": f"Bearer {self._config.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise ApiAuthError("API Key 无效")
            raise ApiNetworkError(f"余额查询失败 (HTTP {e.code})")
        except Exception as e:
            raise ApiNetworkError(f"余额查询失败: {e}")
        infos = data.get("balance_infos") or []
        if not infos:
            return None
        first = infos[0]
        return float(first.get("total_balance", 0.0)), first.get("currency", "CNY")
