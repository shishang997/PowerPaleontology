from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import httpx

from powerpaleontology_core import Chunk

from .config import EmbeddingConfig
from .exceptions import EmbeddingInputError, EmbeddingModelError


class OpenAICompatibleEmbeddingAdapter:
    """调用 OpenAI 兼容 `/embeddings` 接口的远程适配器。"""

    def __init__(
        self,
        config: EmbeddingConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """初始化远程适配器。

        参数：
            config: 必须包含远程服务地址和模型名。
            transport: 可注入的 HTTP 传输层，主要用于单元测试。
        """

        self.config = config
        self._http = httpx.Client(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )
        self._dimension: int | None = None

    def close(self) -> None:
        """关闭底层 HTTP 连接。"""

        self._http.close()

    def __enter__(self) -> "OpenAICompatibleEmbeddingAdapter":
        """支持 with 语句。"""

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """退出时自动关闭 HTTP 连接。"""

        self.close()

    def get_dimension(self) -> int:
        """探测并缓存远程模型的向量维度。"""

        if self._dimension is None:
            probe_vectors = self.embed_texts(["dimension probe"])
            self._dimension = len(probe_vectors[0])

        return self._dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """把文本列表发送到远程 Embedding 服务。"""

        if not texts:
            return []

        vectors: list[list[float]] = []

        for start in range(0, len(texts), self.config.batch_size):
            batch = texts[start : start + self.config.batch_size]
            vectors.extend(self._embed_batch(batch))

        return vectors

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[list[float]]:
        """把 Chunk 列表发送到远程 Embedding 服务。"""

        if not chunks:
            return []

        return self.embed_texts([chunk.text for chunk in chunks])

    def _embed_batch(self, batch: Sequence[str]) -> list[list[float]]:
        """调用 OpenAI 兼容接口并解析批量向量。"""

        normalized_batch: list[str] = []

        for text in batch:
            if not text.strip():
                raise EmbeddingInputError("Embedding text must not be empty")

            if (
                self.config.max_input_characters is not None
                and len(text) > self.config.max_input_characters
            ):
                raise EmbeddingInputError(
                    "Embedding text exceeds max_input_characters"
                )

            normalized_batch.append(text)

        response = self._request_json(
            path="/embeddings",
            json_payload={
                "model": self.config.model_name,
                "input": normalized_batch,
            },
        )
        raw_data = response.get("data")

        if not isinstance(raw_data, list):
            raise EmbeddingModelError(
                "Remote embedding response does not contain data"
            )

        if len(raw_data) != len(normalized_batch):
            raise EmbeddingModelError(
                "Remote service returned a different number of embeddings"
            )

        embeddings: list[object | None] = [None] * len(normalized_batch)

        for index, item in enumerate(raw_data):
            if not isinstance(item, dict):
                raise EmbeddingModelError(
                    "Remote embedding item is not an object"
                )

            item_index = item.get("index", index)

            try:
                target_index = int(item_index)

            except (TypeError, ValueError) as error:
                raise EmbeddingModelError(
                    "Remote embedding item has invalid index"
                ) from error

            if target_index < 0 or target_index >= len(embeddings):
                raise EmbeddingModelError(
                    "Remote embedding item index is out of range"
                )

            embeddings[target_index] = item.get("embedding")

        vectors = [
            self._normalize_vector(embedding)
            for embedding in embeddings
        ]

        if self._dimension is None and vectors:
            self._dimension = len(vectors[0])

        return vectors

    def _request_json(
        self,
        path: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """发送带认证头的 HTTP 请求并解析 JSON。"""

        headers: dict[str, str] = {"Accept": "application/json"}

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            response = self._http.post(
                path,
                json=json_payload,
                headers=headers,
            )

        except httpx.RequestError as error:
            raise EmbeddingModelError(
                f"Failed to call remote embedding API: {error}"
            ) from error

        if response.status_code >= 400:
            raise EmbeddingModelError(
                f"Remote embedding API returned status {response.status_code}: "
                f"{response.text}"
            )

        try:
            payload = response.json()

        except ValueError as error:
            raise EmbeddingModelError(
                "Remote embedding API returned invalid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise EmbeddingModelError(
                "Remote embedding API JSON response is not an object"
            )

        return payload

    def _normalize_vector(self, vector: object) -> list[float]:
        """校验并按配置归一化远程返回的向量。"""

        if not isinstance(vector, list):
            raise EmbeddingModelError("Remote embedding is not a list")

        try:
            float_vector = [float(value) for value in vector]

        except (TypeError, ValueError) as error:
            raise EmbeddingModelError(
                "Remote embedding contains non-numeric values"
            ) from error

        if not float_vector:
            raise EmbeddingModelError("Remote embedding is empty")

        if not self.config.normalize_embeddings:
            return float_vector

        norm = math.sqrt(sum(value * value for value in float_vector))

        if norm == 0:
            return float_vector

        return [value / norm for value in float_vector]
