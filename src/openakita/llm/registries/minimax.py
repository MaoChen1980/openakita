"""
MiniMax 服务商注册表（OpenAI 兼容）

参考（常见 base_url）：
- 中国区： https://api.minimaxi.com/v1
- 国际区： https://api.minimax.io/v1
"""

import httpx

from ..capabilities import infer_capabilities
from .base import ModelInfo, ProviderInfo, ProviderRegistry


class MiniMaxChinaRegistry(ProviderRegistry):
    info = ProviderInfo(
        name="MiniMax（中国区）",
        slug="minimax-cn",
        api_type="openai",
        default_base_url="https://api.minimaxi.com/v1",
        api_key_env_suggestion="MINIMAX_API_KEY",
        supports_model_list=True,
        supports_capability_api=False,
    )

    async def list_models(self, api_key: str) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.info.default_base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                # 部分账号/区域可能没有 models 权限；失败时返回空列表，允许用户手动填模型名。
                return []

        out: list[ModelInfo] = []
        seen: set[str] = set()
        for m in data.get("data", []) or []:
            if not isinstance(m, dict):
                continue
            mid = (m.get("id") or "").strip()
            if not mid:
                continue
            if mid in seen:
                continue
            seen.add(mid)
            out.append(ModelInfo(id=mid, name=mid, capabilities=infer_capabilities(mid, provider_slug="minimax")))
        return sorted(out, key=lambda x: x.id)


class MiniMaxInternationalRegistry(ProviderRegistry):
    info = ProviderInfo(
        name="MiniMax（国际区）",
        slug="minimax-int",
        api_type="openai",
        default_base_url="https://api.minimax.io/v1",
        api_key_env_suggestion="MINIMAX_API_KEY",
        supports_model_list=True,
        supports_capability_api=False,
    )

    async def list_models(self, api_key: str) -> list[ModelInfo]:
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(
                    f"{self.info.default_base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError:
                return []

        out: list[ModelInfo] = []
        seen: set[str] = set()
        for m in data.get("data", []) or []:
            if not isinstance(m, dict):
                continue
            mid = (m.get("id") or "").strip()
            if not mid:
                continue
            if mid in seen:
                continue
            seen.add(mid)
            out.append(ModelInfo(id=mid, name=mid, capabilities=infer_capabilities(mid, provider_slug="minimax")))
        return sorted(out, key=lambda x: x.id)

