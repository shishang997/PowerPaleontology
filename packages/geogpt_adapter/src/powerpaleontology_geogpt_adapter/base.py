from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class GeoGPTAdapter(Protocol):
    """GeoGPT / LLM 适配器的统一接口。"""

    def complete(self, prompt: str) -> str:
        """发送 prompt，并返回模型输出的原始文本。"""

        ...
