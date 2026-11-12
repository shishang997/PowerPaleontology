from __future__ import annotations

import json

from .exceptions import GeoGPTInputError


_DEFAULT_RESPONSE = json.dumps(
    {
        "record": {},
        "evidence": {},
    },
    ensure_ascii=False,
)


class FakeGeoGPTAdapter:
    """用于测试的确定性 GeoGPT 适配器。"""

    def __init__(self, *, response: str | None = None) -> None:
        self.response = response
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:
        """记录请求并返回固定的 JSON 输出。"""

        if not prompt.strip():
            raise GeoGPTInputError("prompt must not be empty")

        self.calls.append(prompt)
        return self.response if self.response is not None else _DEFAULT_RESPONSE
