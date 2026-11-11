from __future__ import annotations

import math
import random
from collections.abc import Sequence

from powerpaleontology_core import Chunk

from .config import EmbeddingConfig
from .exceptions import EmbeddingConfigError, EmbeddingInputError


class FakeEmbeddingAdapter:
    """用于测试的确定性假 Embedding 适配器。"""

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        *,
        dimension: int = 384,
    ) -> None:
        """初始化假适配器。

        参数：
            config: Embedding 配置；不传时使用默认配置。
            dimension: 输出向量维度。
        """

        if dimension <= 0:
            raise EmbeddingConfigError("dimension must be greater than 0")

        self.config = config or EmbeddingConfig()
        self._dimension = dimension

    def get_dimension(self) -> int:
        """返回假模型生成的向量维度。"""

        return self._dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """把文本列表转换为确定性向量列表。"""

        if not texts:
            return []

        return [self._embed_text(text=text) for text in texts]

    def embed_chunks(self, chunks: Sequence[Chunk]) -> list[list[float]]:
        """把 Chunk 列表转换为确定性向量列表。"""

        if not chunks:
            return []

        return [self._embed_text(text=chunk.text) for chunk in chunks]

    def _embed_text(self, text: str) -> list[float]:
        """生成单条文本的确定性伪随机向量。"""

        if not text.strip():
            raise EmbeddingInputError("Embedding text must not be empty")

        if (
            self.config.max_input_characters is not None
            and len(text) > self.config.max_input_characters
        ):
            raise EmbeddingInputError(
                "Embedding text exceeds max_input_characters"
            )

        seed_material = f"{self.config.model_name}:{text}".encode("utf-8")
        seed = int.from_bytes(seed_material[:16], "big")
        generator = random.Random(seed)
        vector = [generator.gauss(0.0, 1.0) for _ in range(self._dimension)]

        if self.config.normalize_embeddings:
            norm = math.sqrt(sum(value * value for value in vector))

            if norm == 0:
                vector[0] = 1.0
            else:
                vector = [value / norm for value in vector]

        return vector
