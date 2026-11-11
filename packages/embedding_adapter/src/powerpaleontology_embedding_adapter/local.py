from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import httpx

from powerpaleontology_core import Chunk

from .config import EmbeddingConfig
from .exceptions import EmbeddingInputError, EmbeddingModelError


class OllamaEmbeddingAdapter:
    """基于本机 Ollama HTTP 服务的 Embedding 适配器。"""

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """初始化 Ollama 适配器。

        参数：
            config: Embedding 配置；不传时使用默认配置。
            transport: 可注入的 HTTP 传输层，主要用于单元测试。
        """

        self.config = config or EmbeddingConfig()
        self._http = httpx.Client(
            base_url=self.config.base_url.rstrip("/"),
            timeout=self.config.timeout_seconds,
            follow_redirects=True,
            transport=transport,
        )
        self._dimension: int | None = None

    def close(self) -> None:
        """关闭底层 HTTP 连接。"""

        self._http.close()

    def __enter__(self) -> "OllamaEmbeddingAdapter":
        """支持 with 语句。"""

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """退出时自动关闭 HTTP 连接。"""

        self.close()

    def get_dimension(self) -> int:
        """探测并缓存当前模型的向量维度。"""

        if self._dimension is None:
            probe_vectors = self.embed_texts(["dimension probe"])
            self._dimension = len(probe_vectors[0])

        return self._dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """把文本列表交给 Ollama，返回向量列表。"""

        if not texts:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.batch_size):
            batch = texts[start : start + self.config.batch_size]
            vectors.extend(self._embed_batch(batch))

        return vectors

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[list[float]]:
        """把 Chunk 列表交给 Ollama，返回向量列表。"""

        if not chunks:
            return []

        return self.embed_texts([chunk.text for chunk in chunks])

    def _embed_batch(self, batch: Sequence[str]) -> list[list[float]]:
        """调用 Ollama 批量 Embedding 接口。"""

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

        payload = {
            "model": self.config.model_name,
            "input": normalized_batch,
        }
        response = self._request_json(path="/api/embed", json_payload=payload)
        embeddings = response.get("embeddings")

        if not isinstance(embeddings, list):
            raise EmbeddingModelError(
                "Ollama response does not contain embeddings"
            )

        if len(embeddings) != len(normalized_batch):
            raise EmbeddingModelError(
                "Ollama returned a different number of embeddings"
            )

        vectors = [self._normalize_vector(embedding) for embedding in embeddings]

        if self._dimension is None and vectors:
            self._dimension = len(vectors[0])

        return vectors

    def _request_json(
        self,
        path: str,
        json_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """发送 HTTP 请求并解析 JSON 响应。"""

        try:
            response = self._http.post(path, json=json_payload)

        except httpx.RequestError as error:
            raise EmbeddingModelError(
                f"Failed to call Ollama embedding API: {error}"
            ) from error

        if response.status_code >= 400:
            raise EmbeddingModelError(
                f"Ollama embedding API returned status {response.status_code}: "
                f"{response.text}"
            )

        try:
            payload = response.json()

        except ValueError as error:
            raise EmbeddingModelError(
                "Ollama embedding API returned invalid JSON"
            ) from error

        if not isinstance(payload, dict):
            raise EmbeddingModelError(
                "Ollama embedding API JSON response is not an object"
            )

        return payload

    def _normalize_vector(self, vector: object) -> list[float]:
        """校验并按配置归一化单个向量。"""

        if not isinstance(vector, list):
            raise EmbeddingModelError("Ollama embedding is not a list")

        try:
            float_vector = [float(value) for value in vector]

        except (TypeError, ValueError) as error:
            raise EmbeddingModelError(
                "Ollama embedding contains non-numeric values"
            ) from error

        if not float_vector:
            raise EmbeddingModelError("Ollama embedding is empty")

        if not self.config.normalize_embeddings:
            return float_vector

        norm = math.sqrt(sum(value * value for value in float_vector))

        if norm == 0:
            return float_vector

        return [value / norm for value in float_vector]
