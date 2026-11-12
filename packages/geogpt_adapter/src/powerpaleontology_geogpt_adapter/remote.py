from __future__ import annotations

import json
from typing import Any

import httpx

from .config import GeoGPTConfig
from .exceptions import GeoGPTInputError, GeoGPTModelError


class GeoGPTHTTPAdapter:
    """调用 GeoGPT 会话接口并返回完整模型输出。"""

    def __init__(
        self,
        config: GeoGPTConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._http = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
            follow_redirects=True,
            trust_env=config.trust_env,
            transport=transport,
        )

    def close(self) -> None:
        """关闭底层 HTTP 连接。"""

        self._http.close()

    def __enter__(self) -> "GeoGPTHTTPAdapter":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def complete(self, prompt: str) -> str:
        """创建一次性会话，发送 prompt 并拼接流式输出。"""

        if not prompt.strip():
            raise GeoGPTInputError("prompt must not be empty")

        session_id = self._create_session()
        return self._send_message(prompt, session_id)

    def _create_session(self) -> str:
        payload = self._request_json(path=self.config.create_session_path)
        if payload.get("code") != "00000":
            raise GeoGPTModelError(
                f"GeoGPT create-session API failed: {payload}"
            )

        session_id = payload.get("data")
        if not isinstance(session_id, str) or not session_id.strip():
            raise GeoGPTModelError(
                "GeoGPT create-session response has no session_id"
            )
        return session_id

    def _send_message(
        self,
        prompt: str,
        session_id: str,
    ) -> str:
        payload = {
            "text": prompt,
            "sessionId": session_id,
            "module": self.config.module_name,
            "isRAG": False,
            "isRAGCommon": False,
        }
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        content_parts: list[str] = []

        try:
            with self._http.stream(
                "POST",
                self.config.send_message_path,
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    raise GeoGPTModelError(
                        f"GeoGPT API returned status {response.status_code}: "
                        f"{response.text}"
                    )

                for line in response.iter_lines():
                    parsed = self._parse_sse_line(line)
                    if parsed is None:
                        continue
                    content = self._extract_delta_content(parsed)
                    if content:
                        content_parts.append(content)
        except httpx.RequestError as error:
            raise GeoGPTModelError(
                f"Failed to call GeoGPT API: {error}"
            ) from error

        content = "".join(content_parts)
        if not content.strip():
            raise GeoGPTModelError(
                "GeoGPT API response content is empty"
            )
        return content

    def _request_json(self, *, path: str) -> dict[str, Any]:
        try:
            response = self._http.get(
                path,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
            )
        except httpx.RequestError as error:
            raise GeoGPTModelError(
                f"Failed to call GeoGPT API: {error}"
            ) from error

        if response.status_code >= 400:
            raise GeoGPTModelError(
                f"GeoGPT API returned status {response.status_code}: "
                f"{response.text}"
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise GeoGPTModelError(
                "GeoGPT API returned invalid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise GeoGPTModelError(
                "GeoGPT API JSON response is not an object"
            )
        return payload

    @staticmethod
    def _parse_sse_line(line: str) -> Any:
        stripped = line.strip()
        if not stripped.startswith("data:"):
            return None

        raw_payload = stripped[5:].strip()
        if not raw_payload:
            return None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as error:
            raise GeoGPTModelError(
                "GeoGPT API returned invalid SSE JSON"
            ) from error

        if isinstance(payload, str):
            if payload.strip() == "[DONE]":
                return None
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as error:
                raise GeoGPTModelError(
                    "GeoGPT API returned invalid SSE JSON"
                ) from error
        return payload

    @staticmethod
    def _extract_delta_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""

        choice = choices[0]
        if not isinstance(choice, dict):
            return ""

        delta = choice.get("delta")
        if not isinstance(delta, dict):
            return ""

        content = delta.get("content")
        return content if isinstance(content, str) else ""
