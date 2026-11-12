from __future__ import annotations

import os
from dataclasses import dataclass

from .exceptions import GeoGPTConfigError


@dataclass(frozen=True)
class GeoGPTConfig:
    """GeoGPT 会话接口配置。"""

    base_url: str
    api_key: str
    module_name: str = "Qwen2.5-72B-GeoGPT"
    create_session_path: str = "/be-api/service/api/geoChat/generate"
    send_message_path: str = "/be-api/service/api/geoChat/sendMsg"
    timeout_seconds: float = 120.0
    trust_env: bool = True

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise GeoGPTConfigError("base_url must not be empty")
        if not self.api_key.strip():
            raise GeoGPTConfigError("api_key must not be empty")
        if not self.module_name.strip():
            raise GeoGPTConfigError("module_name must not be empty")
        if not self.create_session_path.startswith("/"):
            raise GeoGPTConfigError(
                "create_session_path must start with /"
            )
        if not self.send_message_path.startswith("/"):
            raise GeoGPTConfigError(
                "send_message_path must start with /"
            )
        if self.timeout_seconds <= 0:
            raise GeoGPTConfigError(
                "timeout_seconds must be greater than 0"
            )

    @classmethod
    def from_env(cls) -> "GeoGPTConfig":
        """从环境变量创建 GeoGPT 配置。"""

        base_url = os.getenv("GEOGPT_API_BASE", "").strip()
        api_key = os.getenv("GEOGPT_API_KEY", "").strip()
        if not base_url:
            raise GeoGPTConfigError(
                "Missing GEOGPT_API_BASE environment variable"
            )
        if not api_key:
            raise GeoGPTConfigError(
                "Missing GEOGPT_API_KEY environment variable"
            )

        raw_timeout_seconds = os.getenv("GEOGPT_TIMEOUT_SECONDS", "120")
        raw_trust_env = os.getenv("GEOGPT_TRUST_ENV", "true").strip().lower()
        if raw_trust_env not in {"true", "false", "1", "0", "yes", "no"}:
            raise GeoGPTConfigError(
                "GEOGPT_TRUST_ENV must be a boolean"
            )

        try:
            timeout_seconds = float(raw_timeout_seconds)
        except ValueError as error:
            raise GeoGPTConfigError(
                "GEOGPT_TIMEOUT_SECONDS must be a number"
            ) from error

        return cls(
            base_url=base_url,
            api_key=api_key,
            module_name=os.getenv(
                "GEOGPT_MODULE",
                "Qwen2.5-72B-GeoGPT",
            ),
            create_session_path=os.getenv(
                "GEOGPT_CREATE_SESSION_PATH",
                "/be-api/service/api/geoChat/generate",
            ),
            send_message_path=os.getenv(
                "GEOGPT_SEND_MESSAGE_PATH",
                "/be-api/service/api/geoChat/sendMsg",
            ),
            timeout_seconds=timeout_seconds,
            trust_env=raw_trust_env in {"true", "1", "yes"},
        )
