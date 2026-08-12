"""API 通信层 — 统一 LLM 调用接口（DeepSeek / 自定义 OpenAI 兼容）"""
from typing import Generator

from openai import OpenAI
from openai import (
    APIError, APIConnectionError, AuthenticationError,
    RateLimitError, APITimeoutError,
)

from module_2_api.config_manager import ConfigManager


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
        self._client = OpenAI(
            api_key=self._config.api_key,
            base_url=base or None,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._config.api_key)

    @property
    def api_type(self) -> str:
        return self._config.api_type

    def _get_model(self, model=None) -> str:
        return model or self._config.api_model or "deepseek-v4-flash"

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
        except APIConnectionError:
            raise ApiNetworkError("无法连接 API，请检查网络或 API 地址")
        except APITimeoutError:
            raise ApiNetworkError("API 响应超时")
        except APIError as e:
            # 402 余额不足
            if hasattr(e, "status_code") and e.status_code == 402:
                raise ApiQuotaError("余额不足，请充值后重试")
            raise ApiNetworkError(f"API 错误: {e}")

    # ── 非流式对话（备用）─────────────────

    def chat_sync(self, messages: list[dict], model: str = None) -> str:
        """一次性返回完整回复"""
        return "".join(self.chat_stream(messages, model))

    # ── 连通性测试 ─────────────────────────

    def ping(self) -> bool:
        """测试 API 连通性"""
        if not self._client:
            raise ApiConfigError("API 未配置")
        try:
            self._client.chat.completions.create(
                model=self._get_model(),
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except AuthenticationError:
            raise ApiAuthError("API Key 无效")
        except Exception:
            return False
